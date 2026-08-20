from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

from synthetic.s0_proxy import (
    BUNDLE_VERSION,
    CAMERA,
    DT_SECONDS,
    FRAME_COUNT,
    LANDMARKS_LOCAL_M,
    OCCLUDER_HALF_EXTENTS_M,
    SEQUENCE_ID,
    START_TIMESTAMP_NS,
    SUBJECT_ID,
    landmark_world,
    occluder_center_world,
    paw_contact,
    root_position_world,
    tail_curve_world,
    visibility_for_landmark,
    world_to_image,
)

UNITY_EXPORT_VERSION = "S0B-unity-raw-v0"
ROUNDTRIP_VERSION = "S0B-unity-roundtrip-v0"
PINNED_UNITY_EDITOR_VERSION = "6000.3.18f1"
RUNTIME_SOURCE_UNITY = "unity_editor"
RUNTIME_SOURCE_MOCK = "python_mock_unity_contract"
DEFAULT_TOLERANCE = 1e-5
PAW_NAMES = (
    "left_front_paw_center",
    "right_front_paw_center",
    "left_hind_paw_center",
    "right_hind_paw_center",
)


def _vec2(values: list[float]) -> dict[str, float]:
    return {"x": float(values[0]), "y": float(values[1])}


def _vec3(values: list[float]) -> dict[str, float]:
    return {
        "x": float(values[0]),
        "y": float(values[1]),
        "z": float(values[2]),
    }


def _as_vec2(value: Any, path: str, errors: list[str]) -> list[float] | None:
    if not isinstance(value, dict):
        errors.append(f"{path}: expected object {{x,y}}")
        return None
    result: list[float] = []
    for key in ("x", "y"):
        item = value.get(key)
        if not isinstance(item, (int, float)) or isinstance(item, bool):
            errors.append(f"{path}.{key}: expected finite number")
            return None
        item = float(item)
        if not math.isfinite(item):
            errors.append(f"{path}.{key}: expected finite number")
            return None
        result.append(item)
    return result


def _as_vec3(value: Any, path: str, errors: list[str]) -> list[float] | None:
    if not isinstance(value, dict):
        errors.append(f"{path}: expected object {{x,y,z}}")
        return None
    result: list[float] = []
    for key in ("x", "y", "z"):
        item = value.get(key)
        if not isinstance(item, (int, float)) or isinstance(item, bool):
            errors.append(f"{path}.{key}: expected finite number")
            return None
        item = float(item)
        if not math.isfinite(item):
            errors.append(f"{path}.{key}: expected finite number")
            return None
        result.append(item)
    return result


def _close(actual: float, expected: float, tolerance: float) -> bool:
    return abs(float(actual) - float(expected)) <= tolerance


def _compare_scalar(
    actual: Any,
    expected: float,
    path: str,
    tolerance: float,
    errors: list[str],
) -> None:
    if not isinstance(actual, (int, float)) or isinstance(actual, bool):
        errors.append(f"{path}: expected finite number")
        return
    actual = float(actual)
    if not math.isfinite(actual):
        errors.append(f"{path}: expected finite number")
        return
    if not _close(actual, expected, tolerance):
        errors.append(f"{path}: expected {expected!r}, got {actual!r}")


def _compare_vec(
    actual: Any,
    expected: list[float],
    path: str,
    tolerance: float,
    errors: list[str],
) -> None:
    parsed = (
        _as_vec2(actual, path, errors)
        if len(expected) == 2
        else _as_vec3(actual, path, errors)
    )
    if parsed is None:
        return
    for index, (value, target) in enumerate(zip(parsed, expected)):
        if not _close(value, target, tolerance):
            axis = ("x", "y", "z")[index]
            errors.append(
                f"{path}.{axis}: expected {target!r}, got {value!r}"
            )


def _require_exact(actual: Any, expected: Any, path: str, errors: list[str]) -> None:
    if actual != expected:
        errors.append(f"{path}: expected {expected!r}, got {actual!r}")


