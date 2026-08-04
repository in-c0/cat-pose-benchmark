#!/usr/bin/env python3
"""Compare candidate single-camera mirror layouts by finite-aperture geometry.

The simulator uses the exact planar-reflection projection matrix for each mirror,
including reflected-image parity. It also checks whether each object-to-virtual-camera
ray intersects the finite mirror rectangle and lands inside the physical sensor.

It remains a pre-construction model. It does not model lens distortion, mirror
flatness, mounting flex, occlusion by the animal, reflected-view correspondence error,
rolling shutter, or image-processing bias. Those are physical Stage 0 measurements.
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
from pathlib import Path
from typing import Any, Iterable

import numpy as np


def _unit(vector: Iterable[float]) -> np.ndarray:
    value = np.asarray(vector, dtype=float)
    norm = float(np.linalg.norm(value))
    if norm <= 1e-12:
        raise ValueError("Cannot normalize a zero-length vector.")
    return value / norm


def reflection_affine(
    plane_point: Iterable[float],
    plane_normal: Iterable[float],
) -> tuple[np.ndarray, np.ndarray]:
    """Return S, t for reflected point X' = S X + t."""
    point = np.asarray(plane_point, dtype=float)
    normal = _unit(plane_normal)
    reflection = np.eye(3) - 2.0 * np.outer(normal, normal)
    translation = 2.0 * normal * float(np.dot(normal, point))
    return reflection, translation


def reflect_point(
    point: Iterable[float],
    plane_point: Iterable[float],
    plane_normal: Iterable[float],
) -> np.ndarray:
    reflection, translation = reflection_affine(plane_point, plane_normal)
    return reflection @ np.asarray(point, dtype=float) + translation


def world_to_camera_rotation(
    centre: Iterable[float],
    target: Iterable[float],
) -> np.ndarray:
    """Create a right/down/forward world-to-camera rotation."""
    centre_v = np.asarray(centre, dtype=float)
    target_v = np.asarray(target, dtype=float)
    forward = _unit(target_v - centre_v)

    nominal_up = np.asarray([0.0, 0.0, 1.0])
    if abs(float(np.dot(forward, nominal_up))) > 0.98:
        nominal_up = np.asarray([0.0, 1.0, 0.0])

    right = _unit(np.cross(forward, nominal_up))
    down = np.cross(forward, right)
    return np.vstack([right, down, forward])


def intrinsic_matrix(camera: dict[str, Any]) -> np.ndarray:
    return np.asarray(
        [
            [float(camera["fx_px"]), 0.0, float(camera["cx_px"])],
            [0.0, float(camera["fy_px"]), float(camera["cy_px"])],
            [0.0, 0.0, 1.0],
        ],
        dtype=float,
    )


def direct_projection_matrix(camera: dict[str, Any]) -> np.ndarray:
    centre = np.asarray(camera["centre_m"], dtype=float)
    rotation = world_to_camera_rotation(centre, camera["look_at_m"])
    return intrinsic_matrix(camera) @ np.hstack(
        [rotation, (-rotation @ centre)[:, None]]
    )


def mirror_projection_matrix(
    camera: dict[str, Any],
    mirror: dict[str, Any],
) -> np.ndarray:
    """Map real-world points directly to their physical-sensor mirror pixels."""
    centre = np.asarray(camera["centre_m"], dtype=float)
    rotation = world_to_camera_rotation(centre, camera["look_at_m"])
    reflection, translation = reflection_affine(
        mirror["plane_point_m"],
        mirror["plane_normal"],
    )
    return intrinsic_matrix(camera) @ np.hstack(
        [
            rotation @ reflection,
            (rotation @ (translation - centre))[:, None],
        ]
    )


def project_with_matrix(
    point: np.ndarray,
    matrix: np.ndarray,
) -> tuple[np.ndarray, float]:
    homogeneous = matrix @ np.concatenate([point, [1.0]])
    depth = float(homogeneous[2])
    if abs(depth) <= 1e-12:
        raise ValueError("Point projects at zero homogeneous depth.")
    return homogeneous[:2] / depth, depth


