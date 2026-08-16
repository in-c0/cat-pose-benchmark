from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

from temporal.appearance_assignment import (
    _candidate_costs,
    _crop_histogram,
    _frame_path,
)


def _expand_bbox(bbox: list[float], fraction: float) -> list[float]:
    left, top, right, bottom = [float(value) for value in bbox]
    width = max(1.0, right - left)
    height = max(1.0, bottom - top)
    return [
        left - fraction * width,
        top - fraction * height,
        right + fraction * width,
        bottom + fraction * height,
    ]


def select_seed(
    multi_candidates: dict[str, Any], *, rule: str = "first_two_candidate_frame_leftmost"
) -> tuple[int, dict[str, Any]]:
    if rule != "first_two_candidate_frame_leftmost":
        raise ValueError(f"unsupported seed rule: {rule}")
    for frame in multi_candidates.get("frames", []):
        candidates = frame.get("candidates", [])
        if len(candidates) < 2:
            continue
        chosen = min(
            candidates,
            key=lambda candidate: (
                float(candidate["centroid_xy"][0]),
                float(candidate["centroid_xy"][1]),
                candidate["individual"],
            ),
        )
        return int(frame["frame_index"]), chosen
    raise ValueError("no frame contains two candidates; held-out seed rule cannot be applied")


def evaluate_heldout(
    multi_candidates: dict[str, Any],
    *,
    frames_dir: Path,
    appearance_threshold: float,
    clip_id: str,
    histogram_bins: int = 8,
    seed_padding_fraction: float = 0.05,
    seed_rule: str = "first_two_candidate_frame_leftmost",
) -> dict[str, Any]:
    """Evaluate a frozen appearance gate on an independent multi-cat clip.

    The target identity is defined without manual annotation: the leftmost candidate in
    the first frame where at least two animal candidates exist. The appearance threshold
    is supplied externally and must remain frozen for held-out evaluation.
    """

    if not clip_id:
        raise ValueError("clip_id is required")
    seed_frame_index, seed_candidate = select_seed(multi_candidates, rule=seed_rule)
    seed_image = Image.open(_frame_path(frames_dir, seed_frame_index)).convert("RGB")
    seed_bbox = _expand_bbox(seed_candidate["bbox_xyxy"], seed_padding_fraction)
    reference_histogram = _crop_histogram(seed_image, seed_bbox, bins=histogram_bins)

    output_frames: list[dict[str, Any]] = []
    previous_state = "target"
    for frame in multi_candidates.get("frames", []):
        frame_index = int(frame["frame_index"])
        if frame_index < seed_frame_index:
            continue
        image = Image.open(_frame_path(frames_dir, frame_index)).convert("RGB")
        costs = _candidate_costs(
            frame,
            image=image,
            reference_histogram=reference_histogram,
            bins=histogram_bins,
        )
        accepted = (
            costs[0]
            if costs and float(costs[0]["appearance_jsd"]) <= appearance_threshold
            else None
        )
        if accepted is None:
            state = "lost"
            transition = "lost" if previous_state != "lost" else "remain_lost"
        else:
            state = "target"
            transition = "reacquired" if previous_state == "lost" else "tracked"

        output_frames.append(
            {
                "frame_index": frame_index,
                "candidate_count": len(costs),
                "state": state,
                "transition": transition,
                "selected_candidate": accepted,
                "candidate_costs": costs,
            }
        )
        previous_state = state

    target_frames = [frame["frame_index"] for frame in output_frames if frame["state"] == "target"]
    lost_frames = [frame["frame_index"] for frame in output_frames if frame["state"] == "lost"]
    reacquired_frames = [
        frame["frame_index"]
        for frame in output_frames
        if frame["transition"] == "reacquired"
    ]
    selected_jsd = [
        float(frame["selected_candidate"]["appearance_jsd"])
        for frame in output_frames
        if frame["selected_candidate"] is not None
    ]
    rejected_best_jsd = [
        float(frame["candidate_costs"][0]["appearance_jsd"])
        for frame in output_frames
        if frame["selected_candidate"] is None and frame["candidate_costs"]
    ]

    return {
        "schema_version": "0.1.0",
        "clip_id": clip_id,
        "evidence_tier": "R3",
        "protocol": {
            "held_out": True,
            "threshold_tuned_on_this_clip": False,
            "appearance_threshold": appearance_threshold,
            "histogram_bins": histogram_bins,
            "seed_padding_fraction": seed_padding_fraction,
            "seed_rule": seed_rule,
            "target_definition": (
                "leftmost animal candidate in the first frame with at least two candidates"
            ),
        },
        "seed": {
            "frame_index": seed_frame_index,
            "individual_slot": seed_candidate["individual"],
            "bbox_xyxy": seed_candidate["bbox_xyxy"],
            "centroid_xy": seed_candidate["centroid_xy"],
            "reference_bbox_xyxy": seed_bbox,
        },
        "frames": output_frames,
        "summary": {
            "frames_evaluated": len(output_frames),
            "target_frames": target_frames,
            "lost_frames": lost_frames,
            "reacquired_frames": reacquired_frames,
            "target_fraction": len(target_frames) / len(output_frames) if output_frames else 0.0,
            "lost_fraction": len(lost_frames) / len(output_frames) if output_frames else 0.0,
            "max_selected_jsd": max(selected_jsd) if selected_jsd else None,
            "min_rejected_best_jsd": min(rejected_best_jsd) if rejected_best_jsd else None,
            "interpretation_boundary": (
                "Held-out threshold behavior is quantitative, but physical identity correctness "
                "still requires visual review because candidate slots are not ground-truth identities."
            ),
        },
        "scientific_boundary": (
            "SuperAnimal candidates remain research-only R3 outputs. The deterministic seed rule "
            "avoids manual target selection, but this evaluation does not create independent identity labels."
        ),
    }