def build_mock_unity_export() -> dict[str, Any]:
    """Build the raw Unity-side contract without claiming Unity executed it.

    This is used only to test the Python comparator and JSON shape. The runtime_source
    deliberately prevents it from satisfying the real Unity acceptance gate.
    """
    frames: list[dict[str, Any]] = []
    for frame_index in range(FRAME_COUNT):
        landmarks = []
        for name in LANDMARKS_LOCAL_M:
            world = landmark_world(name, frame_index)
            landmarks.append(
                {
                    "name": name,
                    "world_m": _vec3(world),
                    "image_px": _vec2(world_to_image(world)),
                    "visibility": visibility_for_landmark(name, frame_index)[0],
                }
            )
        tail_world = tail_curve_world(frame_index)
        frames.append(
            {
                "frame_index": frame_index,
                "timestamp_ns": START_TIMESTAMP_NS
                + frame_index * 100_000_000,
                "root_world_m": _vec3(
                    root_position_world(frame_index * DT_SECONDS)
                ),
                "occluder_world_m": _vec3(
                    occluder_center_world(frame_index)
                ),
                "landmarks": landmarks,
                "tail_world_m": [_vec3(point) for point in tail_world],
                "tail_image_px": [
                    _vec2(world_to_image(point)) for point in tail_world
                ],
                "contacts": [
                    {
                        "paw_name": paw_name,
                        "floor_contact": paw_contact(paw_name, frame_index),
                    }
                    for paw_name in PAW_NAMES
                ],
            }
        )

    return {
        "export_version": UNITY_EXPORT_VERSION,
        "unity_editor_version": PINNED_UNITY_EDITOR_VERSION,
        "runtime_source": RUNTIME_SOURCE_MOCK,
        "reference_bundle_version": BUNDLE_VERSION,
        "sequence_id": SEQUENCE_ID,
        "subject_id": SUBJECT_ID,
        "dt_seconds": DT_SECONDS,
        "start_timestamp_ns": START_TIMESTAMP_NS,
        "camera": {
            "camera_id": CAMERA["camera_id"],
            "position_world_m": _vec3(CAMERA["position_world_m"]),
            "width_px": CAMERA["width_px"],
            "height_px": CAMERA["height_px"],
            "fx_px": CAMERA["fx_px"],
            "fy_px": CAMERA["fy_px"],
            "cx_px": CAMERA["cx_px"],
            "cy_px": CAMERA["cy_px"],
        },
        "occluder_half_extents_m": _vec3(OCCLUDER_HALF_EXTENTS_M),
        "frame_count": FRAME_COUNT,
        "frames": frames,
    }


