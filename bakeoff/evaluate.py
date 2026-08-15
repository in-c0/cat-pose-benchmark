from __future__ import annotations

import argparse
import json
import math
import statistics
from pathlib import Path
from typing import Any


def _name(point: dict[str, Any]) -> str:
    canonical = point.get("canonical_name")
    return canonical if canonical else point["native_name"]


def _point2(point: dict[str, Any]) -> tuple[float, float]:
    return float(point["x_px"]), float(point["y_px"])


def _point3(point: dict[str, Any]) -> tuple[float, float, float]:
    return float(point["x"]), float(point["y"]), float(point["z"])


def _distance3(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def _frame_map(
    frame: dict[str, Any], key: str, confidence: float
) -> dict[str, dict[str, Any]]:
    mapped: dict[str, dict[str, Any]] = {}
    for point in frame.get(key, []):
        score = float(point.get("score", 1.0))
        if score >= confidence:
            mapped[_name(point)] = point
    return mapped


def _false_runs(values: list[bool]) -> list[tuple[int, bool, bool]]:
    runs: list[tuple[int, bool, bool]] = []
    index = 0
    while index < len(values):
        if values[index]:
            index += 1
            continue
        start = index
        while index < len(values) and not values[index]:
            index += 1
        runs.append(
            (
                index - start,
                start > 0 and values[start - 1],
                index < len(values) and values[index],
            )
        )
    return runs


def _topology_metrics(
    frames_2d: list[dict[str, dict[str, Any]]],
    requirements: dict[str, Any] | None,
) -> dict[str, Any]:
    if not requirements:
        return {}

    present = set().union(*(set(frame) for frame in frames_2d)) if frames_2d else set()
    groups: dict[str, Any] = {}
    for group, names_value in requirements.get("required_groups", {}).items():
        names = list(names_value)
        hits = sorted(set(names) & present)
        groups[group] = {
            "present": hits,
            "missing": sorted(set(names) - present),
            "coverage": (len(hits) / len(names)) if names else 1.0,
        }

    tail_names = requirements.get("required_groups", {}).get("tail", [])
    tail_count = len(set(tail_names) & present)
    minimum_tail = int(requirements.get("minimum_tail_points_for_curve", 3))
    groups["tail_curve_capability"] = {
        "points_present": tail_count,
        "minimum_required": minimum_tail,
        "satisfied": tail_count >= minimum_tail,
    }
    return groups


def evaluate(
    prediction: dict[str, Any],
    requirements: dict[str, Any] | None = None,
    *,
    confidence: float = 0.2,
    acceleration_spike_threshold: float = 0.03,
) -> dict[str, Any]:
    """Compute model-neutral failure-discovery metrics for one prediction sequence."""

    frames = prediction.get("frames", [])
    if not frames:
        raise ValueError("prediction contains no frames")

    width = int(prediction["source"]["width_px"])
    height = int(prediction["source"]["height_px"])
    image_diagonal = math.hypot(width, height)
    if image_diagonal <= 0:
        raise ValueError("source image diagonal must be positive")

    indices = [int(frame["frame_index"]) for frame in frames]
    if indices != list(range(indices[0], indices[0] + len(indices))):
        raise ValueError("frame_index values must be contiguous")

    frame_maps_2d = [
        _frame_map(frame, "keypoints_2d", confidence) for frame in frames
    ]
    frame_maps_3d = [
        _frame_map(frame, "keypoints_3d", confidence) for frame in frames
    ]

    keypoint_names = sorted(set().union(*(set(frame) for frame in frame_maps_2d)))
    coverage_by_keypoint: dict[str, float] = {}
    dropout: dict[str, Any] = {}
    second_differences: list[float] = []
    spike_count = 0
    second_difference_count = 0

    for name in keypoint_names:
        visible = [name in frame for frame in frame_maps_2d]
        coverage_by_keypoint[name] = sum(visible) / len(visible)
        runs = _false_runs(visible)
        bounded = [length for length, left, right in runs if left and right]
        dropout[name] = {
            "dropout_runs": len(runs),
            "bounded_recoveries": len(bounded),
            "max_dropout_frames": max((length for length, _, _ in runs), default=0),
            "mean_bounded_recovery_frames": (
                statistics.fmean(bounded) if bounded else 0.0
            ),
        }

        for index in range(1, len(frames) - 1):
            previous = frame_maps_2d[index - 1]
            current = frame_maps_2d[index]
            following = frame_maps_2d[index + 1]
            if name not in previous or name not in current or name not in following:
                continue

            p0 = _point2(previous[name])
            p1 = _point2(current[name])
            p2 = _point2(following[name])
            dx = p2[0] - 2.0 * p1[0] + p0[0]
            dy = p2[1] - 2.0 * p1[1] + p0[1]
            normalized_second_difference = math.hypot(dx, dy) / image_diagonal
            second_differences.append(normalized_second_difference)
            second_difference_count += 1
            if normalized_second_difference > acceleration_spike_threshold:
                spike_count += 1

    total_expected = len(keypoint_names) * len(frames)
    total_present = sum(len(frame) for frame in frame_maps_2d)

    inference_ms = [float(frame.get("inference_ms", 0.0)) for frame in frames]
    mean_inference_ms = statistics.fmean(inference_ms)
    sorted_inference = sorted(inference_ms)
    p95_index = max(0, math.ceil(0.95 * len(sorted_inference)) - 1)

    bone_metrics: dict[str, Any] = {}
    for edge in prediction.get("skeleton_edges_3d", []):
        if len(edge) != 2:
            continue
        first_name, second_name = edge
        lengths: list[float] = []
        for frame in frame_maps_3d:
            if first_name not in frame or second_name not in frame:
                continue
            first = frame[first_name]
            second = frame[second_name]
            if first["coordinate_frame"] != second["coordinate_frame"]:
                continue
            lengths.append(_distance3(_point3(first), _point3(second)))

        edge_id = f"{first_name}--{second_name}"
        if lengths:
            mean_length = statistics.fmean(lengths)
            bone_metrics[edge_id] = {
                "samples": len(lengths),
                "mean_length": mean_length,
                "coefficient_of_variation": (
                    statistics.pstdev(lengths) / mean_length
                    if len(lengths) > 1 and mean_length > 0
                    else 0.0
                ),
            }
        else:
            bone_metrics[edge_id] = {
                "samples": 0,
                "mean_length": None,
                "coefficient_of_variation": None,
            }

    depth_flip_metrics: dict[str, Any] = {}
    for pair in prediction.get("diagnostic_depth_pairs", []):
        if len(pair) != 2:
            continue
        first_name, second_name = pair
        previous_sign = 0
        flips = 0
        samples = 0
        for frame in frame_maps_3d:
            if first_name not in frame or second_name not in frame:
                continue
            first = frame[first_name]
            second = frame[second_name]
            if first["coordinate_frame"] != second["coordinate_frame"]:
                continue
            difference = float(first["z"]) - float(second["z"])
            if abs(difference) <= 1e-8:
                continue
            sign = 1 if difference > 0 else -1
            if previous_sign and sign != previous_sign:
                flips += 1
            previous_sign = sign
            samples += 1
        depth_flip_metrics[f"{first_name}--{second_name}"] = {
            "samples": samples,
            "flips": flips,
        }

    return {
        "schema_version": "0.1.0",
        "clip_id": prediction["clip_id"],
        "model_id": prediction["model"]["id"],
        "confidence_threshold": confidence,
        "runtime": {
            "mean_inference_ms": mean_inference_ms,
            "p95_inference_ms": sorted_inference[p95_index],
            "effective_inference_fps": (
                1000.0 / mean_inference_ms if mean_inference_ms > 0 else None
            ),
        },
        "two_d": {
            "native_keypoint_count": len(keypoint_names),
            "coverage": (total_present / total_expected) if total_expected else 0.0,
            "coverage_by_keypoint": coverage_by_keypoint,
            "dropout": dropout,
            "mean_normalized_second_difference": (
                statistics.fmean(second_differences)
                if second_differences
                else None
            ),
            "acceleration_spike_threshold": acceleration_spike_threshold,
            "acceleration_spike_rate": (
                spike_count / second_difference_count
                if second_difference_count
                else None
            ),
            "second_difference_samples": second_difference_count,
        },
        "feline_topology": _topology_metrics(frame_maps_2d, requirements),
        "three_d": {
            "frames_with_any_3d": sum(bool(frame) for frame in frame_maps_3d),
            "bone_length_stability": bone_metrics,
            "diagnostic_depth_flips": depth_flip_metrics,
        },
        "interpretation_boundary": (
            "These are failure-discovery metrics. They do not establish real-world "
            "metric accuracy without independent reference labels."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate a canonical CatPose bake-off prediction."
    )
    parser.add_argument("prediction", type=Path)
    parser.add_argument("--requirements", type=Path)
    parser.add_argument("--confidence", type=float, default=0.2)
    parser.add_argument("--acceleration-spike-threshold", type=float, default=0.03)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    prediction = json.loads(args.prediction.read_text(encoding="utf-8"))
    requirements = (
        json.loads(args.requirements.read_text(encoding="utf-8"))
        if args.requirements
        else None
    )
    result = evaluate(
        prediction,
        requirements,
        confidence=args.confidence,
        acceleration_spike_threshold=args.acceleration_spike_threshold,
    )
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