def render_overlays(
    result: dict[str, Any], *, frames_dir: Path, output_dir: Path
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for frame in result["frames"]:
        image = Image.open(_frame_path(frames_dir, int(frame["frame_index"]))).convert("RGB")
        draw = ImageDraw.Draw(image)
        for candidate in frame["candidate_costs"]:
            left, top, right, bottom = candidate["bbox_xyxy"]
            selected = (
                frame["selected_candidate"] is not None
                and candidate["candidate_index"]
                == frame["selected_candidate"]["candidate_index"]
            )
            draw.rectangle(
                (left, top, right, bottom), outline="red", width=6 if selected else 2
            )
            label = (
                f"c{candidate['candidate_index']} JSD={candidate['appearance_jsd']:.3f} "
                f"{'SELECT' if selected else ''}"
            )
            draw.rectangle(
                (left, max(0, top - 22), min(image.width - 1, left + 235), top),
                fill="black",
            )
            draw.text((left + 3, max(0, top - 19)), label, fill="white")
        state = f"{frame['frame_index']:02d}s | {frame['state']} | {frame['transition']}"
        draw.rectangle((5, 5, 290, 32), fill="black")
        draw.text((10, 10), state, fill="white")
        image.save(output_dir / f"{int(frame['frame_index']):05d}.jpg", quality=92)


def make_contact_sheets(
    overlays_dir: Path, output_dir: Path, *, per_sheet: int = 20, columns: int = 5
) -> None:
    paths = sorted(overlays_dir.glob("*.jpg"))
    if not paths:
        return
    output_dir.mkdir(parents=True, exist_ok=True)
    first = Image.open(paths[0]).convert("RGB")
    thumb_width = 320
    thumb_height = round(thumb_width * first.height / first.width)
    for sheet_index, start in enumerate(range(0, len(paths), per_sheet)):
        subset = paths[start : start + per_sheet]
        rows = math.ceil(len(subset) / columns)
        sheet = Image.new("RGB", (columns * thumb_width, rows * thumb_height), "black")
        for offset, path in enumerate(subset):
            image = Image.open(path).convert("RGB").resize((thumb_width, thumb_height))
            sheet.paste(
                image,
                ((offset % columns) * thumb_width, (offset // columns) * thumb_height),
            )
        sheet.save(output_dir / f"assignment-sheet-{sheet_index}.jpg", quality=92)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate the frozen appearance gate on an independent multi-cat clip."
    )
    parser.add_argument("multi_candidates", type=Path)
    parser.add_argument("frames_dir", type=Path)
    parser.add_argument("--clip-id", required=True)
    parser.add_argument("--appearance-threshold", type=float, default=0.30)
    parser.add_argument("--histogram-bins", type=int, default=8)
    parser.add_argument("--seed-padding-fraction", type=float, default=0.05)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--overlays-dir", type=Path)
    parser.add_argument("--contact-sheet-dir", type=Path)
    args = parser.parse_args()

    result = evaluate_heldout(
        json.loads(args.multi_candidates.read_text(encoding="utf-8")),
        frames_dir=args.frames_dir,
        appearance_threshold=args.appearance_threshold,
        clip_id=args.clip_id,
        histogram_bins=args.histogram_bins,
        seed_padding_fraction=args.seed_padding_fraction,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    if args.overlays_dir:
        render_overlays(result, frames_dir=args.frames_dir, output_dir=args.overlays_dir)
        if args.contact_sheet_dir:
            make_contact_sheets(args.overlays_dir, args.contact_sheet_dir)
    print(json.dumps(result["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
