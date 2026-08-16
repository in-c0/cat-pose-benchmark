from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw

from detail.ear_mask_geometry import mask_to_ear_geometry


def _load_prompt(path: Path) -> dict[str, Any]:
    prompt = json.loads(path.read_text(encoding="utf-8"))
    if prompt.get("prompt_provenance", {}).get("evidence_tier") != "R3":
        raise ValueError("ear prompt fixture must remain explicitly R3")
    if len(prompt.get("positive_points", [])) != 2:
        raise ValueError("ear prompt requires exactly base and tip positive points")
    if prompt.get("side") not in {"left", "right"}:
        raise ValueError("ear prompt side must be left or right")
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


def _face_centroid(prompt: dict[str, Any]) -> tuple[float, float]:
    points = prompt.get("face_reference_points", [])
    if not points:
        raise ValueError("face_reference_points are required for medial/lateral assignment")
    return (
        sum(float(point["x_px"]) for point in points) / len(points),
        sum(float(point["y_px"]) for point in points) / len(points),
    )


def _candidate(
    mask: np.ndarray,
    score: float,
    prompt: dict[str, Any],
    index: int,
) -> dict[str, Any]:
    positives = prompt["positive_points"]
    negatives = prompt.get("negative_points", [])
    positive_hits = [
        _inside(mask, float(point["x_px"]), float(point["y_px"])) for point in positives
    ]
    negative_hits = [
        _inside(mask, float(point["x_px"]), float(point["y_px"])) for point in negatives
    ]
    diagnostic: dict[str, Any] = {
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
    }

    base = positives[0]
    tip = positives[1]
    try:
        geometry = mask_to_ear_geometry(
            mask,
            base_seed_xy=(float(base["x_px"]), float(base["y_px"])),
            tip_seed_xy=(float(tip["x_px"]), float(tip["y_px"])),
            face_reference_xy=_face_centroid(prompt),
            side=prompt["side"],
            provenance="sam2.1_prompted_ear_mask_proximal_chord_v0",
        )
        diagnostic["geometry_valid"] = True
        diagnostic["geometry"] = geometry
    except Exception as exception:
        diagnostic["geometry_valid"] = False
        diagnostic["geometry_error"] = f"{type(exception).__name__}: {exception}"
    return diagnostic


def _rank(candidate: dict[str, Any]) -> tuple[float, float, int, float, float]:
    # Semantic prompt agreement dominates SAM2's own mask score. For a part target, a
    # smaller valid mask is preferred to a whole-head/whole-cat mask that happens to
    # include the positives.
    return (
        float(candidate["positive_prompt_inside_fraction"]),
        float(candidate["negative_prompt_outside_fraction"]),
        1 if candidate.get("geometry_valid") else 0,
        -float(candidate["mask_area_fraction"]),
        float(candidate["sam2_predicted_iou"]),
    )


def _save_overlay(
    image: Image.Image,
    mask: np.ndarray,
    prompt: dict[str, Any],
    geometry: dict[str, Any],
    path: Path,
) -> None:
    base = image.convert("RGBA")
    tint = Image.new("RGBA", base.size, (255, 0, 0, 0))
    tint.putalpha(Image.fromarray(np.where(mask, 85, 0).astype(np.uint8), mode="L"))
    composed = Image.alpha_composite(base, tint)
    draw = ImageDraw.Draw(composed)

    for point in prompt["positive_points"]:
        x, y = float(point["x_px"]), float(point["y_px"])
        draw.ellipse((x - 6, y - 6, x + 6, y + 6), fill=(0, 255, 0, 255))
    for point in prompt.get("negative_points", []):
        x, y = float(point["x_px"]), float(point["y_px"])
        draw.ellipse((x - 5, y - 5, x + 5, y + 5), fill=(0, 100, 255, 255))

    medial = geometry["base_medial"]
    lateral = geometry["base_lateral"]
    tip = geometry["tip"]
    mx, my = float(medial["x_px"]), float(medial["y_px"])
    lx, ly = float(lateral["x_px"]), float(lateral["y_px"])
    tx, ty = float(tip["x_px"]), float(tip["y_px"])
    center = ((mx + lx) / 2.0, (my + ly) / 2.0)

    draw.line([(mx, my), (lx, ly)], fill=(255, 255, 0, 255), width=4)
    draw.line([center, (tx, ty)], fill=(255, 255, 0, 255), width=3)
    draw.ellipse((mx - 5, my - 5, mx + 5, my + 5), fill=(255, 0, 255, 255))
    draw.ellipse((lx - 5, ly - 5, lx + 5, ly + 5), fill=(0, 255, 255, 255))
    draw.ellipse((tx - 5, ty - 5, tx + 5, ty + 5), fill=(255, 255, 0, 255))

    composed.convert("RGB").save(path, quality=95)


