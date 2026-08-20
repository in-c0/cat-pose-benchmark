from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from fusion.v1_pose_package import validate_pose_package

BUNDLE_VERSION = "S0A-proxy-handshake-v0"
SEQUENCE_ID = "s0a-proxy-sequence-0001"
SUBJECT_ID = "synthetic-cat-proxy-0001"
SOURCE_ID = "procedural-proxy:s0a-v0"
DT_SECONDS = 0.1
FRAME_COUNT = 5
START_TIMESTAMP_NS = 1_700_000_000_000_000_000
CAMERA = {
    "camera_id": "camera-main",
    "position_world_m": [0.0, 0.8, 0.0],
    "rotation_world_euler_deg": [0.0, 0.0, 0.0],
    "width_px": 640,
    "height_px": 480,
    "fx_px": 500.0,
    "fy_px": 500.0,
    "cx_px": 320.0,
    "cy_px": 240.0,
}
FLOOR_Y_M = 0.0
CONTACT_TOLERANCE_M = 1e-9
OCCLUDER_HALF_EXTENTS_M = [0.08, 0.15, 0.10]

LANDMARKS_LOCAL_M = {
    "nose_tip": [0.0, 0.15, 0.35],
    "left_ear_tip": [-0.14, 0.32, 0.15],
    "right_ear_tip": [0.14, 0.32, 0.15],
    "withers_visible": [0.0, 0.22, 0.00],
    "sacrum_visible": [0.0, 0.18, -0.35],
    "left_front_paw_center": [-0.12, -0.40, 0.18],
    "right_front_paw_center": [0.12, -0.40, 0.18],
    "left_hind_paw_center": [-0.12, -0.40, -0.28],
    "right_hind_paw_center": [0.12, -0.40, -0.28],
}
TAIL_LOCAL_M = [
    [0.0, 0.15, -0.45],
    [0.0, 0.18, -0.62],
    [0.0, 0.20, -0.79],
    [0.0, 0.19, -0.96],
]


def _canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def canonical_sha256(payload: Any) -> str:
    return hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()


def _payload_without_digest(bundle: dict[str, Any]) -> dict[str, Any]:
    clone = copy.deepcopy(bundle)
    clone.pop("payload_sha256", None)
    return clone


def root_position_world(t: float) -> list[float]:
    # x = 0.15 t + 0.1 t^2 => v = 0.15 + 0.2 t, a = 0.2.
    return [0.15 * t + 0.1 * t * t, 0.40, 3.00]


def root_velocity_world(t: float) -> list[float]:
    return [0.15 + 0.2 * t, 0.0, 0.0]


def root_acceleration_world(_: float) -> list[float]:
    return [0.2, 0.0, 0.0]


def _vec_add(a: list[float], b: list[float]) -> list[float]:
    return [a[i] + b[i] for i in range(3)]


def _left_hind_lift(frame_index: int) -> float:
    return 0.08 if frame_index in {2, 3} else 0.0


def landmark_world(name: str, frame_index: int) -> list[float]:
    t = frame_index * DT_SECONDS
    local = list(LANDMARKS_LOCAL_M[name])
    if name == "left_hind_paw_center":
        local[1] += _left_hind_lift(frame_index)
    return _vec_add(root_position_world(t), local)


def tail_curve_world(frame_index: int) -> list[list[float]]:
    t = frame_index * DT_SECONDS
    root = root_position_world(t)
    bend = 0.015 * frame_index
    result: list[list[float]] = []
    for index, point in enumerate(TAIL_LOCAL_M):
        local = list(point)
        local[0] += bend * index
        result.append(_vec_add(root, local))
    return result


def world_to_camera(point_world: list[float]) -> list[float]:
    p = CAMERA["position_world_m"]
    return [point_world[0] - p[0], point_world[1] - p[1], point_world[2] - p[2]]


def camera_to_image(point_camera: list[float]) -> list[float]:
    x, y, z = point_camera
    if z <= 0:
        raise ValueError("point is not in front of camera")
    return [
        CAMERA["fx_px"] * x / z + CAMERA["cx_px"],
        CAMERA["cy_px"] - CAMERA["fy_px"] * y / z,
    ]


def world_to_image(point_world: list[float]) -> list[float]:
    return camera_to_image(world_to_camera(point_world))


def image_to_camera(point_image: list[float], depth_m: float) -> list[float]:
    if depth_m <= 0:
        raise ValueError("depth_m must be positive")
    u, v = point_image
    return [
        (u - CAMERA["cx_px"]) * depth_m / CAMERA["fx_px"],
        (CAMERA["cy_px"] - v) * depth_m / CAMERA["fy_px"],
        depth_m,
    ]