def triangulate(
    observations: list[np.ndarray],
    matrices: list[np.ndarray],
) -> np.ndarray:
    if len(observations) != len(matrices) or len(observations) < 2:
        raise ValueError("Triangulation requires matching observations from >=2 views.")

    rows: list[np.ndarray] = []
    for observation, matrix in zip(observations, matrices):
        u, v = observation
        rows.append(u * matrix[2] - matrix[0])
        rows.append(v * matrix[2] - matrix[1])

    _, _, vh = np.linalg.svd(np.asarray(rows))
    homogeneous = vh[-1]
    if abs(float(homogeneous[3])) <= 1e-12:
        raise ValueError("Degenerate triangulation.")
    return homogeneous[:3] / homogeneous[3]


def propagated_covariance(
    point: np.ndarray,
    matrices: list[np.ndarray],
    pixel_sigma: float,
) -> np.ndarray:
    observations = [
        project_with_matrix(point, matrix)[0]
        for matrix in matrices
    ]
    observation_vector = np.concatenate(observations)

    def reconstruct(vector: np.ndarray) -> np.ndarray:
        split = [
            vector[index : index + 2]
            for index in range(0, len(vector), 2)
        ]
        return triangulate(split, matrices)

    epsilon = 1e-3
    jacobian = np.zeros((3, len(observation_vector)), dtype=float)
    for index in range(len(observation_vector)):
        plus = observation_vector.copy()
        minus = observation_vector.copy()
        plus[index] += epsilon
        minus[index] -= epsilon
        jacobian[:, index] = (
            reconstruct(plus) - reconstruct(minus)
        ) / (2.0 * epsilon)

    image_covariance = np.eye(len(observation_vector)) * pixel_sigma**2
    return jacobian @ image_covariance @ jacobian.T


def sample_volume(volume: dict[str, Any]) -> list[np.ndarray]:
    minimum = np.asarray(volume["min_m"], dtype=float)
    maximum = np.asarray(volume["max_m"], dtype=float)
    counts = [int(value) for value in volume["samples_xyz"]]
    axes = [
        np.linspace(minimum[index], maximum[index], counts[index])
        for index in range(3)
    ]
    return [
        np.asarray(point, dtype=float)
        for point in itertools.product(*axes)
    ]


def mirror_axes(mirror: dict[str, Any]) -> tuple[np.ndarray, np.ndarray]:
    normal = _unit(mirror["plane_normal"])
    vertical = np.asarray(mirror["vertical_axis"], dtype=float)
    in_plane_vertical = vertical - normal * float(np.dot(vertical, normal))
    in_plane_vertical = _unit(in_plane_vertical)
    in_plane_horizontal = _unit(np.cross(in_plane_vertical, normal))
    return in_plane_horizontal, in_plane_vertical


def reflection_point(
    object_point: np.ndarray,
    camera_centre: np.ndarray,
    mirror: dict[str, Any],
) -> tuple[np.ndarray, float]:
    plane_point = np.asarray(mirror["plane_point_m"], dtype=float)
    normal = _unit(mirror["plane_normal"])
    virtual_camera = reflect_point(
        camera_centre,
        plane_point,
        normal,
    )
    denominator = float(np.dot(normal, virtual_camera - object_point))
    if abs(denominator) <= 1e-12:
        raise ValueError("Object-to-virtual-camera ray is parallel to mirror.")
    amount = float(np.dot(normal, plane_point - object_point) / denominator)
    return object_point + amount * (virtual_camera - object_point), amount


def pixel_in_sensor(
    pixel: np.ndarray,
    depth: float,
    resolution: tuple[int, int],
) -> bool:
    width, height = resolution
    return (
        depth > 0.0
        and 0.0 <= float(pixel[0]) < width
        and 0.0 <= float(pixel[1]) < height
    )


