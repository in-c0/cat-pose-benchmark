"""Run grounded tail v3 = v2 (reach-1 one-sided bridge) + two-sided intersection bridge.

Requires tail_grounded_v1 and tail_grounded_v2 results for the clip. Writes the four
bidirectional variants under v2b_* for inspection and copies the intersection variant to
tail_grounded_v3.
"""

from __future__ import annotations

import argparse
import json
import shutil

from detail.tail_bridge_bidir import run as bidir
from review.common import clip_workdir, frames_dir, load_clips, write_json


def run_clip(clip_id: str, *, device: str, samples: int, max_gap: int) -> dict:
    work = clip_workdir(clip_id)
    for req in ("tail_grounded_v1", "tail_grounded_v2"):
        if not (work / req / "result.json").exists():
            raise FileNotFoundError(f"{work / req} missing; run the earlier stages first")
    bidir(frames_dir=frames_dir(clip_id), v1_json=work / "tail_grounded_v1" / "result.json", v2_json=work / "tail_grounded_v2" / "result.json",
          output_root=work, device=device, sample_count=samples, max_gap=max_gap, tag_prefix="v2b")
    src = work / "v2b_intersection"
    dst = work / "tail_grounded_v3"
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    result = json.loads((dst / "result.json").read_text(encoding="utf-8"))
    result["method"] = "tail_grounded_v3"
    (dst / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True, default=float) + "\n", encoding="utf-8")
    overlay_dir = work / "overlays" / "tail_grounded_v3"
    if overlay_dir.exists():
        shutil.rmtree(overlay_dir)
    if (dst / "overlays").exists():
        shutil.copytree(dst / "overlays", overlay_dir)
    payload = {
        "schema_version": "0.1.0", "clip_id": clip_id, "method": "tail_grounded_v3",
        "composition": "tail_grounded_v1 + one-sided reach-1 bridge (tail_bridge) + two-sided intersection bridge for gaps <= %d (tail_bridge_bidir)" % max_gap,
        "evidence_tier": "S2", "summary": result["summary"],
        "frames": [{k: f.get(k) for k in ("frame_index", "status", "bidir", "iou_lr", "propagated_from")} for f in result["frames"]],
    }
    write_json(work / "tail_grounded_v3.json", payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Grounded tail v3 over review frames.")
    parser.add_argument("--clip", action="append")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--samples", type=int, default=24)
    parser.add_argument("--max-gap", type=int, default=3)
    args = parser.parse_args()
    for clip in load_clips():
        if args.clip and clip["clip_id"] not in args.clip:
            continue
        if not clip.get("review", True):
            continue
        payload = run_clip(clip["clip_id"], device=args.device, samples=args.samples, max_gap=args.max_gap)
        print(json.dumps({"clip_id": clip["clip_id"], **payload["summary"]}))


if __name__ == "__main__":
    main()
