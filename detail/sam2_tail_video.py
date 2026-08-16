from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw

from detail.mask_centerline import mask_to_tail_samples


def _load_prompt(path: Path) -> dict[str, Any]:
    prompt = json.loads(path.read_text(encoding="utf-8"))
    provenance = prompt.get("prompt_provenance", {})
    if provenance.get("evidence_tier") != "R3":
        raise ValueError("Frozen video-propagation seed must remain explicitly R3")
    if len(prompt.get("positive_points", [])) < 2:
        raise ValueError("Tail base and tail tip positive prompts are required")
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


def _curve_xy(samples: list[dict[str, Any]]) -> list[tuple[float, float]]:
    return [(float(sample["x_px"]), float(sample["y_px"])) for sample in samples]


def _curve_length(samples: list[dict[str, Any]]) -> float:
    points = _curve_xy(samples)
    return sum(
        math.hypot(right[0] - left[0], right[1] - left[1])
        for left, right in zip(points, points[1:])
    )


def _distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _mask_from_logits(mask_logits: Any) -> np.ndarray:
    tensor = mask_logits
    if hasattr(tensor, "detach"):
        tensor = tensor.detach()
    if hasattr(tensor, "cpu"):
        tensor = tensor.cpu()
    values = np.asarray(tensor)
    while values.ndim > 2:
        values = values[0]
    if values.ndim != 2:
        raise ValueError(f"Unexpected propagated mask shape: {values.shape}")
    return values > 0.0


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


def _render_overlay(
    image_path: Path,
    mask: np.ndarray,
    samples: list[dict[str, Any]],
    output_path: Path,
    *,
    prompt: dict[str, Any] | None = None,
    label: str | None = None,
) -> None:
    image = Image.open(image_path).convert("RGBA")
    tint = Image.new("RGBA", image.size, (255, 0, 0, 0))
    tint.putalpha(Image.fromarray(np.where(mask, 75, 0).astype(np.uint8), mode="L"))
    composed = Image.alpha_composite(image, tint)
    draw = ImageDraw.Draw(composed)

    curve = _curve_xy(samples)
    if len(curve) >= 2:
        draw.line(curve, fill=(255, 255, 0, 255), width=4)
    for x, y in curve:
        draw.ellipse((x - 2, y - 2, x + 2, y + 2), fill=(255, 255, 0, 255))

    if prompt:
        for point in prompt.get("positive_points", []):
            x, y = float(point["x_px"]), float(point["y_px"])
            draw.ellipse((x - 5, y - 5, x + 5, y + 5), fill=(0, 255, 0, 255))
        for point in prompt.get("negative_points", []):
            x, y = float(point["x_px"]), float(point["y_px"])
            draw.ellipse((x - 5, y - 5, x + 5, y + 5), fill=(0, 110, 255, 255))

    if label:
        draw.rectangle((8, 8, 280, 36), fill=(0, 0, 0, 170))
        draw.text((14, 13), label, fill=(255, 255, 255, 255))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    composed.convert("RGB").save(output_path, quality=92)


def _make_contact_sheet(
    overlay_paths: list[Path], output_path: Path, *, columns: int = 4, thumb_width: int = 480
) -> None:
    images = [Image.open(path).convert("RGB") for path in overlay_paths]
    if not images:
        return
    ratio = images[0].height / images[0].width
    thumb_height = max(1, int(round(thumb_width * ratio)))
    rows = math.ceil(len(images) / columns)
    sheet = Image.new("RGB", (thumb_width * columns, thumb_height * rows), "black")
    for index, image in enumerate(images):
        thumb = image.resize((thumb_width, thumb_height))
        x = (index % columns) * thumb_width
        y = (index // columns) * thumb_height
        sheet.paste(thumb, (x, y))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output_path, quality=92)


