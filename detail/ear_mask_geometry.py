from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import numpy as np


def _nearest_mask_xy(mask: np.ndarray, point_xy: tuple[float, float]) -> tuple[float, float]:
    pixels = np.argwhere(mask.astype(bool))
    if len(pixels) == 0:
        raise ValueError("ear mask is empty")
    x, y = point_xy
    distances = (pixels[:, 1] - x) ** 2 + (pixels[:, 0] - y) ** 2
    row, col = pixels[int(np.argmin(distances))]
    return float(col), float(row)


def _inside(mask: np.ndarray, x: float, y: float) -> bool:
    row = int(round(y))
    col = int(round(x))
    return 0 <= row < mask.shape[0] and 0 <= col < mask.shape[1] and bool(mask[row, col])


def _chord(
    mask: np.ndarray,
    center: tuple[float, float],
    normal: tuple[float, float],
    *,
    max_distance: float,
    step: float = 0.5,
) -> tuple[tuple[float, float], tuple[float, float], float] | None:
    cx, cy = center
    if not _inside(mask, cx, cy):
        projected = _nearest_mask_xy(mask, center)
        if math.hypot(projected[0] - cx, projected[1] - cy) > 3.0:
            return None
        cx, cy = projected

    endpoints: list[tuple[float, float]] = []
    for sign in (-1.0, 1.0):
        last = (cx, cy)
        travelled = step
        while travelled <= max_distance:
            x = cx + sign * normal[0] * travelled
            y = cy + sign * normal[1] * travelled
            if not _inside(mask, x, y):
                break
            last = (x, y)
            travelled += step
        endpoints.append(last)

    left, right = endpoints
    width = math.hypot(right[0] - left[0], right[1] - left[1])
    if width < 1.0:
        return None
    return left, right, width


def mask_to_ear_geometry(
    mask: np.ndarray,
    *,
    base_seed_xy: tuple[float, float],
    tip_seed_xy: tuple[float, float],
    face_reference_xy: tuple[float, float],
    side: str,
    provenance: str = "ear_mask_proximal_chord_v0",
) -> dict[str, Any]:
    """Derive visible 2D ear base corners from an ear-only binary mask.

    The upstream animal model supplies only a base midpoint and tip. This baseline uses
    those points as R3 semantic anchors, not as independent truth. A proximal chord
    perpendicular to the base-to-tip axis estimates the two visible base endpoints.

    `base_medial` is the endpoint closer to a face-reference centroid; `base_lateral`
    is the farther endpoint. No latent cartilage or unique 3D ear plane is inferred.
    """

    if side not in {"left", "right"}:
        raise ValueError("side must be 'left' or 'right'")
    if mask.ndim != 2:
        raise ValueError("ear mask must be a 2D array")
    binary = mask.astype(bool)
    if not binary.any():
        raise ValueError("ear mask is empty")

    base_anchor = _nearest_mask_xy(binary, base_seed_xy)
    tip_anchor = _nearest_mask_xy(binary, tip_seed_xy)
    dx = tip_anchor[0] - base_anchor[0]
    dy = tip_anchor[1] - base_anchor[1]
    anchor_length = math.hypot(dx, dy)
    if anchor_length < 3.0:
        raise ValueError("ear base/tip anchors are too close for stable geometry")

    axis = (dx / anchor_length, dy / anchor_length)
    normal = (-axis[1], axis[0])

    # Search slightly toward the face from the supplied base midpoint and through the
    # proximal third of the visible ear. The widest valid perpendicular chord is the
    # engineering estimate of the visible ear attachment/base line.
    best: tuple[tuple[float, float], tuple[float, float], float, float] | None = None
    for fraction in np.linspace(-0.18, 0.32, 21):
        offset = float(fraction) * anchor_length
        center = (
            base_anchor[0] + axis[0] * offset,
            base_anchor[1] + axis[1] * offset,
        )
        chord = _chord(
            binary,
            center,
            normal,
            max_distance=max(8.0, anchor_length),
        )
        if chord is None:
            continue
        endpoint_a, endpoint_b, width = chord
        if best is None or width > best[2]:
            best = (endpoint_a, endpoint_b, width, fraction)

    if best is None:
        raise ValueError("could not find a stable proximal ear-mask chord")

    endpoint_a, endpoint_b, base_width, base_fraction = best
    fx, fy = face_reference_xy
    distance_a = math.hypot(endpoint_a[0] - fx, endpoint_a[1] - fy)
    distance_b = math.hypot(endpoint_b[0] - fx, endpoint_b[1] - fy)
    if distance_a <= distance_b:
        medial, lateral = endpoint_a, endpoint_b
    else:
        medial, lateral = endpoint_b, endpoint_a

    derived_base_center = (
        (medial[0] + lateral[0]) / 2.0,
        (medial[1] + lateral[1]) / 2.0,
    )
    visible_length = math.hypot(
        tip_anchor[0] - derived_base_center[0],
        tip_anchor[1] - derived_base_center[1],
    )
    if visible_length < 3.0:
        raise ValueError("derived visible ear length is too small")

    triangle_area = abs(
        (lateral[0] - medial[0]) * (tip_anchor[1] - medial[1])
        - (lateral[1] - medial[1]) * (tip_anchor[0] - medial[0])
    ) / 2.0

    return {
        "side": side,
        "base_medial": {
            "x_px": medial[0],
            "y_px": medial[1],
            "visibility": "visible",
            "confidence": 1.0,
            "provenance": provenance,
        },
        "base_lateral": {
            "x_px": lateral[0],
            "y_px": lateral[1],
            "visibility": "visible",
            "confidence": 1.0,
            "provenance": provenance,
        },
        "tip": {
            "x_px": tip_anchor[0],
            "y_px": tip_anchor[1],
            "visibility": "visible",
            "confidence": 1.0,
            "provenance": provenance,
        },
        "diagnostics": {
            "teacher_base_seed_xy": [float(base_seed_xy[0]), float(base_seed_xy[1])],
            "teacher_tip_seed_xy": [float(tip_seed_xy[0]), float(tip_seed_xy[1])],
            "projected_base_anchor_xy": [base_anchor[0], base_anchor[1]],
            "projected_tip_anchor_xy": [tip_anchor[0], tip_anchor[1]],
            "derived_base_center_xy": [derived_base_center[0], derived_base_center[1]],
            "base_chord_fraction_from_teacher_base": base_fraction,
            "base_width_px": base_width,
            "visible_length_px": visible_length,
            "width_to_length_ratio": base_width / visible_length,
            "triangle_area_px2": triangle_area,
            "mask_area_px": int(binary.sum()),
            "representation_boundary": (
                "Visible image-space surface geometry only. Medial/lateral naming uses "
                "distance to a face-reference centroid; no 3D ear plane is asserted."
            ),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Derive visible ear base geometry from a binary mask.")
    parser.add_argument("mask_npy", type=Path)
    parser.add_argument("--base-x", type=float, required=True)
    parser.add_argument("--base-y", type=float, required=True)
    parser.add_argument("--tip-x", type=float, required=True)
    parser.add_argument("--tip-y", type=float, required=True)
    parser.add_argument("--face-x", type=float, required=True)
    parser.add_argument("--face-y", type=float, required=True)
    parser.add_argument("--side", choices=["left", "right"], required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    geometry = mask_to_ear_geometry(
        np.load(args.mask_npy),
        base_seed_xy=(args.base_x, args.base_y),
        tip_seed_xy=(args.tip_x, args.tip_y),
        face_reference_xy=(args.face_x, args.face_y),
        side=args.side,
    )
    rendered = json.dumps(geometry, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
