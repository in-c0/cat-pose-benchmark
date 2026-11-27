from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw


def _load_seed(path: Path) -> dict[str, Any]:
    seed = json.loads(path.read_text(encoding="utf-8"))
    if seed.get("prompt_provenance", {}).get("evidence_tier") != "R3":
        raise ValueError("identity seed must remain explicitly R3")
    if len(seed.get("positive_points", [])) < 4:
        raise ValueError("whole-animal identity seed needs several distributed body points")
    return seed


def _frame_names(frames_dir: Path) -> list[str]:
    names = [
        path.name
        for path in frames_dir.iterdir()
        if path.suffix.lower() in {".jpg", ".jpeg"}
    ]
    names.sort(key=lambda name: int(Path(name).stem))
    if not names:
        raise ValueError(f"No JPEG frames found in {frames_dir}")
    return names


def _point_arrays(seed: dict[str, Any]) -> tuple[np.ndarray, np.ndarray, list[dict[str, float]]]:
    positives = [
        [float(point["x_px"]), float(point["y_px"])]
        for point in seed["positive_points"]
    ]
    xs = [point[0] for point in positives]
    ys = [point[1] for point in positives]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    width = max(1.0, max_x - min_x)
    height = max(1.0, max_y - min_y)
    image_width = float(seed["source_frame"]["width_px"])
    image_height = float(seed["source_frame"]["height_px"])

    # Background negatives are derived mechanically from the teacher-point envelope,
    # not hand annotated. Keep them well outside the positive envelope so modest body
    # extent beyond the keypoints is not incorrectly excluded.
    margin_x = max(50.0, width * 0.45)
    margin_y = max(50.0, height * 0.45)
    left = max(5.0, min_x - margin_x)
    right = min(image_width - 6.0, max_x + margin_x)
    top = max(5.0, min_y - margin_y)
    bottom = min(image_height - 6.0, max_y + margin_y)
    mid_x = (left + right) / 2.0
    mid_y = (top + bottom) / 2.0
    negatives = [
        {"x_px": left, "y_px": top},
        {"x_px": mid_x, "y_px": top},
        {"x_px": right, "y_px": top},
        {"x_px": left, "y_px": mid_y},
        {"x_px": right, "y_px": mid_y},
        {"x_px": left, "y_px": bottom},
        {"x_px": mid_x, "y_px": bottom},
        {"x_px": right, "y_px": bottom},
    ]
    coordinates = positives + [[point["x_px"], point["y_px"]] for point in negatives]
    labels = [1] * len(positives) + [0] * len(negatives)
    return (
        np.asarray(coordinates, dtype=np.float32),
        np.asarray(labels, dtype=np.int32),
        negatives,
    )


def _within_mask(mask: np.ndarray, x: float, y: float, radius: int = 3) -> bool:
    height, width = mask.shape
    col = int(round(x))
    row = int(round(y))
    r0 = max(0, row - radius)
    r1 = min(height, row + radius + 1)
    c0 = max(0, col - radius)
    c1 = min(width, col + radius + 1)
    return bool(mask[r0:r1, c0:c1].any())


def _candidate_diagnostics(
    mask: np.ndarray,
    score: float,
    positives: list[dict[str, Any]],
    negatives: list[dict[str, float]],
    index: int,
) -> dict[str, Any]:
    positive_hits = [
        _within_mask(mask, float(point["x_px"]), float(point["y_px"]), radius=4)
        for point in positives
    ]
    negative_hits = [
        _within_mask(mask, float(point["x_px"]), float(point["y_px"]), radius=1)
        for point in negatives
    ]
    pixels = np.argwhere(mask)
    bbox = None
    if len(pixels):
        bbox = [
            int(pixels[:, 1].min()),
            int(pixels[:, 0].min()),
            int(pixels[:, 1].max()),
            int(pixels[:, 0].max()),
        ]
    return {
        "candidate_index": index,
        "sam2_predicted_iou": float(score),
        "positive_prompt_inside_fraction": sum(positive_hits) / len(positive_hits),
        "negative_prompt_outside_fraction": (
            sum(not hit for hit in negative_hits) / len(negative_hits) if negative_hits else 1.0
        ),
        "positive_prompt_hits": positive_hits,
        "negative_prompt_hits": negative_hits,
        "mask_area_px": int(mask.sum()),
        "mask_area_fraction": float(mask.mean()),
        "bbox_xyxy": bbox,
    }


def _candidate_rank(candidate: dict[str, Any]) -> tuple[float, float, float, float]:
    # For a whole-animal target, distributed positive coverage and background exclusion
    # are semantic requirements. Model IoU follows those constraints. If scores tie,
    # prefer the smaller supported object rather than a background-spanning region.
    return (
        float(candidate["positive_prompt_inside_fraction"]),
        float(candidate["negative_prompt_outside_fraction"]),
        float(candidate["sam2_predicted_iou"]),
        -float(candidate["mask_area_fraction"]),
    )