def run(
    *,
    image_path: Path,
    prompt_path: Path,
    output_dir: Path,
    checkpoint: str,
    device: str,
) -> dict[str, Any]:
    try:
        from sam2.sam2_image_predictor import SAM2ImagePredictor
    except ImportError as exception:
        raise RuntimeError("SAM2 is required for the ear segmentation experiment") from exception

    prompt = _load_prompt(prompt_path)
    image = Image.open(image_path).convert("RGB")
    expected_size = (
        int(prompt["source_frame"]["width_px"]),
        int(prompt["source_frame"]["height_px"]),
    )
    if image.size != expected_size:
        raise ValueError(f"image size {image.size} does not match prompt metadata {expected_size}")

    point_coords, point_labels = _prompt_arrays(prompt)
    predictor = SAM2ImagePredictor.from_pretrained(checkpoint, device=device)
    predictor.set_image(np.asarray(image))
    masks, scores, _logits = predictor.predict(
        point_coords=point_coords,
        point_labels=point_labels,
        multimask_output=True,
    )

    boolean_masks = np.asarray(masks).astype(bool)
    score_values = np.asarray(scores).reshape(-1)
    if boolean_masks.ndim != 3 or len(boolean_masks) == 0:
        raise RuntimeError(f"unexpected SAM2 mask output shape: {boolean_masks.shape}")
    if len(boolean_masks) != len(score_values):
        raise RuntimeError("SAM2 mask/score count mismatch")

    candidates = [
        _candidate(mask, float(score_values[index]), prompt, index)
        for index, mask in enumerate(boolean_masks)
    ]
    chosen_index = max(range(len(candidates)), key=lambda index: _rank(candidates[index]))
    chosen = candidates[chosen_index]
    if not chosen.get("geometry_valid"):
        raise RuntimeError(f"chosen SAM2 candidate has no valid ear geometry: {chosen}")
    chosen_mask = boolean_masks[chosen_index]
    geometry = chosen["geometry"]

    output_dir.mkdir(parents=True, exist_ok=True)
    np.save(output_dir / "ear-mask.npy", chosen_mask.astype(np.uint8))
    Image.fromarray((chosen_mask.astype(np.uint8) * 255), mode="L").save(
        output_dir / "ear-mask.png"
    )
    _save_overlay(image, chosen_mask, prompt, geometry, output_dir / "ear-overlay.jpg")

    result = {
        "schema_version": "0.1.0",
        "clip_id": prompt["clip_id"],
        "side": prompt["side"],
        "checkpoint": checkpoint,
        "device": device,
        "evidence_tier": "R3",
        "chosen_candidate": chosen,
        "all_candidates": candidates,
        "ear": geometry,
        "scientific_boundary": (
            "Model-derived segmentation and geometry only. This experiment asks whether "
            "visible image-space ear base corners can be recovered compositionally; it "
            "does not establish independent accuracy or a 3D ear plane."
        ),
    }
    (output_dir / "ear-result.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Prompt SAM2 for an ear-only mask and derive base geometry.")
    parser.add_argument("image", type=Path)
    parser.add_argument("prompt", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--checkpoint", default="facebook/sam2.1-hiera-tiny")
    parser.add_argument("--device", default="cpu")
    args = parser.parse_args()

    result = run(
        image_path=args.image,
        prompt_path=args.prompt,
        output_dir=args.output_dir,
        checkpoint=args.checkpoint,
        device=args.device,
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
