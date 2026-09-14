"""Run the text-grounded tail method (Grounding DINO + SAM2) over the review frames."""

from __future__ import annotations

import argparse
import json
import shutil

from detail.grounded_tail import run as grounded
from review.common import clip_workdir, frames_dir, frames_manifest_path, load_clips, write_json


def run_clip(clip_id: str, *, device: str, samples: int) -> dict:
    work = clip_workdir(clip_id)
    out_dir = work / "tail_grounded"
    if out_dir.exists():
        shutil.rmtree(out_dir)
    body_json = work / "body.json"
    result = grounded(
        frames_dir=frames_dir(clip_id),
        frames_manifest=frames_manifest_path(clip_id),
        output_dir=out_dir,
        body_json=body_json if body_json.exists() else None,
        device=device,
        sample_count=samples,
        clip_id=clip_id,
    )
    overlay_dir = work / "overlays" / "tail_grounded"
    if overlay_dir.exists():
        shutil.rmtree(overlay_dir)
    if (out_dir / "overlays").exists():
        shutil.copytree(out_dir / "overlays", overlay_dir)
    payload = {
        "schema_version": "0.1.0",
        "clip_id": clip_id,
        "method": "tail_grounded",
        "models": result["models"],
        "selection": result["selection"],
        "evidence_tier": "S2",
        "summary": result["summary"],
        "frames": [
            {
                "frame_index": f["frame_index"],
                "status": f["status"],
                "tail_score": f["tail"]["score"] if f.get("tail") else None,
                "limb_keypoints_inside": f.get("limb_keypoints_inside"),
                "cat_score": f["cat"]["score"] if f.get("cat") else None,
            }
            for f in result["frames"]
        ],
    }
    write_json(work / "tail_grounded.json", payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Text-grounded tail over review frames.")
    parser.add_argument("--clip", action="append")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--samples", type=int, default=24)
    args = parser.parse_args()
    for clip in load_clips():
        if args.clip and clip["clip_id"] not in args.clip:
            continue
        payload = run_clip(clip["clip_id"], device=args.device, samples=args.samples)
        print(json.dumps({"clip_id": clip["clip_id"], **payload["summary"]}))


if __name__ == "__main__":
    main()