def _track_direction(
    predictor: Any,
    state: Any,
    *,
    frames_dir: Path,
    frame_names: list[str],
    start_frame_idx: int,
    reverse: bool,
    initial_base_xy: tuple[float, float],
    sample_count: int,
    prompt: dict[str, Any],
    output_dir: Path,
) -> dict[int, dict[str, Any]]:
    results: dict[int, dict[str, Any]] = {}
    previous_base = initial_base_xy
    previous_tip: tuple[float, float] | None = None
    image_diagonal = math.hypot(
        float(prompt["source_frame"]["width_px"]),
        float(prompt["source_frame"]["height_px"]),
    )

    for frame_idx, _obj_ids, mask_logits in predictor.propagate_in_video(
        state,
        start_frame_idx=start_frame_idx,
        reverse=reverse,
    ):
        mask = _mask_from_logits(mask_logits)
        record: dict[str, Any] = {
            "frame_index": int(frame_idx),
            "mask_area_px": int(mask.sum()),
            "mask_area_fraction": float(mask.mean()),
            "direction": "reverse" if reverse else "forward",
        }
        try:
            samples = mask_to_tail_samples(
                mask,
                base_xy=previous_base,
                sample_count=sample_count,
                provenance="sam2.1_video_propagated_mask_to_skeleton_v0",
            )
            root = (float(samples[0]["x_px"]), float(samples[0]["y_px"]))
            tip = (float(samples[-1]["x_px"]), float(samples[-1]["y_px"]))
            record.update(
                {
                    "curve_status": "ok",
                    "curve": {"samples": samples},
                    "curve_length_px": _curve_length(samples),
                    "root_xy": [root[0], root[1]],
                    "tip_xy": [tip[0], tip[1]],
                    "root_step_fraction": _distance(root, previous_base) / image_diagonal,
                    "tip_step_fraction": (
                        _distance(tip, previous_tip) / image_diagonal
                        if previous_tip is not None
                        else None
                    ),
                }
            )
            previous_base = root
            previous_tip = tip
            overlay_path = output_dir / "overlays" / f"{int(frame_idx):05d}.jpg"
            _render_overlay(
                frames_dir / frame_names[int(frame_idx)],
                mask,
                samples,
                overlay_path,
                prompt=prompt if int(frame_idx) == start_frame_idx else None,
                label=f"frame {int(frame_idx)} | {'rev' if reverse else 'fwd'}",
            )
            record["overlay"] = str(overlay_path.name)
        except Exception as exception:  # failure discovery is part of the experiment
            record.update(
                {
                    "curve_status": "failed",
                    "curve_error": f"{type(exception).__name__}: {exception}",
                }
            )
        results[int(frame_idx)] = record
    return results


def _summary(
    records: list[dict[str, Any]], *, seed_frame_idx: int, image_diagonal: float
) -> dict[str, Any]:
    successful = [record for record in records if record.get("curve_status") == "ok"]
    seed = next((record for record in successful if record["frame_index"] == seed_frame_idx), None)
    seed_area = float(seed["mask_area_fraction"]) if seed else None

    chronological_root_steps: list[float] = []
    chronological_tip_steps: list[float] = []
    previous: dict[str, Any] | None = None
    for record in successful:
        if previous is not None and record["frame_index"] == previous["frame_index"] + 1:
            root = tuple(record["root_xy"])
            prior_root = tuple(previous["root_xy"])
            tip = tuple(record["tip_xy"])
            prior_tip = tuple(previous["tip_xy"])
            chronological_root_steps.append(_distance(root, prior_root) / image_diagonal)
            chronological_tip_steps.append(_distance(tip, prior_tip) / image_diagonal)
        previous = record

    suspicious_expansions = []
    if seed_area is not None and seed_area > 0:
        threshold = max(0.02, seed_area * 5.0)
        suspicious_expansions = [
            record["frame_index"]
            for record in records
            if float(record["mask_area_fraction"]) > threshold
        ]
    else:
        threshold = None

    coverage = len(successful) / len(records) if records else 0.0
    return {
        "frames_total": len(records),
        "frames_with_curve": len(successful),
        "curve_coverage": coverage,
        "frames_failed": [
            record["frame_index"]
            for record in records
            if record.get("curve_status") != "ok"
        ],
        "seed_mask_area_fraction": seed_area,
        "suspicious_expansion_threshold": threshold,
        "suspicious_expansion_frames": suspicious_expansions,
        "mean_chronological_root_step_fraction": (
            float(np.mean(chronological_root_steps)) if chronological_root_steps else None
        ),
        "max_chronological_root_step_fraction": (
            float(np.max(chronological_root_steps)) if chronological_root_steps else None
        ),
        "mean_chronological_tip_step_fraction": (
            float(np.mean(chronological_tip_steps)) if chronological_tip_steps else None
        ),
        "max_chronological_tip_step_fraction": (
            float(np.max(chronological_tip_steps)) if chronological_tip_steps else None
        ),
        "engineering_feasibility": (
            "pass"
            if coverage >= 0.75 and not suspicious_expansions
            else "revise"
        ),
        "interpretation_boundary": (
            "Curve coverage and temporal displacement are failure-discovery metrics, not "
            "landmark accuracy. Inter-frame displacement contains true cat motion and "
            "projection change. Numerical accuracy requires independent visible-tail labels."
        ),
    }


