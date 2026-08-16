#!/usr/bin/env python3
"""Validate a Stage S0 synthetic sequence and its cross-field invariants."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft202012Validator


AXES_2 = ("x", "y")
AXES_3 = ("x", "y", "z")


def _path(error: Any) -> str:
    return ".".join(str(part) for part in error.absolute_path) or "<root>"


def _components(vector: dict[str, float], axes: tuple[str, ...]) -> list[float]:
    return [float(vector[axis]) for axis in axes]


def _finite(values: Iterable[float]) -> bool:
    return all(math.isfinite(float(value)) for value in values)


def _finite_vector(vector: dict[str, float], axes: tuple[str, ...]) -> bool:
    return _finite(_components(vector, axes))


def canonical_sha256(sequence: dict[str, Any]) -> str:
    payload = json.dumps(
        sequence,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def validate_sequence(
    sequence: dict[str, Any],
    schema: dict[str, Any],
    *,
    numeric_tolerance: float = 1e-6,
) -> list[str]:
    errors = [
        f"{_path(error)}: {error.message}"
        for error in sorted(
            Draft202012Validator(schema).iter_errors(sequence),
            key=_path,
        )
    ]
    if errors:
        return errors

    frames = sequence["frames"]
    deterministic = sequence["determinism"]
    camera = sequence["camera"]
    width, height = camera["resolution_px"]
    fixed_timestep_ns = deterministic["fixed_timestep_ns"]
    fixed_timestep_s = fixed_timestep_ns / 1_000_000_000.0

    if deterministic["frame_count"] != len(frames):
        errors.append(
            "determinism.frame_count does not equal the number of frames"
        )

    support_ids = {
        surface["object_id"] for surface in sequence["scene"]["support_surfaces"]
    }

    for expected_index, frame in enumerate(frames):
        prefix = f"frames[{expected_index}]"
        if frame["frame_index"] != expected_index:
            errors.append(f"{prefix}.frame_index must be contiguous from zero")
        expected_timestamp = expected_index * fixed_timestep_ns
        if frame["timestamp_ns"] != expected_timestamp:
            errors.append(
                f"{prefix}.timestamp_ns must equal frame_index * fixed_timestep_ns"
            )

        if not _finite_vector(frame["subject_root_world_m"], AXES_3):
            errors.append(f"{prefix}.subject_root_world_m contains a non-finite value")
        if not _finite_vector(frame["subject_velocity_world_mps"], AXES_3):
            errors.append(
                f"{prefix}.subject_velocity_world_mps contains a non-finite value"
            )

        names: set[str] = set()
        for landmark_index, landmark in enumerate(frame["landmarks"]):
            landmark_prefix = f"{prefix}.landmarks[{landmark_index}]"
            name = landmark["semantic_name"]
            if name in names:
                errors.append(
                    f"{prefix}.landmarks contains duplicate semantic_name {name}"
                )
            names.add(name)

            if not _finite_vector(landmark["world_m"], AXES_3):
                errors.append(f"{landmark_prefix}.world_m contains a non-finite value")
            if not _finite_vector(landmark["camera_m"], AXES_3):
                errors.append(f"{landmark_prefix}.camera_m contains a non-finite value")
            if not _finite_vector(landmark["image_px"], AXES_2):
                errors.append(f"{landmark_prefix}.image_px contains a non-finite value")

            image_x = float(landmark["image_px"]["x"])
            image_y = float(landmark["image_px"]["y"])
            camera_z = float(landmark["camera_m"]["z"])
            visibility = landmark["visibility"]
            in_frame = 0.0 <= image_x <= width and 0.0 <= image_y <= height
            if visibility == "visible" and not in_frame:
                errors.append(
                    f"{landmark_prefix} is visible but its image point is outside the frame"
                )
            if visibility == "visible" and camera_z <= 0.0:
                errors.append(f"{landmark_prefix} is visible but is behind the camera")
            if visibility == "out_of_frame" and in_frame and camera_z > 0.0:
                errors.append(
                    f"{landmark_prefix} is out_of_frame but projects inside the image"
                )

        if not all(
            _finite_vector(point, AXES_3)
            for point in frame["tail_curve_world_m"]
        ):
            errors.append(f"{prefix}.tail_curve_world_m contains a non-finite value")

        for contact_index, contact in enumerate(frame["contacts"]):
            if contact["support_surface_id"] not in support_ids:
                errors.append(
                    f"{prefix}.contacts[{contact_index}] references an unknown support surface"
                )

        for relation_index, relation in enumerate(frame["spatial_relations"]):
            if relation["subject_id"] != sequence["subject_id"]:
                errors.append(
                    f"{prefix}.spatial_relations[{relation_index}] has the wrong subject_id"
                )

    if fixed_timestep_s <= 0.0:
        errors.append("determinism.fixed_timestep_ns must be positive")
    else:
        for index in range(len(frames) - 1):
            current = frames[index]
            following = frames[index + 1]
            current_root = _components(current["subject_root_world_m"], AXES_3)
            following_root = _components(following["subject_root_world_m"], AXES_3)
            finite_difference = [
                (following_root[axis] - current_root[axis]) / fixed_timestep_s
                for axis in range(3)
            ]
            declared = _components(current["subject_velocity_world_mps"], AXES_3)
            for axis, (expected, actual) in enumerate(zip(finite_difference, declared)):
                if not math.isclose(
                    expected,
                    actual,
                    rel_tol=numeric_tolerance,
                    abs_tol=numeric_tolerance,
                ):
                    errors.append(
                        f"frames[{index}].subject_velocity_world_mps[{axis}] "
                        f"does not match the finite difference ({actual} vs {expected})"
                    )

    return errors


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("sequence", type=Path)
    parser.add_argument(
        "--schema",
        type=Path,
        default=Path(__file__).parents[1]
        / "schemas"
        / "synthetic-sequence.schema.json",
    )
    args = parser.parse_args()

    sequence = json.loads(args.sequence.read_text(encoding="utf-8"))
    schema = json.loads(args.schema.read_text(encoding="utf-8"))
    errors = validate_sequence(sequence, schema)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        raise SystemExit(1)

    print(f"Valid Stage S0 sequence: {args.sequence}")
    print(f"Canonical SHA-256: {canonical_sha256(sequence)}")


if __name__ == "__main__":
    main()
