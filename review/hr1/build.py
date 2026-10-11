"""Build the HR1 independent human-review package.

Stage A (blind): contact sheets of raw frames, no model output anywhere on them, and an
empty CSV with one row per frame. Reviewers say whether a cat's tail can be seen.

Stage B (images released after Stage A is locked): one image per distinct tail curve that
v1 or v3 reported, shuffled across clips, method identity hidden, drawn in one colour. The
reviewer says whether the line lies on a cat's tail. A few items are shown twice to measure
how consistent each reviewer is with themself.

The shuffle is driven by a secret salt (``review/work/hr1/SECRET-salt.txt``, git-ignored), not
by a public seed: with a public seed, anyone holding the method outputs could rebuild the key
from this file. Everything that maps an item to its clip, frame or method stays private
until every reviewer has locked Stage B: the key, the per-method outputs, and the manifest
of digests (which contains the salt). The repository gets one number now,
``root_sha256`` in ``package/stage_b_commitment.json``: the SHA-256 of the canonical
manifest. Because the manifest includes a 256-bit salt, the root reveals nothing about the
items, yet once the manifest is published anyone can check that no item, key entry or output
changed after the commitment (``python -m review.hr1.withholding --verify-release``).

Also exports the compact method outputs the package was built from
(``outputs/<clip>--<method>.json``: status, box and reported curve per frame), because the
full ``result.json`` files were never committed and the numbers in notes 05/06 could not be
re-derived from the repository alone. They name the method, so they are private until
Stage B is locked by everyone (``review/work/hr1/outputs``).

    python -m review.hr1.build             # after the v1/v3 runs exist under review/work
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import secrets
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from review.common import REPO_ROOT, clip_workdir, frames_dir, load_frames_manifest, write_json
from review.hr1.withholding import MANIFEST_PATH, SALT_PATH, STAGE_B_WORK, manifest_root, shuffle_rng
from review.score_truth import load_truth

HERE = Path(__file__).resolve().parent
PACKAGE = HERE / "package"
OUTPUTS = STAGE_B_WORK.parent / "outputs"

SETS = {"holdout1": "holdout_frames.csv", "holdout2": "holdout2_frames.csv"}
METHODS = ("tail_grounded_v1", "tail_grounded_v3")
N_REPEATS = 15
SHEET_COLUMNS = 4
SHEET_ROWS = 5
TILE_WIDTH = 480
LINE = (255, 0, 255)

STAGE_A_COLUMNS = ["clip_id", "frame_index", "timestamp_s", "sheet", "tail", "note"]
STAGE_B_COLUMNS = ["item_id", "on_tail", "note"]


def _clips_by_set() -> dict[str, list[str]]:
    return {s: sorted({k[0] for k in load_truth(f)}) for s, f in SETS.items()}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _font(size: int) -> ImageFont.ImageFont:
    for name in ("DejaVuSans.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def load_or_create_salt(path: Path = SALT_PATH) -> str:
    """The private shuffle salt. Created once; reused on rebuild so the item order is stable."""
    if path.exists():
        salt = path.read_text(encoding="utf-8").strip()
    else:
        salt = secrets.token_hex(32)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(salt + "\n", encoding="utf-8")
    if len(salt) != 64 or any(c not in "0123456789abcdef" for c in salt):
        raise SystemExit(f"{path}: expected 64 hex characters")
    return salt


# ---------------------------------------------------------------- method outputs


def export_outputs(clips: list[str]) -> dict[str, dict[str, Any]]:
    """Compact per-frame record of what each method reported, committed for reproducibility."""
    out: dict[str, dict[str, Any]] = {}
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    for clip in clips:
        for method in METHODS:
            path = clip_workdir(clip) / method / "result.json"
            result = json.loads(path.read_text(encoding="utf-8"))
            frames = []
            for f in result["frames"]:
                curve = f.get("curve") or {}
                frames.append({
                    "frame_index": f["frame_index"],
                    "status": f["status"],
                    "box": (f.get("tail") or {}).get("box"),
                    "curve": [[round(s["x_px"], 1), round(s["y_px"], 1)] for s in curve.get("samples", [])],
                })
            payload = {"clip_id": clip, "method": method, "source": f"review/work/{clip}/{method}/result.json",
                       "result_sha256": _sha(path), "frames": frames}
            write_json(OUTPUTS / f"{clip}--{method}.json", payload)
            out[f"{clip}--{method}"] = payload
    return out


# ---------------------------------------------------------------- stage A


def build_stage_a(clips_by_set: dict[str, list[str]], out_dir: Path) -> list[dict[str, Any]]:
    sheets_dir = out_dir / "stage_a" / "sheets"
    sheets_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    font = _font(18)
    per_sheet = SHEET_COLUMNS * SHEET_ROWS
    for set_name, clips in clips_by_set.items():
        for clip in clips:
            manifest = load_frames_manifest(clip)
            frames = manifest["frames"]
            for start in range(0, len(frames), per_sheet):
                chunk = frames[start:start + per_sheet]
                sheet_name = f"{clip}--{start // per_sheet + 1:02d}.jpg"
                tiles = []
                for fr in chunk:
                    img = Image.open(frames_dir(clip) / fr["file"]).convert("RGB")
                    img = img.resize((TILE_WIDTH, round(img.height * TILE_WIDTH / img.width)), Image.LANCZOS)
                    tile = Image.new("RGB", (TILE_WIDTH, img.height + 30), (0, 0, 0))
                    tile.paste(img, (0, 30))
                    ImageDraw.Draw(tile).text((8, 5), f"{clip}  frame {fr['frame_index']}  ({fr['timestamp_s']:.2f} s)", fill=(255, 255, 255), font=font)
                    tiles.append(tile)
                    rows.append({"clip_id": clip, "frame_index": fr["frame_index"], "timestamp_s": f"{fr['timestamp_s']:.4f}",
                                 "sheet": sheet_name, "tail": "", "note": ""})
                th = max(t.height for t in tiles)
                ncols = min(SHEET_COLUMNS, len(tiles))
                nrows = (len(tiles) + SHEET_COLUMNS - 1) // SHEET_COLUMNS
                gap = 8
                sheet = Image.new("RGB", (ncols * (TILE_WIDTH + gap) + gap, nrows * (th + gap) + gap), (60, 60, 60))
                for i, t in enumerate(tiles):
                    r, c = divmod(i, SHEET_COLUMNS)
                    sheet.paste(t, (gap + c * (TILE_WIDTH + gap), gap + r * (th + gap)))
                sheet.save(sheets_dir / sheet_name, quality=88)
    with (out_dir / "stage_a" / "stage-a-TEMPLATE.csv").open("w", newline="", encoding="utf-8") as h:
        w = csv.DictWriter(h, fieldnames=STAGE_A_COLUMNS)
        w.writeheader()
        w.writerows(rows)
    return rows


# ---------------------------------------------------------------- stage B


def _curve_key(curve: list[list[float]]) -> str:
    return hashlib.sha256(json.dumps([[round(x), round(y)] for x, y in curve]).encode()).hexdigest()[:16]


def _render_item(clip: str, frame_file: str, curve: list[list[float]], item_id: str, path: Path) -> None:
    img = Image.open(frames_dir(clip) / frame_file).convert("RGB")
    scale = min(1.0, 960 / img.width, 720 / img.height)
    xs, ys = [p[0] for p in curve], [p[1] for p in curve]
    # zoom panel: curve extent padded to at least 3x and 160 px, kept inside the frame
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    side = max(160.0, 3 * max(max(xs) - min(xs), max(ys) - min(ys)))
    side = min(side, img.width, img.height)
    x0 = min(max(cx - side / 2, 0), img.width - side)
    y0 = min(max(cy - side / 2, 0), img.height - side)

    def draw_line(im: Image.Image, pts: list[tuple[float, float]], width: int) -> None:
        d = ImageDraw.Draw(im)
        if len(pts) == 1:
            pts = pts * 2
        d.line(pts, fill=(0, 0, 0), width=width + 4, joint="curve")
        d.line(pts, fill=LINE, width=width, joint="curve")
        for x, y in (pts[0], pts[-1]):
            d.ellipse((x - width, y - width, x + width, y + width), fill=LINE, outline=(0, 0, 0))

    full = img.resize((round(img.width * scale), round(img.height * scale)), Image.LANCZOS)
    draw_line(full, [(x * scale, y * scale) for x, y in curve], 3)
    zoom_px = 480
    zoom = img.crop((round(x0), round(y0), round(x0 + side), round(y0 + side))).resize((zoom_px, zoom_px), Image.LANCZOS)
    z = zoom_px / side
    draw_line(zoom, [((x - x0) * z, (y - y0) * z) for x, y in curve], 3)
    # a clean copy of the zoom, so the reviewer can see what is under the line
    clean = img.crop((round(x0), round(y0), round(x0 + side), round(y0 + side))).resize((zoom_px, zoom_px), Image.LANCZOS)
    ImageDraw.Draw(full).rectangle((x0 * scale, y0 * scale, (x0 + side) * scale, (y0 + side) * scale), outline=(255, 255, 255), width=1)
    h = max(full.height, zoom_px) + 36
    canvas = Image.new("RGB", (full.width + 2 * zoom_px + 32, h), (40, 40, 40))
    canvas.paste(full, (8, 36))
    canvas.paste(zoom, (full.width + 16, 36))
    canvas.paste(clean, (full.width + zoom_px + 24, 36))
    d = ImageDraw.Draw(canvas)
    font = _font(20)
    d.text((8, 8), f"{item_id}    full frame", fill=(255, 255, 255), font=font)
    d.text((full.width + 16, 8), "zoom, with the line", fill=(255, 255, 255), font=font)
    d.text((full.width + zoom_px + 24, 8), "same zoom, no line", fill=(255, 255, 255), font=font)
    path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(path, quality=90)


def build_stage_b(clips_by_set: dict[str, list[str]], outputs: dict[str, dict[str, Any]], salt: str) -> dict[str, Any]:
    distinct: dict[tuple[str, int, str], dict[str, Any]] = {}
    frames_key: list[dict[str, Any]] = []
    for set_name, clips in clips_by_set.items():
        for clip in clips:
            files = {f["frame_index"]: f["file"] for f in load_frames_manifest(clip)["frames"]}
            by_method = {m: {f["frame_index"]: f for f in outputs[f"{clip}--{m}"]["frames"]} for m in METHODS}
            for idx in sorted(files):
                entry: dict[str, Any] = {"set": set_name, "clip_id": clip, "frame_index": idx, "methods": {}}
                for m in METHODS:
                    f = by_method[m].get(idx)
                    asserted = bool(f and f["status"] in ("ok", "propagated"))
                    ck = None
                    if asserted and f["curve"]:
                        ck = _curve_key(f["curve"])
                        d = distinct.setdefault((clip, idx, ck), {"clip_id": clip, "frame_index": idx, "file": files[idx], "curve": f["curve"], "methods": []})
                        d["methods"].append(m)
                    entry["methods"][m] = {"asserted": asserted, "status": f["status"] if f else None, "curve_key": ck}
                frames_key.append(entry)
    rng = shuffle_rng(salt)
    order = list(distinct.values())
    rng.shuffle(order)
    repeats = rng.sample(range(len(order)), min(N_REPEATS, len(order)))
    sequence = [("item", i) for i in range(len(order))] + [("repeat", i) for i in repeats]
    rng.shuffle(sequence)
    items: dict[str, Any] = {}
    repeat_of: dict[str, str] = {}
    first_id: dict[int, str] = {}
    # assign ids in presentation order; a repeat points at the id of its original
    pending_repeats = []
    for old in (STAGE_B_WORK / "items").glob("*.jpg"):
        old.unlink()
    for n, (kind, i) in enumerate(sequence, start=1):
        item_id = f"B{n:03d}"
        if kind == "item":
            first_id[i] = item_id
            d = order[i]
            items[item_id] = {"clip_id": d["clip_id"], "frame_index": d["frame_index"], "curve_key": _curve_key(d["curve"]), "methods": d["methods"]}
        else:
            pending_repeats.append((item_id, i))
        STAGE_B_WORK.mkdir(parents=True, exist_ok=True)
        d = order[i]
        _render_item(d["clip_id"], d["file"], d["curve"], item_id, STAGE_B_WORK / "items" / f"{item_id}.jpg")
    for item_id, i in pending_repeats:
        repeat_of[item_id] = first_id[i]
    for f in frames_key:
        for m, rec in f["methods"].items():
            rec["item_id"] = next((k for k, v in items.items() if rec["curve_key"] and v["clip_id"] == f["clip_id"] and v["frame_index"] == f["frame_index"] and v["curve_key"] == rec["curve_key"]), None)
    with (STAGE_B_WORK / "stage-b-TEMPLATE.csv").open("w", newline="", encoding="utf-8") as h:
        w = csv.DictWriter(h, fieldnames=STAGE_B_COLUMNS)
        w.writeheader()
        for n in range(1, len(sequence) + 1):
            w.writerow({"item_id": f"B{n:03d}", "on_tail": "", "note": ""})
    key = {"methods": list(METHODS), "items": items, "repeat_of": repeat_of, "frames": frames_key}
    write_json(STAGE_B_WORK / "key.json", key)
    manifest = {
        "salt": salt,
        "n_items": len(items),
        "n_repeats": len(repeat_of),
        "key_sha256": _sha(STAGE_B_WORK / "key.json"),
        "template_sha256": _sha(STAGE_B_WORK / "stage-b-TEMPLATE.csv"),
        "images": {p.name: _sha(p) for p in sorted((STAGE_B_WORK / "items").glob("*.jpg"))},
        "outputs": {p.name: _sha(p) for p in sorted(OUTPUTS.glob("*.json"))},
    }
    write_json(MANIFEST_PATH, manifest)
    commitment = {
        "note": ("Stage B images are released after every reviewer has locked Stage A. The key, the method outputs "
                 "and the manifest (which holds the shuffle salt) stay private until every reviewer has locked Stage B. "
                 "root_sha256 is the SHA-256 of the canonical manifest; see review/hr1/README.md."),
        "scheme": "sha256(json.dumps(manifest, sort_keys=True, separators=(',', ':')))",
        "n_items": len(items),
        "n_repeats": len(repeat_of),
        "root_sha256": manifest_root(manifest),
    }
    write_json(PACKAGE / "stage_b_commitment.json", commitment)
    return commitment


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the HR1 review package.")
    parser.add_argument("--skip-stage-a", action="store_true")
    args = parser.parse_args()
    clips_by_set = _clips_by_set()
    clips = [c for cs in clips_by_set.values() for c in cs]
    for clip in clips:
        write_json(PACKAGE / "frames" / f"{clip}--frames.json", load_frames_manifest(clip))
    outputs = export_outputs(clips)
    if not args.skip_stage_a:
        rows = build_stage_a(clips_by_set, PACKAGE)
        print(f"stage A: {len(rows)} frames")
    c = build_stage_b(clips_by_set, outputs, load_or_create_salt())
    print(f"stage B: {c['n_items']} items + {c['n_repeats']} repeats (private; root {c['root_sha256'][:12]}... committed)")


if __name__ == "__main__":
    main()