def direct_visibility(
    points: list[np.ndarray],
    camera: dict[str, Any],
    matrix: np.ndarray,
) -> tuple[np.ndarray, list[np.ndarray]]:
    resolution = tuple(int(value) for value in camera["resolution_px"])
    visible: list[bool] = []
    pixels: list[np.ndarray] = []
    for point in points:
        pixel, depth = project_with_matrix(point, matrix)
        is_visible = pixel_in_sensor(pixel, depth, resolution)
        visible.append(is_visible)
        pixels.append(pixel)
    return np.asarray(visible, dtype=bool), pixels


def mirror_visibility(
    points: list[np.ndarray],
    camera: dict[str, Any],
    mirror: dict[str, Any],
    matrix: np.ndarray,
) -> tuple[np.ndarray, list[np.ndarray]]:
    resolution = tuple(int(value) for value in camera["resolution_px"])
    centre = np.asarray(camera["centre_m"], dtype=float)
    mirror_centre = np.asarray(mirror["plane_point_m"], dtype=float)
    axis_u, axis_v = mirror_axes(mirror)
    width, height = [float(value) for value in mirror["size_m"]]

    visible: list[bool] = []
    pixels: list[np.ndarray] = []
    for point in points:
        try:
            reflected_point, amount = reflection_point(point, centre, mirror)
            pixel, depth = project_with_matrix(point, matrix)
        except ValueError:
            visible.append(False)
            pixels.append(np.asarray([math.nan, math.nan]))
            continue

        offset = reflected_point - mirror_centre
        inside_aperture = (
            0.0 < amount < 1.0
            and abs(float(np.dot(offset, axis_u))) <= width / 2.0
            and abs(float(np.dot(offset, axis_v))) <= height / 2.0
        )
        is_visible = inside_aperture and pixel_in_sensor(
            pixel,
            depth,
            resolution,
        )
        visible.append(is_visible)
        pixels.append(pixel)

    return np.asarray(visible, dtype=bool), pixels


def roi_bounds(
    pixels: list[np.ndarray],
    visible: np.ndarray,
) -> dict[str, list[float]] | None:
    selected = np.asarray(
        [pixel for pixel, is_visible in zip(pixels, visible) if is_visible],
        dtype=float,
    )
    if selected.size == 0:
        return None
    return {
        "min_xy": np.min(selected, axis=0).tolist(),
        "max_xy": np.max(selected, axis=0).tolist(),
    }


def summarize_subset(
    points: list[np.ndarray],
    view_names: list[str],
    view_matrices: dict[str, np.ndarray],
    view_visibility: dict[str, np.ndarray],
    view_centres: dict[str, np.ndarray],
    pixel_sigma: float,
) -> dict[str, Any]:
    mask = np.logical_and.reduce(
        [view_visibility[name] for name in view_names]
    )
    selected_points = [
        point for point, is_visible in zip(points, mask) if is_visible
    ]
    if not selected_points:
        raise ValueError(f"No common visible points for views: {view_names}")

    matrices = [view_matrices[name] for name in view_names]
    radial_std_mm: list[float] = []
    axis_std_mm: list[np.ndarray] = []
    anisotropy: list[float] = []

    for point in selected_points:
        covariance = propagated_covariance(
            point,
            matrices,
            pixel_sigma,
        )
        eigenvalues = np.maximum(np.linalg.eigvalsh(covariance), 1e-18)
        radial_std_mm.append(math.sqrt(float(np.trace(covariance))) * 1000.0)
        axis_std_mm.append(np.sqrt(np.diag(covariance)) * 1000.0)
        anisotropy.append(math.sqrt(float(eigenvalues[-1] / eigenvalues[0])))

    radial = np.asarray(radial_std_mm)
    axis = np.asarray(axis_std_mm)
    anisotropy_values = np.asarray(anisotropy)

    baselines = []
    for left_index in range(len(view_names)):
        for right_index in range(left_index + 1, len(view_names)):
            left_name = view_names[left_index]
            right_name = view_names[right_index]
            baselines.append(
                {
                    "views": [left_name, right_name],
                    "distance_m": float(
                        np.linalg.norm(
                            view_centres[left_name] - view_centres[right_name]
                        )
                    ),
                }
            )

    return {
        "views": view_names,
        "camera_centres_m": {
            name: view_centres[name].round(9).tolist()
            for name in view_names
        },
        "baselines": baselines,
        "visible_sample_count": len(selected_points),
        "total_sample_count": len(points),
        "coverage_fraction": len(selected_points) / len(points),
        "radial_standard_deviation_mm": {
            "median": float(np.median(radial)),
            "p95": float(np.percentile(radial, 95.0)),
            "max": float(np.max(radial)),
        },
        "axis_standard_deviation_mm": {
            "median_xyz": np.median(axis, axis=0).tolist(),
            "p95_xyz": np.percentile(axis, 95.0, axis=0).tolist(),
        },
        "anisotropy_ratio": {
            "median": float(np.median(anisotropy_values)),
            "p95": float(np.percentile(anisotropy_values, 95.0)),
            "max": float(np.max(anisotropy_values)),
        },
    }


