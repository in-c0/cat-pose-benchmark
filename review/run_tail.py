"""Propagate the existing SAM2 tail seed through the review frames of each clip.

Reuses detail.sam2_tail_video unchanged. The seed fixtures were authored against the
smoke-test sampling, so the only thing this module adds is a derived prompt whose
seed index points at the equivalent frame in the review sampling; the point coordinates
and provenance are copied verbatim and the derivation is recorded.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any

from detail.sam2_tail_video import run as propagate
from review.common import REPO_ROOT, clip_workdir, frames_dir, load_clips, load_frames_manifest, write_json


def derive_prompt(clip: dict[str, Any], *, root: Path = REPO_ROOT) -> Path:
    seed = clip["tail_seed"]
    fixture_path = root / seed["fixture"]
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    manifest = load_frames_manifest(clip["clip_id"])
    review_index = int(seed["review_frame_index"])
    frame = next(f for f in manifest["frames"] if f["frame_index"] == review_index)

    derived = dict(fixture)
    derived["source_frame"] = {
        "smoke_frame_index": review_index,
        "timestamp_s": frame["timestamp_s"],
        "width_px": frame["width_px"],
        "height_px": frame["height_px"],
    }
    derived["derived_from"] = {
        "fixture": seed["fixture"],
        "fixture_frame_index": fixture["source_frame"]["smoke_frame_index"],
        "fixture_timestamp_s": fixture["source_frame"]["timestamp_s"],
        "note": "Point coordinates unchanged; only the seed frame index is re-mapped to the review sampling.",
    }
    out = clip_workdir(clip["clip_id"]) / "tail-prompt.json"
    write_json(out, derived)
    return out


def run_clip(clip: dict[str, Any], *, checkpoint: str, device: str, samples: int) -> dict[str, Any]:
    clip_id = clip["clip_id"]
    prompt_path = derive_prompt(clip)
    out_dir = clip_workdir(clip_id) / "tail"
    if out_dir.exists():
        shutil.rmtree(out_dir)
    result = propagate(
        frames_dir=frames_dir(clip_id),
        prompt_path=prompt_path,
        output_dir=out_dir,
        checkpoint=checkpoint,
        device=device,
        sample_count=samples,
    )
    # Mirror the per-frame overlays next to the body overlays so the sheet builder has
    # one layout for both methods.
    overlay_dir = clip_workdir(clip_id) / "overlays" / "tail"
    if overlay_dir.exists():
        shutil.rmtree(overlay_dir)
    shutil.copytree(out_dir / "overlays", overlay_dir)

    payload = {
        "schema_version": "0.1.0",
        "clip_id": clip_id,
        "method": "tail",
        "model": {"checkpoint": checkpoint, "device": device, "prompt": str(prompt_path.relative_to(REPO_ROOT))},
        "evidence_tier": "S2",
        "summary": result["summary"],
        "frames": [
            {
                "frame_index": int(f["frame_index"]),
                "curve_status": f["curve_status"],
                "mask_area_fraction": f["mask_area_fraction"],
                "curve_length_px": f.get("curve_length_px"),
            }
            for f in result["frames"]
        ],
    }
    write_json(clip_workdir(clip_id) / "tail.json", payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Propagate SAM2 tail seeds through the review frames.")
    parser.add_argument("--clip", action="append")
    parser.add_argument("--checkpoint", default="facebook/sam2.1-hiera-tiny")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--samples", type=int, default=24)
    args = parser.parse_args()
    for clip in load_clips():
        if args.clip and clip["clip_id"] not in args.clip:
            continue
        if "tail_seed" not in clip:
            print(json.dumps({"clip_id": clip["clip_id"], "skipped": "no tail_seed"}))
            continue
        payload = run_clip(clip, checkpoint=args.checkpoint, device=args.device, samples=args.samples)
        print(json.dumps({"clip_id": clip["clip_id"], **payload["summary"]}, default=str))


if __name__ == "__main__":
    main()
