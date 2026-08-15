from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw

from detail.mask_centerline import mask_to_tail_samples


def _load_prompt(path: Path) -> dict[str, Any]:
    prompt = json.loads(path.read_text(encoding="utf-8"))
    if prompt.get("prompt_provenance", {}).get("evidence_tier") != "R3":
        raise ValueError("SAM2 research prompt fixture must remain explicitly R3")
    if len(prompt.get("positive_points", [])) < 2:
        raise ValueError("At least tail-base and tail-tip positive prompts are required")
    return prompt


def _prompt_arrays(prompt: dict[str, Any]) -> tuple[np.ndarray, np.ndarray]:
    coordinates: list[list[float]] = []
    labels: list[int] = []
    for point in prompt["positive_points"]:
        coordinates.append([float(point["x_px"]), float(point["y_px"])])
        labels.append(1)
    for point in prompt.get("negative_points", []):
        coordinates.append([float(point["x_px"]), float(point["y_px"])])
        labels.append(0)
    return np.asarray(coordinates, dtype=np.float32), np.asarray(labels, dtype=np.int32)


def _inside(mask: np.ndarray, x: float, y: float) -> bool:
    height, width = mask.shape
    col = min(width - 1, max(0, int(round(x))))
    row = min(height - 1, max(0, int(round(y))))
    return bool(mask[row, col])


def _candidate_diagnostics(
    mask: np.ndarray,
    score: float,
    prompt: dict[str, Any],
    index: int,
) -> dict[str, Any]:
    positives = prompt["positive_points"]
    negatives = prompt.get("negative_points", [])
    positive_hits = [
        _inside(mask, float(point["x_px"]), float(point["y_px"]))
        for point in positives
    ]
    negative_hits = [
        _inside(mask, float(point["x_px"]), float(point["y_px"]))
        for point in negatives
    ]
    positive_fraction = sum(positive_hits) / len(positive_hits) if positive_hits else 0.0
    negative_exclusion_fraction = (
        sum(not hit for hit in negative_hits) / len(negative_hits) if negative_hits else 1.0
    )
    return {
        "candidate_index": index,
        "sam2_predicted_iou": float(score),
        "positive_prompt_inside_fraction": positive_fraction,
        "negative_prompt_outside_fraction": negative_exclusion_fraction,
        "positive_prompt_hits": positive_hits,
        "negative_prompt_hits": negative_hits,
        "mask_area_px": int(mask.sum()),
        "mask_area_fraction": float(mask.mean()),
    }


def _candidate_rank(diagnostic: dict[str, Any]) -> tuple[float, float, float, float]:
    # Prompt consistency outranks SAM2's own mask-quality score. This avoids selecting a
    # high-IoU whole-cat mask that ignores the explicit negative body prompts.
    return (
        float(diagnostic["positive_prompt_inside_fraction"]),
        float(diagnostic["negative_prompt_outside_fraction"]),
        float(diagnostic["sam2_predicted_iou"]),
        -float(diagnostic["mask_area_fraction"]),
    )


def _save_mask_png(mask: np.ndarray, path: Path) -> None:
    Image.fromarray((mask.astype(np.uint8) * 255), mode="L").save(path)


def _save_overlay(
    image: Image.Image,
    mask: np.ndarray,
    prompt: dict[str, Any],
    tail_samples: list[dict[str, Any]],
    path: Path,
) -> None:
    base = image.convert("RGBA")
    tint = Image.new("RGBA", base.size, (255, 0, 0, 0))
    alpha = np.where(mask, 80, 0).astype(np.uint8)
    tint.putalpha(Image.fromarray(alpha, mode="L"))
    composed = Image.alpha_composite(base, tint)
    draw = ImageDraw.Draw(composed)

    for point in prompt["positive_points"]:
        x, y = float(point["x_px"]), float(point["y_px"])
        draw.ellipse((x - 5, y - 5, x + 5, y + 5), fill=(0, 255, 0, 255))
    for point in prompt.get("negative_points", []):
        x, y = float(point["x_px"]), float(point["y_px"])
        draw.ellipse((x - 5, y - 5, x + 5, y + 5), fill=(0, 100, 255, 255))

    curve = [(float(sample["x_px"]), float(sample["y_px"])) for sample in tail_samples]
    if len(curve) >= 2:
        draw.line(curve, fill=(255, 255, 0, 255), width=4)
    for x, y in curve:
        draw.ellipse((x - 2, y - 2, x + 2, y + 2), fill=(255, 255, 0, 255))

    composed.convert("RGB").save(path, quality=95)


