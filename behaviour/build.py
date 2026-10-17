"""Build the BH1 blind labelling package (PROTOCOL.md sections 5-6).

Three steps, each run once the step before it is done. None has been run on real clips.

1. ``identity-template``: after the owner's ruling has produced ``pool/selection.json``, write
   ``work/identity.csv`` with one row per selected clip. A person (not an AI, and not one of
   the behaviour labellers) fills ``cat_id`` and the target description by watching the clips on
   Commons. The filled file stays private until labelling is locked: its digest goes into the
   manifest, so the cat grouping cannot be changed after labels are seen.
2. ``fetch``: download each selected clip into ``work/media/`` and extract frames at 4 fps from
   the first 20 s into ``work/frames/<key>/`` (no audio is ever extracted).
3. ``package``: assign opaque clip ids in an order drawn from a private 256-bit salt, cut each
   clip into 2 s segments, and write

   * ``package/label-TEMPLATE.csv``: one row per segment, opaque ids only (committed);
   * ``package/media.json``: the SHA-256 of every sheet and segment video (committed), so a
     labeller can check the files they were sent;
   * ``package/commitment.json``: counts and ``root_sha256`` of the private manifest (committed);
   * ``work/package/sheets/*.jpg`` and ``work/package/segments/*.mp4``: what labellers receive,
     distributed outside git because of their size;
   * ``work/key.json``, ``work/manifest.json``, ``work/SECRET-salt.txt``: private until every
     registered labeller has locked (``withholding.py``).

Why opaque ids: Commons titles name behaviour ("Cat behaviour - self-grooming", "cat
jumping backwards"), so a title visible to a labeller is a label leak.

    python -m behaviour.build identity-template
    python -m behaviour.build fetch
    python -m behaviour.build package
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import secrets
import shutil
import subprocess
import urllib.request
from pathlib import Path
from typing import Any, Callable

from PIL import Image, ImageDraw, ImageFont

from behaviour.common import (FRAMES_PER_SEGMENT, MAX_SECONDS, PACKAGE, SAMPLE_FPS, SEGMENT_S, TEMPLATE_COLUMNS, WORK,
                              n_segments, read_csv, segment_id, sha256_file, write_csv, write_json)
from behaviour.sample_pool import POOL_DIR

SALT_PATH = WORK / "SECRET-salt.txt"
KEY_PATH = WORK / "key.json"
MANIFEST_PATH = WORK / "manifest.json"
IDENTITY_PATH = WORK / "identity.csv"
IDENTITY_COLUMNS = ["title", "url", "uploader", "cat_id", "n_cats_visible", "target_description", "identity_confidence", "checker", "note"]
IDENTITY_CONFIDENCE = {"sure", "likely", "unsure"}
TILE_WIDTH = 240
UA = "cat-pose-benchmark/0.1 (BH1 fetch; https://github.com/in-c0/cat-pose-benchmark)"

Frames = Callable[[str], list[tuple[float, Image.Image]]]


def title_key(title: str) -> str:
    """Directory name for a clip's private working files."""
    return hashlib.sha256(title.encode("utf-8")).hexdigest()[:16]


def load_or_create_salt(path: Path = SALT_PATH) -> str:
    if path.exists():
        salt = path.read_text(encoding="utf-8").strip()
    else:
        salt = secrets.token_hex(32)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(salt + "\n", encoding="utf-8")
    if len(salt) != 64 or any(c not in "0123456789abcdef" for c in salt):
        raise SystemExit(f"{path}: expected 64 hex characters")
    return salt


def opaque_order(titles: list[str], salt: str) -> dict[str, str]:
    """Commons title -> opaque clip id. The order comes from the private salt, not a public seed."""
    order = sorted(titles)
    random.Random(int.from_bytes(hashlib.sha256(b"bh1-clips|" + salt.encode()).digest(), "big")).shuffle(order)
    return {t: f"BH1-C{i:03d}" for i, t in enumerate(order, start=1)}