def _mask_from_logits(mask_logits: Any) -> np.ndarray:
    value = mask_logits
    if hasattr(value, "detach"):
        value = value.detach()
    if hasattr(value, "cpu"):
        value = value.cpu()
    array = np.asarray(value)
    while array.ndim > 2:
        array = array[0]
    if array.ndim != 2:
        raise ValueError(f"Unexpected mask shape: {array.shape}")
    return array > 0.0


def _mask_iou(left: np.ndarray, right: np.ndarray) -> float:
    left = left.astype(bool)
    right = right.astype(bool)
    union = np.logical_or(left, right).sum()
    if union == 0:
        return 1.0
    return float(np.logical_and(left, right).sum() / union)


def _bbox(mask: np.ndarray) -> list[int] | None:
    pixels = np.argwhere(mask)
    if len(pixels) == 0:
        return None
    return [
        int(pixels[:, 1].min()),
        int(pixels[:, 0].min()),
        int(pixels[:, 1].max()),
        int(pixels[:, 0].max()),
    ]


def _centroid(mask: np.ndarray) -> tuple[float, float] | None:
    pixels = np.argwhere(mask)
    if len(pixels) == 0:
        return None
    return float(pixels[:, 1].mean()), float(pixels[:, 0].mean())


def _masked_histogram(image: Image.Image, mask: np.ndarray, bins: int = 8) -> np.ndarray:
    rgb = np.asarray(image.convert("RGB"), dtype=np.uint8)
    pixels = rgb[mask.astype(bool)]
    if len(pixels) == 0:
        return np.zeros(bins ** 3, dtype=np.float64)
    quantized = np.minimum((pixels.astype(np.int32) * bins) // 256, bins - 1)
    indices = quantized[:, 0] * bins * bins + quantized[:, 1] * bins + quantized[:, 2]
    hist = np.bincount(indices, minlength=bins ** 3).astype(np.float64)
    hist /= hist.sum()
    return hist


def _js_divergence(left: np.ndarray, right: np.ndarray) -> float:
    midpoint = (left + right) / 2.0

    def kl(a: np.ndarray, b: np.ndarray) -> float:
        valid = a > 0
        if not np.any(valid):
            return 0.0
        return float(np.sum(a[valid] * np.log2(a[valid] / np.maximum(b[valid], 1e-12))))

    return (kl(left, midpoint) + kl(right, midpoint)) / 2.0


def _save_overlay(
    image_path: Path,
    mask: np.ndarray,
    output_path: Path,
    *,
    frame_index: int,
    appearance_jsd: float | None,
    seed_points: list[dict[str, Any]] | None = None,
) -> None:
    image = Image.open(image_path).convert("RGBA")
    tint = Image.new("RGBA", image.size, (255, 0, 0, 0))
    tint.putalpha(Image.fromarray(np.where(mask, 75, 0).astype(np.uint8), mode="L"))
    composed = Image.alpha_composite(image, tint)
    draw = ImageDraw.Draw(composed)
    if seed_points:
        for point in seed_points:
            x, y = float(point["x_px"]), float(point["y_px"])
            draw.ellipse((x - 5, y - 5, x + 5, y + 5), fill=(0, 255, 0, 255))
    label = f"frame {frame_index}"
    if appearance_jsd is not None:
        label += f" | seed appearance JSD {appearance_jsd:.3f}"
    draw.rectangle((8, 8, 430, 38), fill=(0, 0, 0, 175))
    draw.text((14, 14), label, fill=(255, 255, 255, 255))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    composed.convert("RGB").save(output_path, quality=92)


def _contact_sheet(paths: list[Path], output: Path, columns: int = 4, width: int = 480) -> None:
    images = [Image.open(path).convert("RGB") for path in paths]
    if not images:
        return
    height = int(round(width * images[0].height / images[0].width))
    rows = math.ceil(len(images) / columns)
    sheet = Image.new("RGB", (columns * width, rows * height), "black")
    for index, image in enumerate(images):
        thumb = image.resize((width, height))
        sheet.paste(thumb, ((index % columns) * width, (index // columns) * height))
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output, quality=92)


def _propagate_direction(
    predictor: Any,
    state: Any,
    *,
    frames_dir: Path,
    frame_names: list[str],
    start_frame_idx: int,
    reverse: bool,
    seed_histogram: np.ndarray,
    seed_points: list[dict[str, Any]],
    output_dir: Path,
) -> dict[int, dict[str, Any]]:
    records: dict[int, dict[str, Any]] = {}
    for frame_idx, _obj_ids, logits in predictor.propagate_in_video(
        state,
        start_frame_idx=start_frame_idx,
        reverse=reverse,
    ):
        mask = _mask_from_logits(logits)
        image = Image.open(frames_dir / frame_names[int(frame_idx)]).convert("RGB")
        hist = _masked_histogram(image, mask)
        appearance_jsd = _js_divergence(seed_histogram, hist) if mask.any() else None
        center = _centroid(mask)
        record = {
            "frame_index": int(frame_idx),
            "direction": "reverse" if reverse else "forward",
            "mask_area_px": int(mask.sum()),
            "mask_area_fraction": float(mask.mean()),
            "bbox_xyxy": _bbox(mask),
            "centroid_xy": list(center) if center else None,
            "seed_appearance_jsd": appearance_jsd,
        }
        overlay_path = output_dir / "overlays" / f"{int(frame_idx):05d}.jpg"
        _save_overlay(
            frames_dir / frame_names[int(frame_idx)],
            mask,
            overlay_path,
            frame_index=int(frame_idx),
            appearance_jsd=appearance_jsd,
            seed_points=seed_points if int(frame_idx) == start_frame_idx else None,
        )
        records[int(frame_idx)] = record
    return records


def _summary(
    records: list[dict[str, Any]],
    *,
    seed_frame_idx: int,
    seed_area_fraction: float,
    seed_mask_iou: float,
    image_diagonal: float,
) -> dict[str, Any]:
    nonempty = [record for record in records if int(record["mask_area_px"]) > 0]
    expansion_threshold = max(0.15, seed_area_fraction * 4.0)
    collapse_threshold = seed_area_fraction * 0.12
    expansion_frames = [
        record["frame_index"]
        for record in records
        if float(record["mask_area_fraction"]) > expansion_threshold
    ]
    collapse_frames = [
        record["frame_index"]
        for record in records
        if 0 < float(record["mask_area_fraction"]) < collapse_threshold
    ]
    empty_frames = [
        record["frame_index"] for record in records if int(record["mask_area_px"]) == 0
    ]

    centroid_steps: list[float] = []
    previous: dict[str, Any] | None = None
    for record in records:
        if (
            previous is not None
            and record["frame_index"] == previous["frame_index"] + 1
            and record.get("centroid_xy")
            and previous.get("centroid_xy")
        ):
            current = record["centroid_xy"]
            prior = previous["centroid_xy"]
            centroid_steps.append(
                math.hypot(current[0] - prior[0], current[1] - prior[1]) / image_diagonal
            )
        previous = record

    appearance = [
        float(record["seed_appearance_jsd"])
        for record in records
        if record.get("seed_appearance_jsd") is not None
    ]
    return {
        "frames_total": len(records),
        "nonempty_mask_coverage": len(nonempty) / len(records) if records else 0.0,
        "seed_mask_iou": seed_mask_iou,
        "seed_preserved": seed_mask_iou >= 0.90,
        "seed_mask_area_fraction": seed_area_fraction,
        "expansion_threshold": expansion_threshold,
        "expansion_frames": expansion_frames,
        "collapse_threshold": collapse_threshold,
        "collapse_frames": collapse_frames,
        "empty_frames": empty_frames,
        "mean_centroid_step_fraction": float(np.mean(centroid_steps)) if centroid_steps else None,
        "max_centroid_step_fraction": float(np.max(centroid_steps)) if centroid_steps else None,
        "mean_seed_appearance_jsd": float(np.mean(appearance)) if appearance else None,
        "max_seed_appearance_jsd": float(np.max(appearance)) if appearance else None,
        "appearance_interpretation": (
            "RGB histogram Jensen-Shannon divergence is an unsupervised identity-change "
            "diagnostic only; it is not a calibrated feline ReID score."
        ),
        "engineering_feasibility": (
            "pass"
            if seed_mask_iou >= 0.90 and not expansion_frames and not collapse_frames and not empty_frames
            else "revise"
        ),
        "scientific_boundary": (
            "This gate tests mask continuity and gross drift, not independent animal identity truth. "
            "Visual regression review of the known second-cat failure window remains required."
        ),
    }


def run(
    *,
    frames_dir: Path,
    seed_path: Path,
    output_dir: Path,
    checkpoint: str,
    device: str,
) -> dict[str, Any]:
    try:
        from sam2.sam2_image_predictor import SAM2ImagePredictor
        from sam2.sam2_video_predictor import SAM2VideoPredictor
    except ImportError as exception:
        raise RuntimeError("SAM2 is required for whole-animal identity tracking") from exception

    seed = _load_seed(seed_path)
    frame_names = _frame_names(frames_dir)
    seed_frame_idx = int(seed["source_frame"]["smoke_frame_index"])
    if not (0 <= seed_frame_idx < len(frame_names)):
        raise ValueError("seed frame index outside sequence")
    seed_image_path = frames_dir / frame_names[seed_frame_idx]
    seed_image = Image.open(seed_image_path).convert("RGB")
    expected_size = (
        int(seed["source_frame"]["width_px"]),
        int(seed["source_frame"]["height_px"]),
    )
    if seed_image.size != expected_size:
        raise ValueError(f"seed image size {seed_image.size} != {expected_size}")

    coords, labels, auto_negatives = _point_arrays(seed)
    image_predictor = SAM2ImagePredictor.from_pretrained(checkpoint, device=device)
    image_predictor.set_image(np.asarray(seed_image))
    masks, scores, _logits = image_predictor.predict(
        point_coords=coords,
        point_labels=labels,
        multimask_output=True,
    )
    boolean_masks = np.asarray(masks).astype(bool)
    score_values = np.asarray(scores).reshape(-1)
    candidates = [
        _candidate_diagnostics(
            mask,
            float(score_values[index]),
            seed["positive_points"],
            auto_negatives,
            index,
        )
        for index, mask in enumerate(boolean_masks)
    ]
    chosen_index = max(range(len(candidates)), key=lambda index: _candidate_rank(candidates[index]))
    chosen_mask = boolean_masks[chosen_index]
    chosen = candidates[chosen_index]
    if chosen["positive_prompt_inside_fraction"] < 0.75:
        raise RuntimeError(f"No whole-animal candidate covers enough seed points: {chosen}")

    output_dir.mkdir(parents=True, exist_ok=True)
    np.save(output_dir / "seed-mask.npy", chosen_mask.astype(np.uint8))
    Image.fromarray((chosen_mask.astype(np.uint8) * 255), mode="L").save(output_dir / "seed-mask.png")
    seed_hist = _masked_histogram(seed_image, chosen_mask)

    video_predictor = SAM2VideoPredictor.from_pretrained(checkpoint, device=device)
    state = video_predictor.init_state(
        str(frames_dir),
        offload_video_to_cpu=True,
        offload_state_to_cpu=True,
        async_loading_frames=False,
    )
    _idx, _ids, seed_logits = video_predictor.add_new_mask(
        state,
        frame_idx=seed_frame_idx,
        obj_id=1,
        mask=chosen_mask,
    )
    video_seed_mask = _mask_from_logits(seed_logits)
    seed_mask_iou = _mask_iou(chosen_mask, video_seed_mask)

    reverse = _propagate_direction(
        video_predictor,
        state,
        frames_dir=frames_dir,
        frame_names=frame_names,
        start_frame_idx=seed_frame_idx,
        reverse=True,
        seed_histogram=seed_hist,
        seed_points=seed["positive_points"],
        output_dir=output_dir,
    )
    forward = _propagate_direction(
        video_predictor,
        state,
        frames_dir=frames_dir,
        frame_names=frame_names,
        start_frame_idx=seed_frame_idx,
        reverse=False,
        seed_histogram=seed_hist,
        seed_points=seed["positive_points"],
        output_dir=output_dir,
    )
    combined = dict(reverse)
    combined.update(forward)
    records = [combined[index] for index in sorted(combined)]
    image_diagonal = math.hypot(expected_size[0], expected_size[1])
    summary = _summary(
        records,
        seed_frame_idx=seed_frame_idx,
        seed_area_fraction=float(chosen_mask.mean()),
        seed_mask_iou=seed_mask_iou,
        image_diagonal=image_diagonal,
    )
    overlay_paths = [output_dir / "overlays" / f"{record['frame_index']:05d}.jpg" for record in records]
    _contact_sheet(overlay_paths, output_dir / "identity-contact-sheet.jpg")

    payload = {
        "schema_version": "0.1.0",
        "clip_id": seed["clip_id"],
        "target_id": seed["target_id"],
        "checkpoint": checkpoint,
        "device": device,
        "evidence_tier": "R3",
        "seed_frame_index": seed_frame_idx,
        "seed_candidate": chosen,
        "all_seed_candidates": candidates,
        "auto_background_negatives": auto_negatives,
        "seed_provenance": seed["prompt_provenance"],
        "frames": records,
        "summary": summary,
        "scientific_boundary": (
            "The seed, mask and propagation are R3 model-derived research evidence. "
            "A visually persistent mask can establish engineering feasibility for a target track, "
            "not independent identity accuracy or product-training eligibility."
        ),
    }
    (output_dir / "identity-result.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Track one whole cat through the multi-cat regression sequence.")
    parser.add_argument("frames_dir", type=Path)
    parser.add_argument("seed", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--checkpoint", default="facebook/sam2.1-hiera-tiny")
    parser.add_argument("--device", default="cpu")
    args = parser.parse_args()

    result = run(
        frames_dir=args.frames_dir,
        seed_path=args.seed,
        output_dir=args.output_dir,
        checkpoint=args.checkpoint,
        device=args.device,
    )
    print(json.dumps(result["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
