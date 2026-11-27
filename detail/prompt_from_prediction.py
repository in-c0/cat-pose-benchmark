from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


NEGATIVE_CANDIDATES = (
    "nose",
    "neck_base",
    "back_middle",
    "left_hind_paw",
    "right_hind_paw",
    "left_front_paw",
    "right_front_paw",
)


def _name(point: dict[str, Any]) -> str:
    return point.get("canonical_name") or point["native_name"]


def _distance(a: dict[str, Any], b: dict[str, Any]) -> float:
    return math.hypot(float(a["x_px"]) - float(b["x_px"]), float(a["y_px"]) - float(b["y_px"]))


def _frame_points(frame: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {_name(point): point for point in frame.get("keypoints_2d", [])}


def select_tail_prompt(
    prediction: dict[str, Any],
    *,
    source_video: str,
    min_score: float = 0.2,
    min_separation_fraction: float = 0.03,
    negative_clearance_fraction: float = 0.025,
    github_actions_run: int | None = None,
) -> dict[str, Any]:
    width = int(prediction["source"]["width_px"])
    height = int(prediction["source"]["height_px"])
    diagonal = math.hypot(width, height)
    if diagonal <= 0:
        raise ValueError("prediction image diagonal must be positive")

    candidates: list[dict[str, Any]] = []
    for frame in prediction.get("frames", []):
        points = _frame_points(frame)
        base = points.get("tail_base")
        tip = points.get("tail_tip")
        if base is None or tip is None:
            continue
        base_score = float(base.get("score", 0.0))
        tip_score = float(tip.get("score", 0.0))
        separation_fraction = _distance(base, tip) / diagonal
        eligible = (
            base_score >= min_score
            and tip_score >= min_score
            and separation_fraction >= min_separation_fraction
        )
        candidates.append(
            {
                "frame_index": int(frame["frame_index"]),
                "timestamp_s": float(frame["timestamp_s"]),
                "tail_base_score": base_score,
                "tail_tip_score": tip_score,
                "minimum_endpoint_score": min(base_score, tip_score),
                "endpoint_separation_fraction": separation_fraction,
                "eligible": eligible,
            }
        )

    eligible_candidates = [candidate for candidate in candidates if candidate["eligible"]]
    if not eligible_candidates:
        raise ValueError(
            "No frame has both tail endpoints above the confidence/separation gate"
        )

    # Confidence is primary; separation breaks ties and discourages collapsed endpoints.
    selected = max(
        eligible_candidates,
        key=lambda candidate: (
            candidate["minimum_endpoint_score"],
            candidate["endpoint_separation_fraction"],
        ),
    )
    frame = next(
        frame
        for frame in prediction["frames"]
        if int(frame["frame_index"]) == selected["frame_index"]
    )
    points = _frame_points(frame)
    base = points["tail_base"]
    tip = points["tail_tip"]

    negatives = []
    clearance_px = negative_clearance_fraction * diagonal
    for name in NEGATIVE_CANDIDATES:
        point = points.get(name)
        if point is None or float(point.get("score", 0.0)) < min_score:
            continue
        if min(_distance(point, base), _distance(point, tip)) < clearance_px:
            continue
        negatives.append(
            {
                "semantic_name": name,
                "x_px": float(point["x_px"]),
                "y_px": float(point["y_px"]),
                "score": float(point.get("score", 0.0)),
            }
        )

    if len(negatives) < 2:
        raise ValueError(
            f"Selected tail frame has only {len(negatives)} usable negative body prompts"
        )

    model = prediction["model"]
    prompt = {
        "schema_version": "0.1.0",
        "clip_id": prediction["clip_id"],
        "source_video": source_video,
        "source_frame": {
            "smoke_frame_index": selected["frame_index"],
            "timestamp_s": selected["timestamp_s"],
            "width_px": width,
            "height_px": height,
        },
        "selection": {
            "method": "max_min_tail_endpoint_confidence_with_separation_gate_v0",
            "min_score": min_score,
            "min_separation_fraction": min_separation_fraction,
            "negative_clearance_fraction": negative_clearance_fraction,
            "selected": selected,
            "all_tail_endpoint_candidates": candidates,
        },
        "prompt_provenance": {
            "evidence_tier": "R3",
            "model": model["id"],
            "model_version": model["version"],
            "checkpoint": model["checkpoint"],
            "checkpoint_status": model["commercial_status"],
            "github_actions_run": github_actions_run,
            "derived_data_status": "research_only_until_issue_9_review",
            "note": (
                "Prompts are selected automatically from model predictions. They are "
                "not manual labels or independent ground truth."
            ),
        },
        "positive_points": [
            {
                "semantic_name": "tail_base",
                "x_px": float(base["x_px"]),
                "y_px": float(base["y_px"]),
                "score": float(base.get("score", 0.0)),
            },
            {
                "semantic_name": "tail_tip",
                "x_px": float(tip["x_px"]),
                "y_px": float(tip["y_px"]),
                "score": float(tip.get("score", 0.0)),
            },
        ],
        "negative_points": negatives,
        "segmentation_model": {
            "repository": "facebookresearch/sam2",
            "checkpoint": "facebook/sam2.1-hiera-tiny",
            "code_license": "Apache-2.0",
            "checkpoint_license": "Apache-2.0",
        },
        "scientific_boundary": (
            "Automatic teacher prompts and resulting SAM2 masks/curves are R3 "
            "model-derived research evidence, not observed truth or cleared product "
            "training labels."
        ),
    }
    return prompt


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Select a tail frame and SAM2 point prompts from canonical predictions."
    )
    parser.add_argument("prediction", type=Path)
    parser.add_argument("--source-video", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--min-score", type=float, default=0.2)
    parser.add_argument("--min-separation-fraction", type=float, default=0.03)
    parser.add_argument("--negative-clearance-fraction", type=float, default=0.025)
    parser.add_argument("--github-actions-run", type=int)
    args = parser.parse_args()

    prediction = json.loads(args.prediction.read_text(encoding="utf-8"))
    prompt = select_tail_prompt(
        prediction,
        source_video=args.source_video,
        min_score=args.min_score,
        min_separation_fraction=args.min_separation_fraction,
        negative_clearance_fraction=args.negative_clearance_fraction,
        github_actions_run=args.github_actions_run,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(prompt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(prompt, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
