"""Write the empty verdict sheet a reviewer fills in: one row per clip x frame x part."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any

from review.common import METHOD_FOR_PART, PARTS, load_clips, load_frames_manifest

COLUMNS = [
    "clip_id",
    "frame_index",
    "timestamp_s",
    "part",
    "method",
    "verdict",
    "condition",
    "note",
]


def rows_for_clip(clip: dict[str, Any], manifest: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for frame in manifest["frames"]:
        for part in PARTS:
            method = METHOD_FOR_PART[part]
            if method == "tail" and "tail_seed" not in clip:
                continue
            rows.append(
                {
                    "clip_id": clip["clip_id"],
                    "frame_index": frame["frame_index"],
                    "timestamp_s": f"{frame['timestamp_s']:.4f}",
                    "part": part,
                    "method": method,
                    "verdict": "",
                    "condition": "",
                    "note": "",
                }
            )
    return rows


def write_template(path: Path, clips: list[dict[str, Any]], manifests: dict[str, dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        for clip in clips:
            for row in rows_for_clip(clip, manifests[clip["clip_id"]]):
                writer.writerow(row)
                count += 1
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description="Write the empty review CSV.")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--clip", action="append")
    args = parser.parse_args()

    clips = [c for c in load_clips() if not args.clip or c["clip_id"] in args.clip]
    manifests = {c["clip_id"]: load_frames_manifest(c["clip_id"]) for c in clips}
    count = write_template(args.output, clips, manifests)
    print(f"{count} rows -> {args.output}")


if __name__ == "__main__":
    main()
