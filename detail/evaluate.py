from __future__ import annotations

import argparse
import json
import math
import statistics
from pathlib import Path
from typing import Any


OBSERVABLE = {"visible", "partially_occluded"}


def _xy(point: dict[str, Any]) -> tuple[float, float]:
    return float(point["x_px"]), float(point["y_px"])


def _distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _mean_point(a: tuple[float, float], b: tuple[float, float]) -> tuple[float, float]:
    return (0.5 * (a[0] + b[0]), 0.5 * (a[1] + b[1]))


def _angle_difference_degrees(
    reference: tuple[float, float], prediction: tuple[float, float]
) -> float | None:
    ref_length = math.hypot(*reference)
    pred_length = math.hypot(*prediction)
    if ref_length <= 1e-12 or pred_length <= 1e-12:
        return None
    cosine = (reference[0] * prediction[0] + reference[1] * prediction[1]) / (
        ref_length * pred_length
    )
    cosine = max(-1.0, min(1.0, cosine))
    return math.degrees(math.acos(cosine))


def _validate_curve(samples: list[dict[str, Any]]) -> None:
    if len(samples) < 2:
        raise ValueError("tail curve requires at least two samples")
    u_values = [float(sample["u"]) for sample in samples]
    if any(right <= left for left, right in zip(u_values, u_values[1:])):
        raise ValueError("tail sample u values must be strictly increasing from base to tip")
    if abs(u_values[0]) > 1e-9 or abs(u_values[-1] - 1.0) > 1e-9:
        raise ValueError("tail curve must include u=0 base and u=1 tip")


def _resample_curve(
    samples: list[dict[str, Any]], count: int = 32
) -> list[tuple[float, float]]:
    _validate_curve(samples)
    points = [_xy(sample) for sample in samples]
    segment_lengths = [
        _distance(left, right) for left, right in zip(points, points[1:])
    ]
    total = sum(segment_lengths)
    if total <= 1e-12:
        return [points[0] for _ in range(count)]

    cumulative = [0.0]
    for length in segment_lengths:
        cumulative.append(cumulative[-1] + length)

    result: list[tuple[float, float]] = []
    segment_index = 0
    for sample_index in range(count):
        target = total * sample_index / (count - 1)
        while (
            segment_index < len(segment_lengths) - 1
            and cumulative[segment_index + 1] < target
        ):
            segment_index += 1
        start_distance = cumulative[segment_index]
        segment_length = segment_lengths[segment_index]
        if segment_length <= 1e-12:
            alpha = 0.0
        else:
            alpha = (target - start_distance) / segment_length
        start = points[segment_index]
        end = points[segment_index + 1]
        result.append(
            (
                start[0] + alpha * (end[0] - start[0]),
                start[1] + alpha * (end[1] - start[1]),
            )
        )
    return result


def _ear_metrics(
    reference: dict[str, Any], prediction: dict[str, Any], image_diagonal: float
) -> dict[str, Any]:
    point_errors: dict[str, float | None] = {}
    comparable = 0
    for name in ("base_medial", "base_lateral", "tip"):
        ref_point = reference[name]
        pred_point = prediction[name]
        if ref_point["visibility"] not in OBSERVABLE:
            point_errors[name] = None
            continue
        if pred_point["visibility"] not in OBSERVABLE:
            point_errors[name] = None
            continue
        point_errors[name] = _distance(_xy(ref_point), _xy(pred_point)) / image_diagonal
        comparable += 1

    base_centre_error = None
    axis_error = None
    ref_base_points = (reference["base_medial"], reference["base_lateral"])
    pred_base_points = (prediction["base_medial"], prediction["base_lateral"])
    if (
        all(point["visibility"] in OBSERVABLE for point in ref_base_points)
        and all(point["visibility"] in OBSERVABLE for point in pred_base_points)
        and reference["tip"]["visibility"] in OBSERVABLE
        and prediction["tip"]["visibility"] in OBSERVABLE
    ):
        ref_base = _mean_point(_xy(ref_base_points[0]), _xy(ref_base_points[1]))
        pred_base = _mean_point(_xy(pred_base_points[0]), _xy(pred_base_points[1]))
        base_centre_error = _distance(ref_base, pred_base) / image_diagonal
        ref_tip = _xy(reference["tip"])
        pred_tip = _xy(prediction["tip"])
        axis_error = _angle_difference_degrees(
            (ref_tip[0] - ref_base[0], ref_tip[1] - ref_base[1]),
            (pred_tip[0] - pred_base[0], pred_tip[1] - pred_base[1]),
        )

    return {
        "side": reference["side"],
        "comparable_points": comparable,
        "normalized_point_error": point_errors,
        "normalized_base_centre_error": base_centre_error,
        "axis_angle_error_degrees": axis_error,
    }