def occluder_center_world(frame_index: int) -> list[float]:
    # Moves into the left-ear line of sight for exactly frames 2 and 3.
    x = -0.05 if frame_index in {2, 3} else 0.80
    return [x, 0.75, 1.50]


def _segment_intersects_aabb(
    start: list[float],
    end: list[float],
    center: list[float],
    half_extents: list[float],
) -> bool:
    t_min, t_max = 0.0, 1.0
    for axis in range(3):
        delta = end[axis] - start[axis]
        low = center[axis] - half_extents[axis]
        high = center[axis] + half_extents[axis]
        if abs(delta) < 1e-12:
            if start[axis] < low or start[axis] > high:
                return False
            continue
        a = (low - start[axis]) / delta
        b = (high - start[axis]) / delta
        lo, hi = min(a, b), max(a, b)
        t_min = max(t_min, lo)
        t_max = min(t_max, hi)
        if t_min > t_max:
            return False
    return t_max > 0.0 and t_min < 1.0


def visibility_for_landmark(name: str, frame_index: int) -> list[str]:
    point = landmark_world(name, frame_index)
    image = world_to_image(point)
    in_frame = 0.0 <= image[0] < CAMERA["width_px"] and 0.0 <= image[1] < CAMERA["height_px"]
    if not in_frame:
        return ["out_of_frame"]
    if _segment_intersects_aabb(
        list(CAMERA["position_world_m"]),
        point,
        occluder_center_world(frame_index),
        OCCLUDER_HALF_EXTENTS_M,
    ):
        return ["fully_occluded"]
    return ["visible"]


def paw_contact(name: str, frame_index: int) -> bool:
    return abs(landmark_world(name, frame_index)[1] - FLOOR_Y_M) <= CONTACT_TOLERANCE_M


def _observation(
    *,
    frame_index: int,
    semantic_name: str,
    observation_class: str,
    coordinate_space: str,
    units: str,
    mean: Any,
    visibility: list[str],
    suffix: str,
    lineage_extra: str,
) -> dict[str, Any]:
    timestamp_ns = START_TIMESTAMP_NS + int(round(frame_index * DT_SECONDS * 1_000_000_000))
    return {
        "observation_id": f"{SEQUENCE_ID}/frame-{frame_index:04d}/{semantic_name}/{suffix}",
        "sequence_id": SEQUENCE_ID,
        "frame_index": frame_index,
        "timestamp_ns": timestamp_ns,
        "subject_id": SUBJECT_ID,
        "observation_class": observation_class,
        "semantic_name": semantic_name,
        "coordinate_space": coordinate_space,
        "units": units,
        "mean": mean,
        "confidence_region": {"type": "synthetic_exact", "radius": 0.0, "units": units},
        "visibility": visibility,
        "evidence_tier": "X1",
        "quality": "unknown",
        "source_ids": [SOURCE_ID],
        "lineage": [
            f"synthetic:{BUNDLE_VERSION}",
            "proxy:analytic-rigid-surface-v0",
            lineage_extra,
        ],
        "validation": {"synthetic_exact": True},
    }


def _contact_observation(frame_index: int, paw_name: str) -> dict[str, Any]:
    timestamp_ns = START_TIMESTAMP_NS + int(round(frame_index * DT_SECONDS * 1_000_000_000))
    contact = paw_contact(paw_name, frame_index)
    return {
        "observation_id": f"{SEQUENCE_ID}/frame-{frame_index:04d}/{paw_name}/contact",
        "sequence_id": SEQUENCE_ID,
        "frame_index": frame_index,
        "interval": {"start_ns": timestamp_ns, "end_ns": timestamp_ns},
        "timestamp_ns": timestamp_ns,
        "subject_id": SUBJECT_ID,
        "observation_class": "contact_event",
        "semantic_name": f"{paw_name}_floor_contact",
        "coordinate_space": "world",
        "units": "boolean",
        "mean": contact,
        "confidence_region": {"type": "synthetic_exact"},
        "visibility": ["not_applicable"],
        "evidence_tier": "X1",
        "quality": "unknown",
        "source_ids": [SOURCE_ID, "scene:floor"],
        "lineage": [
            f"synthetic:{BUNDLE_VERSION}",
            "contact:analytic-plane-test-v0",
        ],
        "validation": {
            "support_surface_id": "floor",
            "floor_y_m": FLOOR_Y_M,
            "contact_tolerance_m": CONTACT_TOLERANCE_M,
        },
    }


