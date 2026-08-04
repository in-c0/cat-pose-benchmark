#!/usr/bin/env python3
"""Compare candidate single-camera mirror layouts by first-order geometry.

This is a pre-construction conditioning simulation. It treats each planar reflection as
a virtual camera centre, aims each virtual camera at the capture-volume centre, and
propagates isotropic image-point noise through linear triangulation.

It deliberately does not model mirror ROI boundaries, image parity, reflected-camera
handedness, lens distortion, occlusion, rolling shutter, mirror flatness, or detection
bias. Those are physical Stage 0 measurements, not assumptions to hide in simulation.
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


def reflect_point(
    point: Iterable[float],
    plane_point: Iterable[float],
    plane_normal: Iterable[float],
) -> np.ndarray:
    """Reflect a 3D point across a plane."""
    p = np.asarray(point, dtype=float)
    q = np.asarray(plane_point, dtype=float)
    n = _unit(plane_normal)
    return p - 2.0 * n * float(np.dot(n, p - q))


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


def projection_matrix(
    centre: np.ndarray,
    rotation: np.ndarray,
    intrinsics: tuple[float, float, float, float],
) -> np.ndarray:
    fx, fy, cx, cy = intrinsics
    intrinsic_matrix = np.asarray(
        [[fx, 0.0, cx], [0.0, fy, cy], [0.0, 0.0, 1.0]],
        dtype=float,
    )
    translation = -rotation @ centre
    return intrinsic_matrix @ np.hstack([rotation, translation[:, None]])


def project_point(
    point: np.ndarray,
    centre: np.ndarray,
    rotation: np.ndarray,
    intrinsics: tuple[float, float, float, float],
) -> np.ndarray:
    camera_point = rotation @ (point - centre)
    if camera_point[2] <= 1e-9:
        raise ValueError("Sample point is behind a simulated camera.")

    fx, fy, cx, cy = intrinsics
    return np.asarray(
        [
            fx * camera_point[0] / camera_point[2] + cx,
            fy * camera_point[1] / camera_point[2] + cy,
        ],
        dtype=float,
    )


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
    centres: list[np.ndarray],
    rotations: list[np.ndarray],
    intrinsics: tuple[float, float, float, float],
    pixel_sigma: float,
) -> np.ndarray:
    matrices = [
        projection_matrix(centre, rotation, intrinsics)
        for centre, rotation in zip(centres, rotations)
    ]
    observations = [
        project_point(point, centre, rotation, intrinsics)
        for centre, rotation in zip(centres, rotations)
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


def percentile(values: np.ndarray, amount: float) -> float:
    return float(np.percentile(values, amount))


def summarize_subset(
    points: list[np.ndarray],
    centres: list[np.ndarray],
    names: list[str],
    look_at: np.ndarray,
    intrinsics: tuple[float, float, float, float],
    pixel_sigma: float,
) -> dict[str, Any]:
    rotations = [
        world_to_camera_rotation(centre, look_at)
        for centre in centres
    ]

    radial_std_mm: list[float] = []
    axis_std_mm: list[np.ndarray] = []
    anisotropy: list[float] = []

    for point in points:
        covariance = propagated_covariance(
            point,
            centres,
            rotations,
            intrinsics,
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
    for left_index in range(len(centres)):
        for right_index in range(left_index + 1, len(centres)):
            baselines.append(
                {
                    "views": [names[left_index], names[right_index]],
                    "distance_m": float(
                        np.linalg.norm(centres[left_index] - centres[right_index])
                    ),
                }
            )

    return {
        "views": names,
        "camera_centres_m": {
            name: centre.round(9).tolist()
            for name, centre in zip(names, centres)
        },
        "baselines": baselines,
        "sample_count": len(points),
        "radial_standard_deviation_mm": {
            "median": float(np.median(radial)),
            "p95": percentile(radial, 95.0),
            "max": float(np.max(radial)),
        },
        "axis_standard_deviation_mm": {
            "median_xyz": np.median(axis, axis=0).tolist(),
            "p95_xyz": np.percentile(axis, 95.0, axis=0).tolist(),
        },
        "anisotropy_ratio": {
            "median": float(np.median(anisotropy_values)),
            "p95": percentile(anisotropy_values, 95.0),
            "max": float(np.max(anisotropy_values)),
        },
    }


def evaluate(config: dict[str, Any]) -> dict[str, Any]:
    camera = config["camera"]
    physical_centre = np.asarray(camera["centre_m"], dtype=float)
    look_at = np.asarray(camera["look_at_m"], dtype=float)
    intrinsics = (
        float(camera["fx_px"]),
        float(camera["fy_px"]),
        float(camera["cx_px"]),
        float(camera["cy_px"]),
    )
    pixel_sigma = float(camera["pixel_sigma_px"])
    points = sample_volume(config["capture_volume"])

    layout_reports: dict[str, Any] = {}
    for layout_name, layout in config["layouts"].items():
        reflected: list[tuple[str, np.ndarray]] = []
        for mirror in layout["mirrors"]:
            reflected.append(
                (
                    str(mirror["name"]),
                    reflect_point(
                        physical_centre,
                        mirror["plane_point_m"],
                        mirror["plane_normal"],
                    ),
                )
            )

        subsets: dict[str, Any] = {}
        for mirror_name, mirror_centre in reflected:
            key = f"direct+{mirror_name}"
            subsets[key] = summarize_subset(
                points,
                [physical_centre, mirror_centre],
                ["direct", mirror_name],
                look_at,
                intrinsics,
                pixel_sigma,
            )

        if len(reflected) >= 2:
            names = ["direct"] + [name for name, _ in reflected]
            centres = [physical_centre] + [centre for _, centre in reflected]
            subsets["direct+all_reflections"] = summarize_subset(
                points,
                centres,
                names,
                look_at,
                intrinsics,
                pixel_sigma,
            )

        layout_reports[layout_name] = {
            "description": layout.get("description", ""),
            "subsets": subsets,
        }

    return {
        "schema_version": "0.1.0",
        "warning": (
            "Conditioning simulation only; values are not physical calibration results."
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