def _tail_metrics(
    reference: dict[str, Any], prediction: dict[str, Any], image_diagonal: float
) -> dict[str, Any]:
    ref_samples = reference["samples"]
    pred_samples = prediction["samples"]
    _validate_curve(ref_samples)
    _validate_curve(pred_samples)

    observable_reference = [
        sample for sample in ref_samples if sample["visibility"] in OBSERVABLE
    ]
    visible_fraction = len(observable_reference) / len(ref_samples)

    base_error = None
    tip_error = None
    if (
        ref_samples[0]["visibility"] in OBSERVABLE
        and pred_samples[0]["visibility"] in OBSERVABLE
    ):
        base_error = _distance(_xy(ref_samples[0]), _xy(pred_samples[0])) / image_diagonal
    if (
        ref_samples[-1]["visibility"] in OBSERVABLE
        and pred_samples[-1]["visibility"] in OBSERVABLE
    ):
        tip_error = _distance(_xy(ref_samples[-1]), _xy(pred_samples[-1])) / image_diagonal

    # A full ordered-curve error is only an observation-space metric when the complete
    # reference curve is directly observable. Partial/hidden reference geometry is not
    # silently scored as if it were measured truth.
    curve_mean_error = None
    curve_max_error = None
    if visible_fraction == 1.0:
        ref_curve = _resample_curve(ref_samples)
        pred_curve = _resample_curve(pred_samples)
        errors = [
            _distance(ref_point, pred_point) / image_diagonal
            for ref_point, pred_point in zip(ref_curve, pred_curve)
        ]
        curve_mean_error = statistics.fmean(errors)
        curve_max_error = max(errors)

    return {
        "reference_sample_count": len(ref_samples),
        "prediction_sample_count": len(pred_samples),
        "reference_observable_fraction": visible_fraction,
        "normalized_base_error": base_error,
        "normalized_tip_error": tip_error,
        "normalized_ordered_curve_mean_error": curve_mean_error,
        "normalized_ordered_curve_max_error": curve_max_error,
        "curve_error_boundary": (
            "Full ordered-curve error is reported only when the complete reference "
            "centreline is observable."
        ),
    }


def evaluate_sequence(
    reference: dict[str, Any], prediction: dict[str, Any]
) -> dict[str, Any]:
    if reference["sequence_id"] != prediction["sequence_id"]:
        raise ValueError("reference/prediction sequence_id mismatch")
    width = int(reference["image"]["width_px"])
    height = int(reference["image"]["height_px"])
    if prediction["image"] != reference["image"]:
        raise ValueError("reference/prediction image metadata mismatch")
    image_diagonal = math.hypot(width, height)

    ref_frames = {int(frame["frame_index"]): frame for frame in reference["frames"]}
    pred_frames = {int(frame["frame_index"]): frame for frame in prediction["frames"]}
    if set(ref_frames) != set(pred_frames):
        raise ValueError("reference/prediction frame sets differ")

    frame_results = []
    ear_point_errors: list[float] = []
    ear_axis_errors: list[float] = []
    tail_curve_errors: list[float] = []

    for frame_index in sorted(ref_frames):
        ref_frame = ref_frames[frame_index]
        pred_frame = pred_frames[frame_index]
        ref_ears = {ear["side"]: ear for ear in ref_frame["ears"]}
        pred_ears = {ear["side"]: ear for ear in pred_frame["ears"]}

        ears = []
        for side in sorted(ref_ears):
            if side not in pred_ears:
                ears.append({"side": side, "missing_prediction": True})
                continue
            result = _ear_metrics(ref_ears[side], pred_ears[side], image_diagonal)
            ears.append(result)
            for value in result["normalized_point_error"].values():
                if value is not None:
                    ear_point_errors.append(value)
            if result["axis_angle_error_degrees"] is not None:
                ear_axis_errors.append(result["axis_angle_error_degrees"])

        tail = _tail_metrics(ref_frame["tail"], pred_frame["tail"], image_diagonal)
        if tail["normalized_ordered_curve_mean_error"] is not None:
            tail_curve_errors.append(tail["normalized_ordered_curve_mean_error"])

        frame_results.append(
            {
                "frame_index": frame_index,
                "ears": ears,
                "tail": tail,
            }
        )

    return {
        "schema_version": "0.1.0",
        "sequence_id": reference["sequence_id"],
        "summary": {
            "mean_normalized_ear_point_error": (
                statistics.fmean(ear_point_errors) if ear_point_errors else None
            ),
            "mean_ear_axis_error_degrees": (
                statistics.fmean(ear_axis_errors) if ear_axis_errors else None
            ),
            "mean_normalized_tail_curve_error": (
                statistics.fmean(tail_curve_errors) if tail_curve_errors else None
            ),
            "fully_observable_tail_frames": len(tail_curve_errors),
        },
        "frames": frame_results,
        "evidence_boundary": (
            "Only reference geometry marked directly observable is scored as observation "
            "truth; hidden geometry requires a different R3/G-tier evaluation."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("reference", type=Path)
    parser.add_argument("prediction", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    reference = json.loads(args.reference.read_text(encoding="utf-8"))
    prediction = json.loads(args.prediction.read_text(encoding="utf-8"))
    result = evaluate_sequence(reference, prediction)
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