def run(
    *,
    image_path: Path,
    prompt_path: Path,
    output_dir: Path,
    checkpoint: str,
    sample_count: int,
) -> dict[str, Any]:
    try:
        from sam2.sam2_image_predictor import SAM2ImagePredictor
    except ImportError as exception:
        raise RuntimeError(
            "SAM2 is not installed. Install facebookresearch/sam2 with "
            "SAM2_BUILD_CUDA=0 for the CPU research baseline."
        ) from exception

    prompt = _load_prompt(prompt_path)
    image = Image.open(image_path).convert("RGB")
    expected_width = int(prompt["source_frame"]["width_px"])
    expected_height = int(prompt["source_frame"]["height_px"])
    if image.size != (expected_width, expected_height):
        raise ValueError(
            f"Frame size {image.size} does not match prompt metadata "
            f"{(expected_width, expected_height)}"
        )

    point_coords, point_labels = _prompt_arrays(prompt)
    predictor = SAM2ImagePredictor.from_pretrained(checkpoint)
    predictor.set_image(np.asarray(image))
    masks, scores, _logits = predictor.predict(
        point_coords=point_coords,
        point_labels=point_labels,
        multimask_output=True,
    )

    boolean_masks = np.asarray(masks).astype(bool)
    score_values = np.asarray(scores).reshape(-1)
    if boolean_masks.ndim != 3 or len(boolean_masks) == 0:
        raise RuntimeError(f"Unexpected SAM2 mask output shape: {boolean_masks.shape}")
    if len(boolean_masks) != len(score_values):
        raise RuntimeError("SAM2 mask/score count mismatch")

    diagnostics = [
        _candidate_diagnostics(mask, float(score_values[index]), prompt, index)
        for index, mask in enumerate(boolean_masks)
    ]
    chosen_index = max(range(len(diagnostics)), key=lambda index: _candidate_rank(diagnostics[index]))
    chosen_mask = boolean_masks[chosen_index]

    tail_base = prompt["positive_points"][0]
    tail_samples = mask_to_tail_samples(
        chosen_mask,
        base_xy=(float(tail_base["x_px"]), float(tail_base["y_px"])),
        sample_count=sample_count,
        provenance="sam2.1_hiera_tiny_prompted_mask_to_skeleton_v0",
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    np.save(output_dir / "tail-mask.npy", chosen_mask.astype(np.uint8))
    _save_mask_png(chosen_mask, output_dir / "tail-mask.png")
    _save_overlay(image, chosen_mask, prompt, tail_samples, output_dir / "tail-overlay.jpg")

    curve_payload = {
        "schema_version": "0.1.0",
        "evidence_tier": "R3",
        "clip_id": prompt["clip_id"],
        "source_frame": prompt["source_frame"],
        "tail": {"samples": tail_samples},
        "provenance": {
            "prompt": prompt["prompt_provenance"],
            "segmentation_model": prompt["segmentation_model"],
            "method": "prompted_mask_to_skeleton_longest_path_v0",
        },
        "scientific_boundary": (
            "Model-derived segmentation and geometry. This is not observed ground truth "
            "and is not product-training data under the current licensing gate."
        ),
    }
    (output_dir / "tail-curve.json").write_text(
        json.dumps(curve_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    result = {
        "schema_version": "0.1.0",
        "checkpoint": checkpoint,
        "chosen_candidate": diagnostics[chosen_index],
        "all_candidates": diagnostics,
        "tail_sample_count": len(tail_samples),
        "prompt_count": int(len(point_labels)),
        "positive_prompt_count": int((point_labels == 1).sum()),
        "negative_prompt_count": int((point_labels == 0).sum()),
        "scientific_boundary": curve_payload["scientific_boundary"],
    }
    (output_dir / "diagnostics.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prompt SAM2 for a research-only cat tail mask and derive a centreline."
    )
    parser.add_argument("image", type=Path)
    parser.add_argument("prompt", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--checkpoint", default="facebook/sam2.1-hiera-tiny")
    parser.add_argument("--samples", type=int, default=24)
    args = parser.parse_args()

    result = run(
        image_path=args.image,
        prompt_path=args.prompt,
        output_dir=args.output_dir,
        checkpoint=args.checkpoint,
        sample_count=args.samples,
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
