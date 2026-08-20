from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

POSE_PACKAGE_VERSION = "V1-M1-pose-package-v0"
POSE_PACKAGE_SCHEMA_REF = "fusion/v1_pose_package.schema.json"
POSE_PACKAGE_SCHEMA_PATH = Path(__file__).with_name("v1_pose_package.schema.json")
OBSERVATION_SCHEMA_PATH = Path(__file__).resolve().parents[1] / "schemas" / "observation.schema.json"

ALLOWED_OBSERVATION_CLASSES = {
    "surface_landmark",
    "surface_curve",
    "latent_anatomy",
    "derived_temporal",
}
ALLOWED_PROSPECTIVE_EVIDENCE_TIERS = {"G2", "G3", "S1", "S2"}


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _canonical_json(payload: Any) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _render_schema_errors(payload: Any, schema: dict[str, Any], prefix: str) -> list[str]:
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    rendered: list[str] = []
    for error in sorted(validator.iter_errors(payload), key=lambda item: list(item.absolute_path)):
        path = ".".join(str(part) for part in error.absolute_path) or "<root>"
        rendered.append(f"{prefix}.{path}: {error.message}")
    return rendered


def validate_pose_package(
    payload: Any,
    *,
    sidecar: dict[str, Any] | None = None,
    event: dict[str, Any] | None = None,
    package_schema: dict[str, Any] | None = None,
    observation_schema: dict[str, Any] | None = None,
) -> list[str]:
    """Validate a prospective real-data V1 pose package for M1 use.

    This validates *provenance and package integrity*, not pose accuracy. A valid
    package may still contain poor S2 predictions; those limitations stay explicit
    in evidence tier, quality, uncertainty and downstream held-out evaluation.
    """
    package_schema = package_schema or _load_json(POSE_PACKAGE_SCHEMA_PATH)
    observation_schema = observation_schema or _load_json(OBSERVATION_SCHEMA_PATH)
    errors = _render_schema_errors(payload, package_schema, "package")
    if errors or not isinstance(payload, dict):
        return errors or ["package.<root>: pose package must be a JSON object"]

    window = payload["evidence_window_ms"]
    start = window["start_offset_ms"]
    end = window["end_offset_ms"]
    if start >= end:
        errors.append("package.evidence_window_ms: start_offset_ms must precede end_offset_ms")

    source_media = payload["source_media"]
    for index, source in enumerate(source_media):
        media_type = str(source["media_type"]).lower()
        if not (media_type.startswith("video/") or media_type.startswith("image/")):
            errors.append(
                f"package.source_media.{index}.media_type: V1 source must be image/* or video/*"
            )

    samples = payload["samples"]
    offsets = [float(sample["event_offset_ms"]) for sample in samples]
    if offsets != sorted(offsets):
        errors.append("package.samples: event_offset_ms values must be non-decreasing")
    frame_indices = [sample["frame_index"] for sample in samples]
    if len(frame_indices) != len(set(frame_indices)):
        errors.append("package.samples: frame_index values must be unique")

    observation_count = 0
    observation_ids: list[str] = []
    for sample_index, sample in enumerate(samples):
        offset = float(sample["event_offset_ms"])
        if offset < start or offset > end:
            errors.append(
                f"package.samples.{sample_index}.event_offset_ms: {offset} lies outside package evidence window {start}-{end} ms"
            )

        for observation_index, observation in enumerate(sample["observations"]):
            observation_count += 1
            prefix = f"package.samples.{sample_index}.observations.{observation_index}"
            observation_errors = _render_schema_errors(
                observation,
                observation_schema,
                prefix,
            )
            errors.extend(observation_errors)
            if observation_errors:
                continue

            observation_ids.append(observation["observation_id"])
            if observation["sequence_id"] != payload["sequence_id"]:
                errors.append(f"{prefix}.sequence_id: does not match package sequence_id")
            if observation["subject_id"] != payload["subject_id"]:
                errors.append(f"{prefix}.subject_id: does not match package subject_id")
            if observation.get("frame_index") != sample["frame_index"]:
                errors.append(f"{prefix}.frame_index: does not match enclosing sample frame_index")

            observation_class = observation["observation_class"]
            if observation_class not in ALLOWED_OBSERVATION_CLASSES:
                errors.append(
                    f"{prefix}.observation_class: {observation_class!r} is not eligible for the V1-only M1 comparator"
                )

            evidence_tier = observation["evidence_tier"]
            if evidence_tier not in ALLOWED_PROSPECTIVE_EVIDENCE_TIERS:
                errors.append(
                    f"{prefix}.evidence_tier: {evidence_tier!r} cannot count as prospective real V1 evidence"
                )

            if "mean" not in observation:
                errors.append(f"{prefix}.mean: an actual visual estimate/value is required")
            if "covariance" not in observation and "confidence_region" not in observation:
                errors.append(
                    f"{prefix}: uncertainty is required via covariance or confidence_region"
                )

    if observation_count == 0:
        errors.append("package.samples: at least one V1 observation is required")
    if len(observation_ids) != len(set(observation_ids)):
        errors.append("package.samples: observation_id values must be unique across the package")

    if sidecar is not None:
        if sidecar.get("modality") != "visual_pose":
            errors.append("sidecar.modality: V1 package requires visual_pose reservation")
        if sidecar.get("schema_ref") != POSE_PACKAGE_SCHEMA_REF:
            errors.append(
                f"sidecar.schema_ref: visual_pose reservation must use {POSE_PACKAGE_SCHEMA_REF}"
            )
        if payload["event_id"] != sidecar.get("event_id"):
            errors.append("package.event_id: does not match reserved sidecar event_id")
        if payload["episode_id"] != sidecar.get("episode_id"):
            errors.append("package.episode_id: does not match reserved sidecar episode_id")
        if start != sidecar.get("start_offset_ms") or end != sidecar.get("end_offset_ms"):
            errors.append(
                "package.evidence_window_ms: must exactly match reserved visual_pose sidecar interval"
            )

    if event is not None:
        if payload["event_id"] != event.get("event_id"):
            errors.append("package.event_id: does not match CT1 event")
        if payload["episode_id"] != event.get("episode_id"):
            errors.append("package.episode_id: does not match CT1 episode")
        if payload["subject_id"] != event.get("subject_id"):
            errors.append("package.subject_id: does not match CT1 subject")

    return errors