def evaluate(config: dict[str, Any]) -> dict[str, Any]:
    camera = config["camera"]
    pixel_sigma = float(camera["pixel_sigma_px"])
    points = sample_volume(config["capture_volume"])
    camera_centre = np.asarray(camera["centre_m"], dtype=float)

    direct_matrix = direct_projection_matrix(camera)
    direct_mask, direct_pixels = direct_visibility(
        points,
        camera,
        direct_matrix,
    )

    layout_reports: dict[str, Any] = {}
    for layout_name, layout in config["layouts"].items():
        view_matrices: dict[str, np.ndarray] = {"direct": direct_matrix}
        view_visibility: dict[str, np.ndarray] = {"direct": direct_mask}
        view_centres: dict[str, np.ndarray] = {"direct": camera_centre}
        view_reports: dict[str, Any] = {
            "direct": {
                "coverage_fraction": float(np.mean(direct_mask)),
                "visible_sample_count": int(np.sum(direct_mask)),
                "roi_bounds_px": roi_bounds(direct_pixels, direct_mask),
            }
        }

        reflected_names: list[str] = []
        for mirror in layout["mirrors"]:
            name = str(mirror["name"])
            reflected_names.append(name)
            matrix = mirror_projection_matrix(camera, mirror)
            mask, pixels = mirror_visibility(
                points,
                camera,
                mirror,
                matrix,
            )
            view_matrices[name] = matrix
            view_visibility[name] = mask
            virtual_centre = reflect_point(
                camera_centre,
                mirror["plane_point_m"],
                mirror["plane_normal"],
            )
            view_centres[name] = virtual_centre
            view_reports[name] = {
                "coverage_fraction": float(np.mean(mask)),
                "visible_sample_count": int(np.sum(mask)),
                "roi_bounds_px": roi_bounds(pixels, mask),
                "virtual_camera_centre_m": virtual_centre.round(9).tolist(),
            }

        subsets: dict[str, Any] = {}
        for name in reflected_names:
            subsets[f"direct+{name}"] = summarize_subset(
                points,
                ["direct", name],
                view_matrices,
                view_visibility,
                view_centres,
                pixel_sigma,
            )

        subsets["direct+all_reflections"] = summarize_subset(
            points,
            ["direct", *reflected_names],
            view_matrices,
            view_visibility,
            view_centres,
            pixel_sigma,
        )

        layout_reports[layout_name] = {
            "description": layout.get("description", ""),
            "views": view_reports,
            "subsets": subsets,
        }

    return {
        "schema_version": "0.2.0",
        "warning": (
            "Finite-aperture geometry simulation only; values are not physical "
            "calibration results."
        ),
        "assumed_pixel_sigma_px": pixel_sigma,
        "capture_volume": config["capture_volume"],
        "layouts": layout_reports,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("stage0/layouts.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    with args.config.open("r", encoding="utf-8") as handle:
        config = json.load(handle)

    report = evaluate(config)
    serialized = json.dumps(report, indent=2) + "\n"

    if args.output is None:
        print(serialized, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized, encoding="utf-8")
        print(f"Wrote {args.output}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