def compare_unity_export(
    payload: Any,
    *,
    tolerance: float = DEFAULT_TOLERANCE,
    require_unity_runtime: bool = True,
) -> list[str]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return ["<root>: Unity export must be a JSON object"]
    if tolerance <= 0 or not math.isfinite(tolerance):
        return ["tolerance: must be a positive finite number"]

    _require_exact(
        payload.get("export_version"),
        UNITY_EXPORT_VERSION,
        "export_version",
        errors,
    )
    _require_exact(
        payload.get("unity_editor_version"),
        PINNED_UNITY_EDITOR_VERSION,
        "unity_editor_version",
        errors,
    )
    _require_exact(
        payload.get("reference_bundle_version"),
        BUNDLE_VERSION,
        "reference_bundle_version",
        errors,
    )
    _require_exact(payload.get("sequence_id"), SEQUENCE_ID, "sequence_id", errors)
    _require_exact(payload.get("subject_id"), SUBJECT_ID, "subject_id", errors)
    _require_exact(
        payload.get("start_timestamp_ns"),
        START_TIMESTAMP_NS,
        "start_timestamp_ns",
        errors,
    )
    _require_exact(payload.get("frame_count"), FRAME_COUNT, "frame_count", errors)

    runtime_source = payload.get("runtime_source")
    if require_unity_runtime:
        _require_exact(
            runtime_source,
            RUNTIME_SOURCE_UNITY,
            "runtime_source: actual gate requires 'unity_editor'",
            errors,
        )
    elif runtime_source not in {RUNTIME_SOURCE_UNITY, RUNTIME_SOURCE_MOCK}:
        errors.append(
            "runtime_source: expected 'unity_editor' or 'python_mock_unity_contract'"
        )

    _compare_scalar(
        payload.get("dt_seconds"),
        DT_SECONDS,
        "dt_seconds",
        tolerance,
        errors,
    )

    camera = payload.get("camera")
    if not isinstance(camera, dict):
        errors.append("camera: expected object")
    else:
        _require_exact(camera.get("camera_id"), CAMERA["camera_id"], "camera.camera_id", errors)
        _require_exact(camera.get("width_px"), CAMERA["width_px"], "camera.width_px", errors)
        _require_exact(camera.get("height_px"), CAMERA["height_px"], "camera.height_px", errors)
        for field in ("fx_px", "fy_px", "cx_px", "cy_px"):
            _compare_scalar(
                camera.get(field),
                CAMERA[field],
                f"camera.{field}",
                tolerance,
                errors,
            )
        _compare_vec(
            camera.get("position_world_m"),
            CAMERA["position_world_m"],
            "camera.position_world_m",
            tolerance,
            errors,
        )

    _compare_vec(
        payload.get("occluder_half_extents_m"),
        OCCLUDER_HALF_EXTENTS_M,
        "occluder_half_extents_m",
        tolerance,
        errors,
    )

    frames = payload.get("frames")
    if not isinstance(frames, list):
        errors.append("frames: expected array")
        return errors
    if len(frames) != FRAME_COUNT:
        errors.append(f"frames: expected {FRAME_COUNT} entries, got {len(frames)}")

    expected_landmark_names = set(LANDMARKS_LOCAL_M)
    expected_contact_names = set(PAW_NAMES)

    for frame_index, frame in enumerate(frames[:FRAME_COUNT]):
        path = f"frames.{frame_index}"
        if not isinstance(frame, dict):
            errors.append(f"{path}: expected object")
            continue
        _require_exact(frame.get("frame_index"), frame_index, f"{path}.frame_index", errors)
        _require_exact(
            frame.get("timestamp_ns"),
            START_TIMESTAMP_NS + frame_index * 100_000_000,
            f"{path}.timestamp_ns",
            errors,
        )
        _compare_vec(
            frame.get("root_world_m"),
            root_position_world(frame_index * DT_SECONDS),
            f"{path}.root_world_m",
            tolerance,
            errors,
        )
        _compare_vec(
            frame.get("occluder_world_m"),
            occluder_center_world(frame_index),
            f"{path}.occluder_world_m",
            tolerance,
            errors,
        )

        landmarks = frame.get("landmarks")
        if not isinstance(landmarks, list):
            errors.append(f"{path}.landmarks: expected array")
        else:
            by_name: dict[str, dict[str, Any]] = {}
            for landmark_index, landmark in enumerate(landmarks):
                landmark_path = f"{path}.landmarks.{landmark_index}"
                if not isinstance(landmark, dict):
                    errors.append(f"{landmark_path}: expected object")
                    continue
                name = landmark.get("name")
                if not isinstance(name, str) or not name:
                    errors.append(f"{landmark_path}.name: expected non-empty string")
                    continue
                if name in by_name:
                    errors.append(f"{path}.landmarks: duplicate landmark name {name!r}")
                    continue
                by_name[name] = landmark
            missing = sorted(expected_landmark_names - set(by_name))
            extra = sorted(set(by_name) - expected_landmark_names)
            if missing:
                errors.append(f"{path}.landmarks: missing names {missing}")
            if extra:
                errors.append(f"{path}.landmarks: unexpected names {extra}")
            for name in sorted(expected_landmark_names & set(by_name)):
                landmark = by_name[name]
                expected_world = landmark_world(name, frame_index)
                _compare_vec(
                    landmark.get("world_m"),
                    expected_world,
                    f"{path}.landmarks[{name}].world_m",
                    tolerance,
                    errors,
                )
                _compare_vec(
                    landmark.get("image_px"),
                    world_to_image(expected_world),
                    f"{path}.landmarks[{name}].image_px",
                    tolerance,
                    errors,
                )
                _require_exact(
                    landmark.get("visibility"),
                    visibility_for_landmark(name, frame_index)[0],
                    f"{path}.landmarks[{name}].visibility",
                    errors,
                )

        expected_tail_world = tail_curve_world(frame_index)
        tail_world = frame.get("tail_world_m")
        if not isinstance(tail_world, list):
            errors.append(f"{path}.tail_world_m: expected array")
        else:
            if len(tail_world) != len(expected_tail_world):
                errors.append(
                    f"{path}.tail_world_m: expected {len(expected_tail_world)} points, got {len(tail_world)}"
                )
            for point_index, expected in enumerate(expected_tail_world):
                if point_index >= len(tail_world):
                    break
                _compare_vec(
                    tail_world[point_index],
                    expected,
                    f"{path}.tail_world_m.{point_index}",
                    tolerance,
                    errors,
                )

        tail_image = frame.get("tail_image_px")
        if not isinstance(tail_image, list):
            errors.append(f"{path}.tail_image_px: expected array")
        else:
            if len(tail_image) != len(expected_tail_world):
                errors.append(
                    f"{path}.tail_image_px: expected {len(expected_tail_world)} points, got {len(tail_image)}"
                )
            for point_index, expected_world in enumerate(expected_tail_world):
                if point_index >= len(tail_image):
                    break
                _compare_vec(
                    tail_image[point_index],
                    world_to_image(expected_world),
                    f"{path}.tail_image_px.{point_index}",
                    tolerance,
                    errors,
                )

        contacts = frame.get("contacts")
        if not isinstance(contacts, list):
            errors.append(f"{path}.contacts: expected array")
        else:
            by_paw: dict[str, dict[str, Any]] = {}
            for contact_index, contact in enumerate(contacts):
                contact_path = f"{path}.contacts.{contact_index}"
                if not isinstance(contact, dict):
                    errors.append(f"{contact_path}: expected object")
                    continue
                paw_name = contact.get("paw_name")
                if not isinstance(paw_name, str) or not paw_name:
                    errors.append(f"{contact_path}.paw_name: expected non-empty string")
                    continue
                if paw_name in by_paw:
                    errors.append(f"{path}.contacts: duplicate paw_name {paw_name!r}")
                    continue
                by_paw[paw_name] = contact
            missing = sorted(expected_contact_names - set(by_paw))
            extra = sorted(set(by_paw) - expected_contact_names)
            if missing:
                errors.append(f"{path}.contacts: missing paw names {missing}")
            if extra:
                errors.append(f"{path}.contacts: unexpected paw names {extra}")
            for paw_name in sorted(expected_contact_names & set(by_paw)):
                value = by_paw[paw_name].get("floor_contact")
                if not isinstance(value, bool):
                    errors.append(
                        f"{path}.contacts[{paw_name}].floor_contact: expected boolean"
                    )
                else:
                    _require_exact(
                        value,
                        paw_contact(paw_name, frame_index),
                        f"{path}.contacts[{paw_name}].floor_contact",
                        errors,
                    )

    return errors