def build_frame(frame_index: int) -> dict[str, Any]:
    t = frame_index * DT_SECONDS
    timestamp_ns = START_TIMESTAMP_NS + int(round(t * 1_000_000_000))
    observations: list[dict[str, Any]] = []

    for name in LANDMARKS_LOCAL_M:
        world = landmark_world(name, frame_index)
        visibility = visibility_for_landmark(name, frame_index)
        observations.append(
            _observation(
                frame_index=frame_index,
                semantic_name=name,
                observation_class="surface_landmark",
                coordinate_space="world",
                units="metres",
                mean=world,
                visibility=visibility,
                suffix="world",
                lineage_extra="transform:proxy-local-to-world-v0",
            )
        )
        observations.append(
            _observation(
                frame_index=frame_index,
                semantic_name=name,
                observation_class="surface_landmark",
                coordinate_space="image",
                units="pixels",
                mean=world_to_image(world),
                visibility=visibility,
                suffix="image",
                lineage_extra="projection:pinhole-top-left-v0",
            )
        )

    tail_world = tail_curve_world(frame_index)
    observations.append(
        _observation(
            frame_index=frame_index,
            semantic_name="tail_centreline",
            observation_class="surface_curve",
            coordinate_space="world",
            units="metres",
            mean=tail_world,
            visibility=["visible"],
            suffix="world",
            lineage_extra="curve:procedural-tail-v0",
        )
    )
    observations.append(
        _observation(
            frame_index=frame_index,
            semantic_name="tail_centreline",
            observation_class="surface_curve",
            coordinate_space="image",
            units="pixels",
            mean=[world_to_image(point) for point in tail_world],
            visibility=["visible"],
            suffix="image",
            lineage_extra="projection:pinhole-top-left-v0",
        )
    )

    observations.append(
        _observation(
            frame_index=frame_index,
            semantic_name="subject_root_velocity",
            observation_class="derived_temporal",
            coordinate_space="world",
            units="metres_per_second",
            mean=root_velocity_world(t),
            visibility=["not_applicable"],
            suffix="world",
            lineage_extra="derivative:analytic-root-motion-v0",
        )
    )
    observations.append(
        _observation(
            frame_index=frame_index,
            semantic_name="subject_root_acceleration",
            observation_class="derived_temporal",
            coordinate_space="world",
            units="metres_per_second_squared",
            mean=root_acceleration_world(t),
            visibility=["not_applicable"],
            suffix="world",
            lineage_extra="derivative:analytic-root-motion-v0",
        )
    )

    for paw_name in (
        "left_front_paw_center",
        "right_front_paw_center",
        "left_hind_paw_center",
        "right_hind_paw_center",
    ):
        observations.append(_contact_observation(frame_index, paw_name))

    return {
        "frame_index": frame_index,
        "time_seconds": t,
        "timestamp_ns": timestamp_ns,
        "subject_root_world_m": root_position_world(t),
        "scene_objects": [
            {
                "object_id": "floor",
                "kind": "plane",
                "position_world_m": [0.0, FLOOR_Y_M, 0.0],
            },
            {
                "object_id": "occluder-box",
                "kind": "aabb",
                "position_world_m": occluder_center_world(frame_index),
                "half_extents_m": OCCLUDER_HALF_EXTENTS_M,
            },
        ],
        "observations": observations,
    }


def build_bundle(frame_count: int = FRAME_COUNT) -> dict[str, Any]:
    if frame_count < 3:
        raise ValueError("frame_count must be at least 3")
    bundle: dict[str, Any] = {
        "bundle_version": BUNDLE_VERSION,
        "sequence_id": SEQUENCE_ID,
        "subject_id": SUBJECT_ID,
        "generator": {
            "kind": "procedural_proxy",
            "name": "cat-pose-benchmark-s0a-reference",
            "version": BUNDLE_VERSION,
            "seed": 0,
            "third_party_asset_used": False,
            "licence_status": "project-authored procedural geometry; no external asset",
        },
        "conventions": {
            "world_axes": {"x": "right", "y": "up", "z": "forward"},
            "world_handedness": "unity_compatible_left_handed",
            "world_units": "metres",
            "image_origin": "top_left",
            "image_axes": {"u": "right", "v": "down"},
            "time_step_seconds": DT_SECONDS,
            "timestamp_units": "nanoseconds",
        },
        "camera": copy.deepcopy(CAMERA),
        "frame_count": frame_count,
        "frames": [build_frame(index) for index in range(frame_count)],
        "claims_boundary": {
            "real_animal_data": False,
            "pose_accuracy_evaluated": False,
            "eligible_as_prospective_real_v1": False,
            "evidence_tier": "X1",
        },
    }
    bundle["payload_sha256"] = canonical_sha256(bundle)
    return bundle


