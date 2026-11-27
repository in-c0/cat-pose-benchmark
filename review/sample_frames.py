"""Extract the fixed review frame set for every clip in review/clips.json."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from PIL import Image

from bakeoff.materialize_clip import materialize
from review.common import (
    REPO_ROOT,
    frames_dir,
    frames_manifest_path,
    load_clips,
    sha256_file,
    write_json,
)


def _ffmpeg() -> str:
    import imageio_ffmpeg

    return imageio_ffmpeg.get_ffmpeg_exe()


def sample_clip(clip: dict[str, Any], *, root: Path = REPO_ROOT) -> dict[str, Any]:
    manifest = json.loads((root / clip["manifest"]).read_text(encoding="utf-8"))
    media_path, media_sha = materialize(manifest, root=root)

    out_dir = frames_dir(clip["clip_id"])
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)

    fps = float(clip["sample_fps"])
    max_seconds = float(clip["max_seconds"])
    subprocess.run(
        [
            _ffmpeg(),
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(media_path),
            "-t",
            f"{max_seconds}",
            "-vf",
            f"fps={fps}",
            "-an",
            "-q:v",
            "2",
            "-start_number",
            "0",
            str(out_dir / "%05d.jpg"),
        ],
        check=True,
    )

    frames = []
    for path in sorted(out_dir.glob("*.jpg"), key=lambda p: int(p.stem)):
        index = int(path.stem)
        with Image.open(path) as image:
            width, height = image.size
        frames.append(
            {
                "frame_index": index,
                "file": path.name,
                "timestamp_s": index / fps,
                "width_px": width,
                "height_px": height,
                "sha256": sha256_file(path),
            }
        )

    seed = clip.get("tail_seed")
    if seed:
        seed_index = int(seed["review_frame_index"])
        expected = float(seed["fixture_timestamp_s"])
        actual = seed_index / fps
        if abs(actual - expected) > 1e-6:
            raise ValueError(
                f"{clip['clip_id']}: tail seed fixture is at {expected:.4f}s but review "
                f"frame {seed_index} at {fps} fps is {actual:.4f}s"
            )

    payload = {
        "schema_version": "0.1.0",
        "clip_id": clip["clip_id"],
        "source": {
            "manifest": clip["manifest"],
            "media_path": str(media_path.relative_to(root)),
            "media_sha256": media_sha,
            "licence": manifest["licence"]["identifier"],
        },
        "sampling": {"fps": fps, "max_seconds": max_seconds},
        "frame_count": len(frames),
        "frames": frames,
    }
    write_json(frames_manifest_path(clip["clip_id"]), payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Sample review frames from the licence-approved clips.")
    parser.add_argument("--clip", action="append", help="Restrict to one clip_id (repeatable).")
    args = parser.parse_args()

    for clip in load_clips():
        if args.clip and clip["clip_id"] not in args.clip:
            continue
        payload = sample_clip(clip)
        print(json.dumps({"clip_id": payload["clip_id"], "frame_count": payload["frame_count"]}))


if __name__ == "__main__":
    main()