def build_report(
    payload: Any,
    *,
    tolerance: float = DEFAULT_TOLERANCE,
    require_unity_runtime: bool = True,
) -> dict[str, Any]:
    mismatches = compare_unity_export(
        payload,
        tolerance=tolerance,
        require_unity_runtime=require_unity_runtime,
    )
    runtime_source = payload.get("runtime_source") if isinstance(payload, dict) else None
    return {
        "roundtrip_version": ROUNDTRIP_VERSION,
        "contract_valid": not mismatches,
        "unity_runtime_verified": (
            not mismatches and runtime_source == RUNTIME_SOURCE_UNITY
        ),
        "performance_analysis_performed": False,
        "tolerance": tolerance,
        "mismatch_count": len(mismatches),
        "mismatches": mismatches,
    }


def write_mock_export(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(build_mock_unity_export(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare an S0B Unity raw export against the frozen S0A reference"
    )
    parser.add_argument("export", type=Path)
    parser.add_argument("--summary", type=Path)
    parser.add_argument("--tolerance", type=float, default=DEFAULT_TOLERANCE)
    parser.add_argument(
        "--allow-mock",
        action="store_true",
        help="accept the Python mock runtime source for comparator CI/tests only",
    )
    args = parser.parse_args()

    payload = json.loads(args.export.read_text(encoding="utf-8"))
    report = build_report(
        payload,
        tolerance=args.tolerance,
        require_unity_runtime=not args.allow_mock,
    )
    rendered = json.dumps(report, indent=2, sort_keys=True)
    print(rendered)
    if args.summary:
        args.summary.parent.mkdir(parents=True, exist_ok=True)
        args.summary.write_text(rendered + "\n", encoding="utf-8")
    if not report["contract_valid"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
