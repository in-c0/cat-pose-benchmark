"""Run grounded tail v2 = v1 result + SAM2 bridging of short gaps."""

from __future__ import annotations

import argparse
import json
import shutil

from detail.tail_bridge import run as bridge
from review.common import clip_workdir, frames_dir, load_clips, write_json


def run_clip(clip_id: str, *, device: str, samples: int, max_reach: int) -> dict:
    work = clip_workdir(clip_id)
    source = work / "tail_grounded_v1" / "result.json"
    if not source.exists():
        raise FileNotFoundError(f"{source} missing; run review.run_tail_grounded_v1 first")
    out_dir = work / "tail_grounded_v2"
    if out_dir.exists():
        shutil.rmtree(out_dir)
    result = bridge(frames_dir=frames_dir(clip_id), result_json=source, output_dir=out_dir, device=device, sample_count=samples, max_reach=max_reach)
    overlay_dir = work / "overlays" / "tail_grounded_v2"
    if overlay_dir.exists():
        shutil.rmtree(overlay_dir)
    if (out_dir / "overlays").exists():
        shutil.copytree(out_dir / "overlays", overlay_dir)
    payload = {
        "schema_version": "0.1.0",
        "clip_id": clip_id,
        "method": "tail_grounded_v2",
        "source_method": result["source_method"],
        "bridge": result["bridge"],
        "evidence_tier": "S2",
        "summary": result["summary"],
        "frames": [
            {k: f.get(k) for k in ("frame_index", "status", "propagated_from", "propagated_distance", "propagated_area_ratio")}
            for f in result["frames"]
        ],
    }
    write_json(work / "tail_grounded_v2.json", payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Grounded tail v2 (v1 + bridging) over review frames.")
    parser.add_argument("--clip", action="append")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--samples", type=int, default=24)
    parser.add_argument("--max-reach", type=int, default=1)
    args = parser.parse_args()
    for clip in load_clips():
        if args.clip and clip["clip_id"] not in args.clip:
            continue
        payload = run_clip(clip["clip_id"], device=args.device, samples=args.samples, max_reach=args.max_reach)
        print(json.dumps({"clip_id": clip["clip_id"], **payload["summary"]}))


if __name__ == "__main__":
    main()
