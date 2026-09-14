"""Run grounded tail v1 (zoom + crop check + temporal) over the review frames."""

from __future__ import annotations

import argparse
import json
import shutil

from detail.grounded_tail_v1 import run as grounded_v1
from review.common import clip_workdir, frames_dir, frames_manifest_path, load_clips, write_json


def run_clip(clip_id: str, *, device: str, samples: int, zoom: bool, crop_check: bool, temporal: bool, tag: str = "tail_grounded_v1") -> dict:
    work = clip_workdir(clip_id)
    out_dir = work / tag
    if out_dir.exists():
        shutil.rmtree(out_dir)
    body_json = work / "body.json"
    result = grounded_v1(
        frames_dir=frames_dir(clip_id),
        frames_manifest=frames_manifest_path(clip_id),
        output_dir=out_dir,
        body_json=body_json if body_json.exists() else None,
        device=device,
        sample_count=samples,
        clip_id=clip_id,
        zoom=zoom,
        crop_check=crop_check,
        temporal=temporal,
    )
    overlay_dir = work / "overlays" / tag
    if overlay_dir.exists():
        shutil.rmtree(overlay_dir)
    if (out_dir / "overlays").exists():
        shutil.copytree(out_dir / "overlays", overlay_dir)
    payload = {
        "schema_version": "0.1.0",
        "clip_id": clip_id,
        "method": tag,
        "models": result["models"],
        "options": result["options"],
        "evidence_tier": "S2",
        "summary": result["summary"],
        "frames": [
            {
                "frame_index": f["frame_index"],
                "status": f["status"],
                "n_candidates": f.get("n_candidates"),
                "n_after_crop_check": f.get("n_after_crop_check"),
                "tail_score": f["tail"]["score"] if f.get("tail") else None,
                "crop_probs": f["tail"].get("crop_probs") if f.get("tail") else None,
            }
            for f in result["frames"]
        ],
    }
    write_json(work / f"{tag}.json", payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Grounded tail v1 over review frames.")
    parser.add_argument("--clip", action="append")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--samples", type=int, default=24)
    parser.add_argument("--zoom", action="store_true")
    parser.add_argument("--no-crop-check", action="store_true")
    parser.add_argument("--no-temporal", action="store_true")
    parser.add_argument("--tag", default="tail_grounded_v1", help="output method name (for ablations)")
    args = parser.parse_args()
    for clip in load_clips():
        if args.clip and clip["clip_id"] not in args.clip:
            continue
        payload = run_clip(
            clip["clip_id"], device=args.device, samples=args.samples,
            zoom=args.zoom, crop_check=not args.no_crop_check, temporal=not args.no_temporal, tag=args.tag,
        )
        print(json.dumps({"clip_id": clip["clip_id"], **payload["summary"]}))


if __name__ == "__main__":
    main()
