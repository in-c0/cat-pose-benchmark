"""Run the keypoint-anchored per-frame tail method over the review frames."""

from __future__ import annotations

import argparse
import json
import shutil

from detail.anchored_tail import run as anchored
from review.common import clip_workdir, frames_dir, load_clips, write_json


def run_clip(clip_id: str, *, checkpoint: str, device: str, samples: int) -> dict:
    work = clip_workdir(clip_id)
    body_json = work / "body.json"
    if not body_json.exists():
        raise FileNotFoundError(f"{body_json} missing; run review.run_body first")
    out_dir = work / "tail_anchored"
    if out_dir.exists():
        shutil.rmtree(out_dir)
    result = anchored(
        frames_dir=frames_dir(clip_id),
        body_json=body_json,
        output_dir=out_dir,
        checkpoint=checkpoint,
        device=device,
        sample_count=samples,
        clip_id=clip_id,
    )
    overlay_dir = work / "overlays" / "tail_anchored"
    if overlay_dir.exists():
        shutil.rmtree(overlay_dir)
    if (out_dir / "overlays").exists():
        shutil.copytree(out_dir / "overlays", overlay_dir)
    payload = {
        "schema_version": "0.1.0",
        "clip_id": clip_id,
        "method": "tail_anchored",
        "model": {"checkpoint": checkpoint, "device": device, "anchors": "review/work/<clip>/body.json"},
        "rules": result["rules"],
        "evidence_tier": "S2",
        "summary": result["summary"],
        "frames": [
            {k: f.get(k) for k in ("frame_index", "status", "rejection_reasons", "chosen", "curve_length_px")}
            for f in result["frames"]
        ],
    }
    write_json(work / "tail_anchored.json", payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Anchored per-frame SAM2 tail over review frames.")
    parser.add_argument("--clip", action="append")
    parser.add_argument("--checkpoint", default="facebook/sam2.1-hiera-tiny")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--samples", type=int, default=24)
    args = parser.parse_args()
    for clip in load_clips():
        if args.clip and clip["clip_id"] not in args.clip:
            continue
        payload = run_clip(clip["clip_id"], checkpoint=args.checkpoint, device=args.device, samples=args.samples)
        print(json.dumps({"clip_id": clip["clip_id"], **payload["summary"]}))


if __name__ == "__main__":
    main()