def pose_package_metadata(payload: dict[str, Any]) -> dict[str, Any]:
    observations = [
        observation
        for sample in payload["samples"]
        for observation in sample["observations"]
    ]
    producer = payload["producer"]
    return {
        "container": "json",
        "package_version": payload["package_version"],
        "event_id": payload["event_id"],
        "episode_id": payload["episode_id"],
        "sequence_id": payload["sequence_id"],
        "subject_id": payload["subject_id"],
        "evidence_window_ms": payload["evidence_window_ms"],
        "sample_count": len(payload["samples"]),
        "observation_count": len(observations),
        "observation_class_counts": dict(
            sorted(Counter(item["observation_class"] for item in observations).items())
        ),
        "evidence_tier_counts": dict(
            sorted(Counter(item["evidence_tier"] for item in observations).items())
        ),
        "quality_counts": dict(
            sorted(Counter(item["quality"] for item in observations).items())
        ),
        "producer": {
            "kind": producer["kind"],
            "name": producer["name"],
            "version": producer["version"],
            "model_family": producer.get("model_family"),
            "weights_sha256": producer.get("weights_sha256"),
            "code_revision": producer.get("code_revision"),
        },
        "producer_fingerprint_sha256": hashlib.sha256(_canonical_json(producer)).hexdigest(),
        "source_media_count": len(payload["source_media"]),
    }


def validate_pose_package_path(path: Path) -> list[str]:
    try:
        payload = _load_json(path)
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        return [f"package.<root>: unable to read pose package JSON: {exc}"]
    return validate_pose_package(payload)