def validate_bundle(
    bundle: dict[str, Any],
    *,
    observation_schema_path: Path | None = None,
) -> list[str]:
    errors: list[str] = []
    if bundle.get("bundle_version") != BUNDLE_VERSION:
        errors.append("bundle_version mismatch")
    if bundle.get("sequence_id") != SEQUENCE_ID:
        errors.append("sequence_id mismatch")
    if bundle.get("subject_id") != SUBJECT_ID:
        errors.append("subject_id mismatch")
    expected_digest = canonical_sha256(_payload_without_digest(bundle))
    if bundle.get("payload_sha256") != expected_digest:
        errors.append("payload_sha256 mismatch")
    frames = bundle.get("frames")
    if not isinstance(frames, list) or len(frames) != bundle.get("frame_count"):
        errors.append("frame_count does not match frames")
        return errors

    schema_path = observation_schema_path or (
        Path(__file__).resolve().parents[1] / "schemas" / "observation.schema.json"
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)

    seen_ids: set[str] = set()
    for frame_index, frame in enumerate(frames):
        if frame.get("frame_index") != frame_index:
            errors.append(f"frame {frame_index}: frame_index mismatch")
        expected_timestamp = START_TIMESTAMP_NS + int(
            round(frame_index * DT_SECONDS * 1_000_000_000)
        )
        if frame.get("timestamp_ns") != expected_timestamp:
            errors.append(f"frame {frame_index}: timestamp mismatch")
        for observation in frame.get("observations", []):
            obs_id = observation.get("observation_id")
            if obs_id in seen_ids:
                errors.append(f"duplicate observation_id: {obs_id}")
            seen_ids.add(obs_id)
            for schema_error in validator.iter_errors(observation):
                path = ".".join(str(item) for item in schema_error.absolute_path) or "<root>"
                errors.append(
                    f"frame {frame_index} observation {obs_id} {path}: {schema_error.message}"
                )
            if observation.get("evidence_tier") != "X1":
                errors.append(f"{obs_id}: synthetic observation must use X1")
            if observation.get("source_ids") != list(dict.fromkeys(observation.get("source_ids", []))):
                errors.append(f"{obs_id}: source_ids must be unique")
            if not observation.get("lineage"):
                errors.append(f"{obs_id}: lineage missing")
            if "confidence_region" not in observation and "covariance" not in observation:
                errors.append(f"{obs_id}: uncertainty missing")
    return errors


def build_synthetic_m1_candidate(bundle: dict[str, Any]) -> dict[str, Any]:
    # Deliberately constructs a structurally valid package with X1 observations so
    # the prospective-real V1 validator can prove it rejects synthetic evidence.
    first = bundle["frames"][0]
    selected = [
        copy.deepcopy(obs)
        for obs in first["observations"]
        if obs["observation_class"] == "surface_landmark"
        and obs["coordinate_space"] == "image"
    ][:2]
    return {
        "package_version": "V1-M1-pose-package-v0",
        "event_id": "synthetic-event",
        "episode_id": "synthetic-episode",
        "sequence_id": bundle["sequence_id"],
        "subject_id": bundle["subject_id"],
        "evidence_window_ms": {"start_offset_ms": 0, "end_offset_ms": 100},
        "producer": {
            "kind": "calibrated_geometry",
            "name": "s0a-procedural-proxy",
            "version": BUNDLE_VERSION,
            "code_revision": BUNDLE_VERSION,
        },
        "source_media": [
            {
                "record_id": "synthetic-render-placeholder",
                "sha256": "0" * 64,
                "media_type": "image/png",
                "width_px": CAMERA["width_px"],
                "height_px": CAMERA["height_px"],
            }
        ],
        "samples": [
            {
                "event_offset_ms": 0,
                "frame_index": 0,
                "observations": selected,
            }
        ],
        "notes": "Synthetic X1 package used only to assert prospective-real rejection.",
    }


def validate_m1_boundary(bundle: dict[str, Any]) -> list[str]:
    return validate_pose_package(build_synthetic_m1_candidate(bundle))


def write_bundle(path: Path, bundle: dict[str, Any] | None = None) -> None:
    payload = bundle or build_bundle()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate/validate the deterministic S0A procedural-proxy annotation handshake"
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()

    if args.validate_only:
        payload = json.loads(args.output.read_text(encoding="utf-8"))
    else:
        payload = build_bundle()
        write_bundle(args.output, payload)

    errors = validate_bundle(payload)
    boundary_errors = validate_m1_boundary(payload)
    if not any(
        "evidence_tier" in error
        and "cannot count as prospective real V1 evidence" in error
        for error in boundary_errors
    ):
        errors.append("M1 boundary failure: X1 synthetic evidence was not explicitly rejected")

    print(
        json.dumps(
            {
                "bundle_valid": not errors,
                "errors": errors,
                "payload_sha256": payload.get("payload_sha256"),
                "m1_boundary_rejected": bool(boundary_errors),
            },
            indent=2,
            sort_keys=True,
        )
    )
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