def manifest_root(manifest: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


# ---------------------------------------------------------------- identity pass


def identity_template(selection: dict[str, Any], pool: dict[str, dict[str, Any]], path: Path = IDENTITY_PATH) -> None:
    if path.exists():
        raise SystemExit(f"{path} exists; refusing to overwrite a filled identity file")
    rows = [{"title": s["title"], "url": pool[s["title"]]["url"], "uploader": s["uploader"], **{c: "" for c in IDENTITY_COLUMNS[3:]}}
            for s in selection["selected"]]
    write_csv(path, IDENTITY_COLUMNS, rows)


def validate_identity(rows: list[dict[str, str]], titles: list[str]) -> dict[str, dict[str, str]]:
    """Every selected clip needs a cat_id, a target description and a named checker. Nothing is inferred."""
    by_title = {r["title"]: r for r in rows}
    errors = []
    for t in titles:
        r = by_title.get(t)
        if r is None:
            errors.append(f"{t}: missing from the identity file")
            continue
        for col in ("cat_id", "target_description", "checker"):
            if not (r.get(col) or "").strip():
                errors.append(f"{t}: {col} is blank")
        if (r.get("identity_confidence") or "").strip() not in IDENTITY_CONFIDENCE:
            errors.append(f"{t}: identity_confidence must be one of {sorted(IDENTITY_CONFIDENCE)}")
        if not (r.get("n_cats_visible") or "").strip().isdigit():
            errors.append(f"{t}: n_cats_visible must be a whole number")
    extra = set(by_title) - set(titles)
    if extra:
        errors.append(f"identity rows for clips not in the selection: {sorted(extra)[:5]}")
    if errors:
        raise ValueError("; ".join(errors[:10]) + (" ..." if len(errors) > 10 else ""))
    return {t: by_title[t] for t in titles}


# ---------------------------------------------------------------- fetch (run step; needs network and ffmpeg)


def _ffmpeg() -> str:
    import imageio_ffmpeg

    return imageio_ffmpeg.get_ffmpeg_exe()


def fetch(selected: list[dict[str, Any]], pool: dict[str, dict[str, Any]]) -> None:
    for s in selected:
        f = pool[s["title"]]
        key = title_key(s["title"])
        media = WORK / "media" / (key + Path(f["url"].split("?")[0]).suffix)
        if not media.exists():
            media.parent.mkdir(parents=True, exist_ok=True)
            req = urllib.request.Request(f["url"], headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=300) as r, media.with_suffix(".part").open("wb") as h:
                shutil.copyfileobj(r, h)
            media.with_suffix(".part").replace(media)
        out = WORK / "frames" / key
        if out.exists():
            shutil.rmtree(out)
        out.mkdir(parents=True)
        subprocess.run([_ffmpeg(), "-hide_banner", "-loglevel", "error", "-y", "-i", str(media), "-t", str(MAX_SECONDS),
                        "-vf", f"fps={SAMPLE_FPS}", "-an", str(out / "f%04d.jpg")], check=True)
        frames = sorted(out.glob("f*.jpg"))
        write_json(out / "frames.json", {"title": s["title"], "media_sha256": sha256_file(media), "fps": SAMPLE_FPS,
                                         "frames": [{"file": p.name, "t": round(i / SAMPLE_FPS, 4), "sha256": sha256_file(p)} for i, p in enumerate(frames)]})


def frames_from_work(title: str) -> list[tuple[float, Image.Image]]:
    d = WORK / "frames" / title_key(title)
    meta = json.loads((d / "frames.json").read_text(encoding="utf-8"))
    return [(f["t"], Image.open(d / f["file"]).convert("RGB")) for f in meta["frames"]]


def cut_segment_video(title: str, out: Path, t0: float) -> None:
    """Silent 2 s clip of one segment, scaled to 480 px high."""
    media = next((WORK / "media").glob(title_key(title) + ".*"))
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([_ffmpeg(), "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{t0:.3f}", "-i", str(media), "-t", f"{SEGMENT_S:.3f}",
                    "-an", "-vf", "scale=-2:480", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(out)], check=True)


# ---------------------------------------------------------------- package


def _font(size: int) -> ImageFont.ImageFont:
    for name in ("DejaVuSans.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def segment_frames(frames: list[tuple[float, Image.Image]], k: int) -> list[Image.Image]:
    lo, hi = k * SEGMENT_S, (k + 1) * SEGMENT_S
    return [im for t, im in frames if lo - 1e-6 <= t < hi - 1e-6][:FRAMES_PER_SEGMENT]


def render_sheet(clip_id: str, target: str, rows: list[list[Image.Image]], path: Path) -> None:
    """One row per segment, frames left to right in time. Nothing is drawn on the frames."""
    font, small = _font(18), _font(14)
    tiles = []
    for frames in rows:
        scaled = [im.resize((TILE_WIDTH, max(1, round(im.height * TILE_WIDTH / im.width))), Image.LANCZOS) for im in frames]
        tiles.append(scaled)
    th = max((im.height for r in tiles for im in r), default=TILE_WIDTH)
    gap, label_w, head = 6, 110, 34
    width = label_w + FRAMES_PER_SEGMENT * (TILE_WIDTH + gap) + gap
    sheet = Image.new("RGB", (width, head + len(tiles) * (th + gap) + gap), (50, 50, 50))
    d = ImageDraw.Draw(sheet)
    d.text((8, 8), f"{clip_id}    target cat: {target}", fill=(255, 255, 255), font=font)
    for k, r in enumerate(tiles):
        y = head + k * (th + gap)
        d.text((8, y + 4), f"S{k:02d}", fill=(255, 255, 255), font=font)
        d.text((8, y + 28), f"{k * SEGMENT_S:.0f}-{(k + 1) * SEGMENT_S:.0f} s", fill=(200, 200, 200), font=small)
        for j, im in enumerate(r):
            sheet.paste(im, (label_w + gap + j * (TILE_WIDTH + gap), y))
    path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(path, quality=85)


def build_package(selected: list[dict[str, Any]], identity: dict[str, dict[str, str]], frames: Frames, salt: str,
                  package_dir: Path = PACKAGE, work: Path = WORK, cut_video: Callable[[str, Path, float], None] | None = None) -> dict[str, Any]:
    titles = [s["title"] for s in selected]
    ids = opaque_order(titles, salt)
    out = work / "package"
    if out.exists():
        shutil.rmtree(out)
    rows, key = [], {}
    for s in sorted(selected, key=lambda s: ids[s["title"]]):
        clip = ids[s["title"]]
        idn = identity[s["title"]]
        fr = frames(s["title"])
        n = min(n_segments(s["duration_s"]), int(len(fr) // FRAMES_PER_SEGMENT))
        sheet = f"{clip}.jpg"
        render_sheet(clip, idn["target_description"], [segment_frames(fr, k) for k in range(n)], out / "sheets" / sheet)
        for k in range(n):
            sid = segment_id(clip, k)
            if cut_video:
                cut_video(s["title"], out / "segments" / f"{sid}.mp4", k * SEGMENT_S)
            rows.append({"segment_id": sid, "clip_id": clip, "segment": k, "t_start_s": f"{k * SEGMENT_S:.1f}", "t_end_s": f"{(k + 1) * SEGMENT_S:.1f}",
                         "sheet": sheet, "behaviour": "", "note": ""})
        key[clip] = {"title": s["title"], "uploader": s["uploader"], "licence": s["licence"], "cat_id": idn["cat_id"].strip(),
                     "identity_confidence": idn["identity_confidence"], "n_cats_visible": int(idn["n_cats_visible"]),
                     "target_description": idn["target_description"], "n_segments": n}
    write_csv(package_dir / "label-TEMPLATE.csv", TEMPLATE_COLUMNS, rows)
    write_json(work / "key.json", {"clips": key})
    media = {f"{p.parent.name}/{p.name}": sha256_file(p) for p in sorted(out.rglob("*")) if p.is_file()}
    write_json(package_dir / "media.json", {"note": "SHA-256 of each file sent to labellers (sheets/, segments/).", "files": media})
    manifest = {
        "salt": salt, "n_clips": len(key), "n_segments": len(rows),
        "key_sha256": sha256_file(work / "key.json"), "template_sha256": sha256_file(package_dir / "label-TEMPLATE.csv"),
        "identity_sha256": hashlib.sha256(json.dumps({t: identity[t] for t in sorted(identity)}, sort_keys=True).encode()).hexdigest(),
        "media": media,
    }
    write_json(work / "manifest.json", manifest)
    commitment = {
        "note": ("The key (opaque clip id -> Commons title and cat_id), the identity pass and the manifest (which holds the salt) "
                 "stay private until every registered labeller has locked. root_sha256 is the SHA-256 of the canonical manifest; "
                 "see behaviour/PROTOCOL.md section 6."),
        "scheme": "sha256(json.dumps(manifest, sort_keys=True, separators=(',', ':')))",
        "n_clips": len(key), "n_segments": len(rows), "root_sha256": manifest_root(manifest),
    }
    write_json(package_dir / "commitment.json", commitment)
    return commitment


def _selection() -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    path = POOL_DIR / "selection.json"
    if not path.exists():
        raise SystemExit("pool/selection.json does not exist: the selection waits for the owner's ruling (PROTOCOL.md section 4)")
    pool = {f["title"]: f for f in json.loads((POOL_DIR / "pool.json").read_text(encoding="utf-8"))["files"]}
    return json.loads(path.read_text(encoding="utf-8")), pool


def main() -> None:
    p = argparse.ArgumentParser(description="Build the BH1 labelling package.")
    p.add_argument("step", choices=["identity-template", "fetch", "package"])
    p.add_argument("--no-videos", action="store_true", help="sheets only, no per-segment video")
    a = p.parse_args()
    selection, pool = _selection()
    if a.step == "identity-template":
        identity_template(selection, pool)
        print(f"wrote {IDENTITY_PATH}; fill it by watching each clip on Commons")
    elif a.step == "fetch":
        fetch(selection["selected"], pool)
    else:
        identity = validate_identity(read_csv(IDENTITY_PATH), [s["title"] for s in selection["selected"]])
        c = build_package(selection["selected"], identity, frames_from_work, load_or_create_salt(),
                          cut_video=None if a.no_videos else cut_segment_video)
        print(f"{c['n_clips']} clips, {c['n_segments']} segments; root {c['root_sha256'][:12]}... committed")


if __name__ == "__main__":
    main()
