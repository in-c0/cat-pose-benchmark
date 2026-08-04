#!/usr/bin/env python3
"""Independent Python reference for the Unity Stage S0 procedural exporter.

This module duplicates the declared procedural motion and pinhole camera equations using
only Python's standard library. It is intentionally independent of Unity serialization
and is used to detect transform, projection, timing, or topology drift in a generated
Unity fixture.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

from synthetic.validate_sequence import validate_sequence


SEED = 17
FRAME_COUNT = 5
FIXED_TIMESTEP_NS = 100_000_000
IMAGE_WIDTH = 640
IMAGE_HEIGHT = 480
VERTICAL_FOV_DEGREES = 60.0
SEQUENCE_ID = "stage-s0-proxy-v0"
SUBJECT_ID = "proxy-cat-001"
EXPORTER_VERSION = "StageS0SyntheticExporter-v0.2"
CAMERA_POSITION = (0.0, 1.1, -3.0)
CAMERA_LOOK_AT = (0.0, 0.4, 0.0)
WORLD_UP = (0.0, 1.0, 0.0)

STATIC_LANDMARKS: tuple[tuple[str, tuple[float, float, float]], ...] = (
    ("nose", (0.0, 0.55, 0.65)),
    ("left_ear_tip", (-0.16, 0.82, 0.48)),
    ("right_ear_tip", (0.16, 0.82, 0.48)),
    ("left_front_paw", (-0.18, 0.0, 0.38)),
    ("right_front_paw", (0.18, 0.0, 0.38)),
    ("left_hind_paw", (-0.18, 0.0, -0.35)),
    ("right_hind_paw", (0.18, 0.0, -0.35)),
    ("tail_base", (0.0, 0.35, -0.55)),
)


def _add(
    left: tuple[float, float, float],
    right: tuple[float, float, float],
) -> tuple[float, float, float]:
    return tuple(a + b for a, b in zip(left, right))  # type: ignore[return-value]


def _subtract(
    left: tuple[float, float, float],
    right: tuple[float, float, float],
) -> tuple[float, float, float]:
    return tuple(a - b for a, b in zip(left, right))  # type: ignore[return-value]


def _dot(
    left: tuple[float, float, float],
    right: tuple[float, float, float],
) -> float:
    return sum(a * b for a, b in zip(left, right))


def _cross(
    left: tuple[float, float, float],
    right: tuple[float, float, float],
) -> tuple[float, float, float]:
    return (
        left[1] * right[2] - left[2] * right[1],
        left[2] * right[0] - left[0] * right[2],
        left[0] * right[1] - left[1] * right[0],
    )


def _normalize(vector: tuple[float, float, float]) -> tuple[float, float, float]:
    length = math.sqrt(_dot(vector, vector))
    if length <= 0.0:
        raise ValueError("Cannot normalize a zero-length vector")
    return tuple(value / length for value in vector)  # type: ignore[return-value]


def _vec3(values: tuple[float, float, float]) -> dict[str, float]:
    return {"x": values[0], "y": values[1], "z": values[2]}


def _vec2(values: tuple[float, float]) -> dict[str, float]:
    return {"x": values[0], "y": values[1]}


def camera_basis() -> tuple[
    tuple[float, float, float],
    tuple[float, float, float],
    tuple[float, float, float],
]:
    """Return Unity-compatible right, up, and forward camera axes in world space."""

    forward = _normalize(_subtract(CAMERA_LOOK_AT, CAMERA_POSITION))
    right = _normalize(_cross(WORLD_UP, forward))
    up = _cross(forward, right)
    return right, up, forward


def world_to_camera(
    world: tuple[float, float, float],
) -> tuple[float, float, float]:
    right, up, forward = camera_basis()
    delta = _subtract(world, CAMERA_POSITION)
    return (_dot(delta, right), _dot(delta, up), _dot(delta, forward))


def camera_to_image(
    camera: tuple[float, float, float],
) -> tuple[float, float]:
    x, y, z = camera
    if z == 0.0:
        return (math.copysign(math.inf, x), math.copysign(math.inf, y))
    tangent = math.tan(math.radians(VERTICAL_FOV_DEGREES) / 2.0)
    aspect = IMAGE_WIDTH / IMAGE_HEIGHT
    normalized_x = x / (z * tangent * aspect)
    normalized_y = y / (z * tangent)
    return (
        (normalized_x + 1.0) * 0.5 * IMAGE_WIDTH,
        (normalized_y + 1.0) * 0.5 * IMAGE_HEIGHT,
    )


def project_landmark(
    name: str,
    world: tuple[float, float, float],
) -> dict[str, Any]:
    camera = world_to_camera(world)
    image = camera_to_image(camera)
    visible = (
        camera[2] > 0.0
        and 0.0 <= image[0] <= IMAGE_WIDTH
        and 0.0 <= image[1] <= IMAGE_HEIGHT
    )
    return {
        "semantic_name": name,
        "world_m": _vec3(world),
        "camera_m": _vec3(camera),
        "image_px": _vec2(image),
        "visibility": "visible" if visible else "out_of_frame",
    }


def generate_reference(required_editor: str = "6000.0.75f1") -> dict[str, Any]:
    frames: list[dict[str, Any]] = []
    for frame_index in range(FRAME_COUNT):
        root = (0.02 * frame_index, 0.0, 0.0)
        landmarks = [
            project_landmark(name, _add(root, local))
            for name, local in STATIC_LANDMARKS
        ]

        swing = math.sin(0.7 * frame_index)
        tail_curve = (
            _add(root, (0.0, 0.35, -0.55)),
            _add(root, (0.05 * swing, 0.42, -0.80)),
            _add(root, (0.12 * swing, 0.48, -1.00)),
            _add(root, (0.20 * swing, 0.55, -1.15)),
        )
        landmarks.append(project_landmark("tail_tip", tail_curve[-1]))

        frames.append(
            {
                "frame_index": frame_index,
                "timestamp_ns": frame_index * FIXED_TIMESTEP_NS,
                "subject_root_world_m": _vec3(root),
                "subject_velocity_world_mps": _vec3((0.2, 0.0, 0.0)),
                "landmarks": landmarks,
                "tail_curve_world_m": [_vec3(point) for point in tail_curve],
                "contacts": [
                    {
                        "semantic_name": name,
                        "active": True,
                        "support_surface_id": "floor",
                    }
                    for name in (
                        "left_front_paw_contact",
                        "right_front_paw_contact",
                        "left_hind_paw_contact",
                        "right_hind_paw_contact",
                    )
                ],
                "spatial_relations": [
                    {
                        "subject_id": SUBJECT_ID,
                        "relation": "on",
                        "object_id": "floor",
                    }
                ],
            }
        )

    return {
        "schema_version": "0.1.0",
        "sequence_id": SEQUENCE_ID,
        "subject_id": SUBJECT_ID,
        "evidence_tier": "S",
        "quality": "gold",
        "units": "metres",
        "engine": {
            "name": "Unity",
            "project": "cat-pose-benchmark/unity-viewer",
            "required_editor": required_editor,
            "exporter": EXPORTER_VERSION,
        },
        "determinism": {
            "seed": SEED,
            "fixed_timestep_ns": FIXED_TIMESTEP_NS,
            "frame_count": FRAME_COUNT,
            "coordinate_convention": "unity-left-handed-x-right-y-up-z-forward",
        },
        "camera": {
            "camera_id": "synthetic-camera-0",
            "resolution_px": [IMAGE_WIDTH, IMAGE_HEIGHT],
            "vertical_fov_degrees": VERTICAL_FOV_DEGREES,
            "position_world_m": _vec3(CAMERA_POSITION),
            "look_at_world_m": _vec3(CAMERA_LOOK_AT),
            "screen_origin": "bottom_left",
        },
        "scene": {
            "support_surfaces": [
                {
                    "object_id": "floor",
                    "plane_world": {
                        "normal": _vec3(WORLD_UP),
                        "offset_m": 0.0,
                    },
                }
            ],
            "objects": [
                {
                    "object_id": "box-left",
                    "type": "box",
                    "position_world_m": _vec3((-0.8, 0.25, 0.4)),
                },
                {
                    "object_id": "box-right",
                    "type": "box",
                    "position_world_m": _vec3((0.8, 0.25, 0.4)),
                },
            ],
        },
        "lineage": [
            "generator:procedural-proxy-v0.2",
            f"seed:{SEED}",
            f"fixed-timestep-ns:{FIXED_TIMESTEP_NS}",
        ],
        "frames": frames,
    }


def compare_values(
    expected: Any,
    actual: Any,
    *,
    path: str = "<root>",
    abs_tol: float = 2e-5,
    rel_tol: float = 2e-5,
) -> list[str]:
    errors: list[str] = []
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return [f"{path}: expected object, got {type(actual).__name__}"]
        expected_keys = set(expected)
        actual_keys = set(actual)
        for missing in sorted(expected_keys - actual_keys):
            errors.append(f"{path}: missing key {missing}")
        for extra in sorted(actual_keys - expected_keys):
            errors.append(f"{path}: unexpected key {extra}")
        for key in sorted(expected_keys & actual_keys):
            errors.extend(
                compare_values(
                    expected[key],
                    actual[key],
                    path=f"{path}.{key}",
                    abs_tol=abs_tol,
                    rel_tol=rel_tol,
                )
            )
        return errors

    if isinstance(expected, list):
        if not isinstance(actual, list):
            return [f"{path}: expected array, got {type(actual).__name__}"]
        if len(expected) != len(actual):
            errors.append(
                f"{path}: expected {len(expected)} elements, got {len(actual)}"
            )
        for index, (expected_item, actual_item) in enumerate(zip(expected, actual)):
            errors.extend(
                compare_values(
                    expected_item,
                    actual_item,
                    path=f"{path}[{index}]",
                    abs_tol=abs_tol,
                    rel_tol=rel_tol,
                )
            )
        return errors

    if isinstance(expected, bool) or isinstance(actual, bool):
        if expected is not actual:
            errors.append(f"{path}: expected {expected!r}, got {actual!r}")
        return errors

    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        if not math.isclose(
            float(expected),
            float(actual),
            rel_tol=rel_tol,
            abs_tol=abs_tol,
        ):
            errors.append(f"{path}: expected {expected!r}, got {actual!r}")
        return errors

    if expected != actual:
        errors.append(f"{path}: expected {expected!r}, got {actual!r}")
    return errors


def editor_version(project_version_path: Path) -> str:
    for line in project_version_path.read_text(encoding="utf-8").splitlines():
        key, separator, value = line.partition(":")
        if separator and key.strip() == "m_EditorVersion":
            version = value.strip()
            if version:
                return version
    raise ValueError(f"No m_EditorVersion found in {project_version_path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("unity_export", type=Path)
    parser.add_argument(
        "--schema",
        type=Path,
        default=Path(__file__).parents[1]
        / "schemas"
        / "synthetic-sequence.schema.json",
    )
    parser.add_argument(
        "--project-version",
        type=Path,
        default=Path(__file__).parents[1]
        / "unity-viewer"
        / "ProjectSettings"
        / "ProjectVersion.txt",
    )
    parser.add_argument("--abs-tol", type=float, default=2e-5)
    parser.add_argument("--rel-tol", type=float, default=2e-5)
    args = parser.parse_args()

    actual = json.loads(args.unity_export.read_text(encoding="utf-8"))
    schema = json.loads(args.schema.read_text(encoding="utf-8"))
    validation_errors = validate_sequence(actual, schema)
    if validation_errors:
        for error in validation_errors:
            print(f"ERROR: {error}")
        raise SystemExit(1)

    expected = generate_reference(editor_version(args.project_version))
    comparison_errors = compare_values(
        expected,
        actual,
        abs_tol=args.abs_tol,
        rel_tol=args.rel_tol,
    )
    if comparison_errors:
        for error in comparison_errors:
            print(f"ERROR: {error}")
        raise SystemExit(1)

    print(f"Unity export matches independent Python reference: {args.unity_export}")


if __name__ == "__main__":
    main()
