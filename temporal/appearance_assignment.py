from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _seed_bbox(seed: dict[str, Any], padding_fraction: float) -> list[float]:
    points = seed.get("positive_points", [])
    if not points:
        raise ValueError("identity seed contains no positive points")
    xs = [float(point["x_px"]) for point in points]
    ys = [float(point["y_px"]) for point in points]
    left, top, right, bottom = min(xs), min(ys), max(xs), max(ys)
    width = max(1.0, right - left)
    height = max(1.0, bottom - top)
    return [
        left - padding_fraction * width,
        top - padding_fraction * height,
        right + padding_fraction * width,
        bottom + padding_fraction * height,
    ]


def _crop_histogram(
    image: Image.Image,
    bbox_xyxy: list[float],
    *,
    bins: int,
) -> np.ndarray:
    if bins < 2:
        raise ValueError("histogram bins must be >= 2")
    array = np.asarray(image.convert("RGB"), dtype=np.uint8)
    left, top, right, bottom = [float(value) for value in bbox_xyxy]
    x0 = max(0, int(math.floor(left)))
    y0 = max(0, int(math.floor(top)))
    x1 = min(array.shape[1] - 1, int(math.ceil(right)))
    y1 = min(array.shape[0] - 1, int(math.ceil(bottom)))
    if x1 < x0 or y1 < y0:
        raise ValueError(f"invalid crop bbox {bbox_xyxy}")
    pixels = array[y0 : y1 + 1, x0 : x1 + 1].reshape(-1, 3).astype(np.int32)
    if len(pixels) == 0:
        raise ValueError("candidate crop contains no pixels")
    quantized = np.minimum((pixels * bins) // 256, bins - 1)
    indices = (
        quantized[:, 0] * bins * bins
        + quantized[:, 1] * bins
        + quantized[:, 2]
    )
    histogram = np.bincount(indices, minlength=bins**3).astype(np.float64)
    histogram /= histogram.sum()
    return histogram


def _js_divergence(left: np.ndarray, right: np.ndarray) -> float:
    if left.shape != right.shape:
        raise ValueError("histograms must have identical shape")
    midpoint = (left + right) / 2.0

    def kl(a: np.ndarray, b: np.ndarray) -> float:
        valid = a > 0
        if not np.any(valid):
            return 0.0
        return float(
            np.sum(a[valid] * np.log2(a[valid] / np.maximum(b[valid], 1e-12)))
        )

    return (kl(left, midpoint) + kl(right, midpoint)) / 2.0


def _frame_path(frames_dir: Path, frame_index: int) -> Path:
    candidates = [
        frames_dir / f"{frame_index:05d}.jpg",
        frames_dir / f"{frame_index:05d}.jpeg",
        frames_dir / f"frame-{frame_index + 1:02d}.png",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        f"No raw frame for source index {frame_index}; tried {[str(path) for path in candidates]}"
    )


def _candidate_costs(
    frame: dict[str, Any],
    *,
    image: Image.Image,
    reference_histogram: np.ndarray,
    bins: int,
) -> list[dict[str, Any]]:
    costs: list[dict[str, Any]] = []
    for candidate_index, candidate in enumerate(frame.get("candidates", [])):
        histogram = _crop_histogram(image, candidate["bbox_xyxy"], bins=bins)
        appearance_jsd = _js_divergence(reference_histogram, histogram)
        costs.append(
            {
                "candidate_index": candidate_index,
                "individual": candidate["individual"],
                "appearance_jsd": appearance_jsd,
                "mean_keypoint_score": float(candidate["mean_keypoint_score"]),
                "high_confidence_keypoint_count": int(
                    candidate["high_confidence_keypoint_count"]
                ),
                "bbox_xyxy": [float(value) for value in candidate["bbox_xyxy"]],
            }
        )
    costs.sort(
        key=lambda item: (
            item["appearance_jsd"],
            -item["high_confidence_keypoint_count"],
            -item["mean_keypoint_score"],
            item["candidate_index"],
        )
    )
    return costs


def assign_candidates(
    multi_candidates: dict[str, Any],
    seed: dict[str, Any],
    *,
    frames_dir: Path,
    appearance_threshold: float,
    seed_padding_fraction: float = 0.05,
    histogram_bins: int = 8,
) -> dict[str, Any]:
    """Conservatively assign one target identity or emit LOST.

    The threshold is an engineering parameter, not a calibrated probability. The first
    regression uses 0.30 after observing a gap between the visually correct grey-cat
    candidate and the wrong black/white-cat candidate. It must be validated on held-out
    clips before any general identity claim.
    """

    if appearance_threshold < 0:
        raise ValueError("appearance_threshold must be non-negative")
    if seed.get("prompt_provenance", {}).get("evidence_tier") != "R3":
        raise ValueError("seed provenance must remain explicitly R3")

    seed_frame_index = int(seed["source_frame"]["smoke_frame_index"])
    seed_image = Image.open(_frame_path(frames_dir, seed_frame_index)).convert("RGB")
    reference_bbox = _seed_bbox(seed, seed_padding_fraction)
    reference_histogram = _crop_histogram(
        seed_image, reference_bbox, bins=histogram_bins
    )

    output_frames: list[dict[str, Any]] = []
    previous_state = "target"
    for frame in multi_candidates.get("frames", []):
        source_index = int(frame["frame_index"])
        image = Image.open(_frame_path(frames_dir, source_index)).convert("RGB")
        costs = _candidate_costs(
            frame,
            image=image,
            reference_histogram=reference_histogram,
            bins=histogram_bins,
        )
        accepted = costs[0] if costs and costs[0]["appearance_jsd"] <= appearance_threshold else None

        if accepted is None:
            state = "lost"
            transition = "lost" if previous_state != "lost" else "remain_lost"
        else:
            state = "target"
            transition = "reacquired" if previous_state == "lost" else "tracked"

        output_frames.append(
            {
                "frame_index": source_index,
                "candidate_count": len(costs),
                "state": state,
                "transition": transition,
                "selected_candidate": accepted,
                "candidate_costs": costs,
            }
        )
        previous_state = state

    target_frames = [
        frame["frame_index"] for frame in output_frames if frame["state"] == "target"
    ]
    lost_frames = [
        frame["frame_index"] for frame in output_frames if frame["state"] == "lost"
    ]
    reacquired_frames = [
        frame["frame_index"]
        for frame in output_frames
        if frame["transition"] == "reacquired"
    ]
    return {
        "schema_version": "0.1.0",
        "clip_id": multi_candidates.get("source", {}).get("clip_id", seed["clip_id"]),
        "target_id": seed["target_id"],
        "evidence_tier": "R3",
        "appearance": {
            "descriptor": f"rgb_{histogram_bins}x{histogram_bins}x{histogram_bins}_bbox_histogram",
            "distance": "jensen_shannon_divergence_bits",
            "threshold": appearance_threshold,
            "seed_padding_fraction": seed_padding_fraction,
            "reference_bbox_xyxy": reference_bbox,
            "calibration_status": "exploratory_same_regression_clip",
        },
        "frames": output_frames,
        "summary": {
            "target_frames": target_frames,
            "lost_frames": lost_frames,
            "reacquired_frames": reacquired_frames,
            "wrong_candidate_is_never_forced_when_gate_fails": True,
            "interpretation_boundary": (
                "This is an exploratory assignment baseline on the same regression clip "
                "used to select the 0.30 appearance threshold. It demonstrates the value "
                "of an explicit LOST state; it does not establish held-out feline ReID accuracy."
            ),
        },
        "scientific_boundary": (
            "Candidate poses and the seed are R3 research-only model outputs. Appearance "
            "assignment is engineering evidence only and is not identity ground truth."
        ),
    }


def _render_assignment_overlays(
    result: dict[str, Any],
    *,
    frames_dir: Path,
    output_dir: Path,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for frame in result["frames"]:
        image = Image.open(_frame_path(frames_dir, int(frame["frame_index"]))).convert("RGB")
        draw = ImageDraw.Draw(image)
        for cost in frame["candidate_costs"]:
            left, top, right, bottom = cost["bbox_xyxy"]
            selected = (
                frame["selected_candidate"] is not None
                and cost["candidate_index"]
                == frame["selected_candidate"]["candidate_index"]
            )
            width = 6 if selected else 2
            draw.rectangle((left, top, right, bottom), outline="red", width=width)
            label = (
                f"c{cost['candidate_index']} JSD={cost['appearance_jsd']:.3f} "
                f"{'SELECT' if selected else ''}"
            )
            draw.rectangle(
                (left, max(0, top - 23), min(image.width - 1, left + 245), top),
                fill="black",
            )
            draw.text((left + 3, max(0, top - 20)), label, fill="white")
        state_label = f"frame {frame['frame_index']} | {frame['state']} | {frame['transition']}"
        draw.rectangle((8, 8, 430, 36), fill="black")
        draw.text((14, 13), state_label, fill="white")
        image.save(output_dir / f"{int(frame['frame_index']):05d}.jpg", quality=92)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Assign a persistent target among multi-animal pose candidates using a conservative appearance gate."
    )
    parser.add_argument("multi_candidates", type=Path)
    parser.add_argument("seed", type=Path)
    parser.add_argument("frames_dir", type=Path)
    parser.add_argument("--appearance-threshold", type=float, default=0.30)
    parser.add_argument("--seed-padding-fraction", type=float, default=0.05)
    parser.add_argument("--histogram-bins", type=int, default=8)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--overlays-dir", type=Path)
    args = parser.parse_args()

    result = assign_candidates(
        _load_json(args.multi_candidates),
        _load_json(args.seed),
        frames_dir=args.frames_dir,
        appearance_threshold=args.appearance_threshold,
        seed_padding_fraction=args.seed_padding_fraction,
        histogram_bins=args.histogram_bins,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    if args.overlays_dir:
        _render_assignment_overlays(
            result, frames_dir=args.frames_dir, output_dir=args.overlays_dir
        )
    print(json.dumps(result["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