def run(
    *,
    frames_dir: Path,
    prompt_path: Path,
    output_dir: Path,
    checkpoint: str,
    device: str,
    sample_count: int,
) -> dict[str, Any]:
    try:
        from sam2.sam2_video_predictor import SAM2VideoPredictor
    except ImportError as exception:
        raise RuntimeError("SAM2 is required for video propagation") from exception

    prompt = _load_prompt(prompt_path)
    frame_names = _frame_names(frames_dir)
    seed_frame_idx = int(prompt["source_frame"]["smoke_frame_index"])
    if not (0 <= seed_frame_idx < len(frame_names)):
        raise ValueError(
            f"Seed frame {seed_frame_idx} outside frame sequence of length {len(frame_names)}"
        )

    seed_image = Image.open(frames_dir / frame_names[seed_frame_idx])
    expected_size = (
        int(prompt["source_frame"]["width_px"]),
        int(prompt["source_frame"]["height_px"]),
    )
    if seed_image.size != expected_size:
        raise ValueError(f"Seed image size {seed_image.size} != expected {expected_size}")

    predictor = SAM2VideoPredictor.from_pretrained(checkpoint, device=device)
    state = predictor.init_state(
        str(frames_dir),
        offload_video_to_cpu=True,
        offload_state_to_cpu=True,
        async_loading_frames=False,
    )
    points, labels = _prompt_arrays(prompt)
    predictor.add_new_points_or_box(
        state,
        frame_idx=seed_frame_idx,
        obj_id=1,
        points=points,
        labels=labels,
        clear_old_points=True,
    )

    seed_base = (
        float(prompt["positive_points"][0]["x_px"]),
        float(prompt["positive_points"][0]["y_px"]),
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    forward = _track_direction(
        predictor,
        state,
        frames_dir=frames_dir,
        frame_names=frame_names,
        start_frame_idx=seed_frame_idx,
        reverse=False,
        initial_base_xy=seed_base,
        sample_count=sample_count,
        prompt=prompt,
        output_dir=output_dir,
    )
    reverse = _track_direction(
        predictor,
        state,
        frames_dir=frames_dir,
        frame_names=frame_names,
        start_frame_idx=seed_frame_idx,
        reverse=True,
        initial_base_xy=seed_base,
        sample_count=sample_count,
        prompt=prompt,
        output_dir=output_dir,
    )

    combined = dict(reverse)
    combined.update(forward)  # forward owns the duplicate seed frame
    records = [combined[index] for index in sorted(combined)]
    image_diagonal = math.hypot(expected_size[0], expected_size[1])
    summary = _summary(records, seed_frame_idx=seed_frame_idx, image_diagonal=image_diagonal)

    overlay_paths = [
        output_dir / "overlays" / f"{record['frame_index']:05d}.jpg"
        for record in records
        if record.get("curve_status") == "ok"
    ]
    _make_contact_sheet(overlay_paths, output_dir / "sequence-overlay.jpg")

    payload = {
        "schema_version": "0.1.0",
        "clip_id": prompt["clip_id"],
        "checkpoint": checkpoint,
        "device": device,
        "seed_frame_index": seed_frame_idx,
        "seed_provenance": prompt["prompt_provenance"],
        "evidence_tier": "R3",
        "frames": records,
        "summary": summary,
        "scientific_boundary": (
            "All masks and curves are model-derived R3 evidence. A temporal feasibility "
            "pass does not establish visible-tail accuracy or clear derived labels for product training."
        ),
    }
    (output_dir / "sequence-result.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Propagate one automatic tail seed through a JPEG sequence with SAM2."
    )
    parser.add_argument("frames_dir", type=Path)
    parser.add_argument("prompt", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--checkpoint", default="facebook/sam2.1-hiera-tiny")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--samples", type=int, default=24)
    args = parser.parse_args()

    result = run(
        frames_dir=args.frames_dir,
        prompt_path=args.prompt,
        output_dir=args.output_dir,
        checkpoint=args.checkpoint,
        device=args.device,
        sample_count=args.samples,
    )
    print(json.dumps(result["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
