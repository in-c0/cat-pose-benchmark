from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from context.ct1_capture import validate_capture_event
from fusion.v1_pose_package import POSE_PACKAGE_SCHEMA_REF, POSE_PACKAGE_VERSION
from programme.validate_intent_event import validate_instance

TARGET_NAME = "signalling_terminated"
TARGET_HORIZON_MS = 60_000
SENSOR_EVIDENCE_CUTOFF_MS = 5_000
PRIMARY_ABLATION_ROWS = ("B0", "V", "A", "BV", "BA", "VA", "BVA", "BVA-V", "BVA-A")
SENSOR_MODALITIES = {"V1": "visual_pose", "A1": "audio_vocalisation"}
# Duplicated here intentionally to avoid a circular import: m1_sensor_sidecar imports
# this cohort module. If the public sidecar version changes, the cohort marker must be
# advanced in the same change.
EXPECTED_SENSOR_SIDECAR_VERSION = "M1.3-sensor-sidecar-v0"


def _digest_ids(ids: list[str]) -> str:
    return hashlib.sha256("\n".join(sorted(ids)).encode("utf-8")).hexdigest()


def _is_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdefABCDEF" for character in value)
    )


def _termination_label(event: dict[str, Any]) -> tuple[bool | None, list[str]]:
    errors: list[str] = []
    values: list[tuple[bool, int]] = []
    for outcome in event.get("outcomes", []):
        if outcome.get("outcome_type") != "signalling_termination":
            continue
        value = outcome.get("signalling_terminated")
        if not isinstance(value, bool):
            continue
        timestamp = int(outcome.get("end_offset_ms", outcome["start_offset_ms"]))
        if timestamp > TARGET_HORIZON_MS:
            errors.append(
                f"termination outcome {outcome.get('outcome_id')} exceeds frozen {TARGET_HORIZON_MS} ms horizon"
            )
            continue
        values.append((value, timestamp))

    if not values:
        return None, errors
    unique = {value for value, _ in values}
    if len(unique) > 1:
        errors.append("contradictory signalling_termination boolean outcomes")
        return None, errors

    value = values[0][0]
    if value is False and max(timestamp for _, timestamp in values) < TARGET_HORIZON_MS:
        errors.append(
            "continued/false termination label must be observed at the frozen 60 s horizon"
        )
        return None, errors
    return value, errors


def _valid_v1_package_provenance(
    observation: dict[str, Any], event: dict[str, Any]
) -> bool:
    """Require the public markers emitted by a validated V1 sidecar composition.

    The full local package is validated when sealed/composed. M1.2 sees only the
    public-shaped derived #18 event, so it independently requires the canonical
    package schema, immutable sidecar hashes, exact package/event identity and the
    non-empty package summary. A hand-authored modality name alone cannot satisfy V1.
    """
    if observation.get("schema_ref") != POSE_PACKAGE_SCHEMA_REF:
        return False
    features = observation.get("features")
    if not isinstance(features, dict):
        return False
    if features.get("sensor_sidecar_version") != EXPECTED_SENSOR_SIDECAR_VERSION:
        return False
    if features.get("artifact_kind") != "pose_features_json":
        return False
    if features.get("local_path_included") is not False:
        return False
    if not _is_sha256(features.get("artifact_sha256")):
        return False
    if not _is_sha256(features.get("reservation_sha256")):
        return False
    if not _is_sha256(features.get("sealed_record_sha256")):
        return False

    metadata = features.get("media_metadata")
    if not isinstance(metadata, dict):
        return False
    if metadata.get("package_version") != POSE_PACKAGE_VERSION:
        return False
    if metadata.get("event_id") != event.get("event_id"):
        return False
    if metadata.get("episode_id") != event.get("episode_id"):
        return False
    if metadata.get("subject_id") != event.get("subject_id"):
        return False
    if not isinstance(metadata.get("sequence_id"), str) or not metadata["sequence_id"]:
        return False

    window = metadata.get("evidence_window_ms")
    if not isinstance(window, dict):
        return False
    if window.get("start_offset_ms") != observation.get("start_offset_ms"):
        return False
    if window.get("end_offset_ms") != observation.get("end_offset_ms"):
        return False
    if not isinstance(metadata.get("observation_count"), int) or metadata["observation_count"] < 1:
        return False
    if not isinstance(metadata.get("sample_count"), int) or metadata["sample_count"] < 1:
        return False
    if not isinstance(metadata.get("source_media_count"), int) or metadata["source_media_count"] < 1:
        return False
    if not _is_sha256(metadata.get("producer_fingerprint_sha256")):
        return False
    return True


def _sensor_support(
    event: dict[str, Any], modality: str
) -> tuple[list[str], list[str], list[str]]:
    eligible: list[str] = []
    late: list[str] = []
    invalid_provenance: list[str] = []
    for observation in event.get("observations", []):
        if observation.get("modality") != modality:
            continue
        ref = str(observation.get("observation_ref", "<unknown>"))
        if int(observation.get("end_offset_ms", 0)) > SENSOR_EVIDENCE_CUTOFF_MS:
            late.append(ref)
            continue
        if modality == "visual_pose" and not _valid_v1_package_provenance(observation, event):
            invalid_provenance.append(ref)
            continue
        eligible.append(ref)
    return sorted(eligible), sorted(late), sorted(invalid_provenance)


def _event_row(event: dict[str, Any]) -> dict[str, Any]:
    event_errors = validate_instance(event)
    ct1_errors = validate_capture_event(event) if not event_errors else []
    label, label_errors = _termination_label(event) if not event_errors else (None, [])

    observed_modalities = {
        str(observation.get("modality")) for observation in event.get("observations", [])
    }
    declared_missing = set(event.get("missing_modalities", []))
    modality_conflicts = sorted(observed_modalities & declared_missing)

    visual_refs, late_visual_refs, invalid_visual_refs = _sensor_support(event, "visual_pose")
    audio_refs, late_audio_refs, invalid_audio_refs = _sensor_support(event, "audio_vocalisation")

    reasons: list[str] = []
    reasons.extend(f"event_contract:{error}" for error in event_errors)
    reasons.extend(f"ct1_b0:{error}" for error in ct1_errors)
    reasons.extend(f"target:{error}" for error in label_errors)
    if modality_conflicts:
        reasons.append(
            "modality_present_and_declared_missing:" + ",".join(modality_conflicts)
        )
    if label is None and not label_errors:
        reasons.append("target:missing_or_unknown_termination_label")
    if invalid_visual_refs:
        reasons.append(
            "V1:visual_pose_observation_lacks_valid_pose_package_provenance:"
            + ",".join(invalid_visual_refs)
        )
    if not visual_refs:
        reasons.append("V1:no_visual_pose_observation_within_0_5000ms")
    if not audio_refs:
        reasons.append("A1:no_audio_vocalisation_observation_within_0_5000ms")

    b0_supported = not event_errors and not ct1_errors
    v1_supported = bool(visual_refs) and "visual_pose" not in declared_missing and not event_errors
    a1_supported = bool(audio_refs) and "audio_vocalisation" not in declared_missing and not event_errors
    target_supported = label is not None and not label_errors and not event_errors
    primary_eligible = (
        b0_supported
        and v1_supported
        and a1_supported
        and target_supported
        and not modality_conflicts
    )

    return {
        "event_id": event.get("event_id"),
        "episode_id": event.get("episode_id"),
        "subject_id": event.get("subject_id"),
        "household_id": event.get("household_id"),
        "session_id": event.get("session_id"),
        "start_time": event.get("time", {}).get("start_time"),
        "target": {
            "name": TARGET_NAME,
            "horizon_ms": TARGET_HORIZON_MS,
            "available": target_supported,
            "value": label,
        },
        "support": {
            "B0_context_routine": b0_supported,
            "V1_visual_pose": v1_supported,
            "A1_vocal_audio": a1_supported,
            "V1_A1": v1_supported and a1_supported,
            "B0_V1_A1": b0_supported and v1_supported and a1_supported,
        },
        "eligible_observation_refs": {
            "V1": visual_refs,
            "A1": audio_refs,
        },
        "post_evidence_cutoff_observation_refs": {
            "V1": late_visual_refs,
            "A1": late_audio_refs,
        },
        "invalid_provenance_observation_refs": {
            "V1": invalid_visual_refs,
            "A1": invalid_audio_refs,
        },
        "observed_modalities": sorted(observed_modalities),
        "declared_missing_modalities": sorted(declared_missing),
        "modality_conflicts": modality_conflicts,
        "primary_cohort_eligible": primary_eligible,
        "exclusion_reasons": sorted(set(reasons)),
    }


def build_manifest(events: list[dict[str, Any]]) -> dict[str, Any]:
    if not isinstance(events, list):
        raise ValueError("M1 input must be an array of #18 event objects")

    rows = [_event_row(event) for event in events]
    global_errors: list[str] = []
    for field in ("event_id", "episode_id"):
        values = [row.get(field) for row in rows]
        duplicates = sorted(
            value for value, count in Counter(values).items() if value is not None and count > 1
        )
        for value in duplicates:
            global_errors.append(f"duplicate {field}: {value}")

    primary_ids = sorted(
        str(row["episode_id"])
        for row in rows
        if row["primary_cohort_eligible"] and row.get("episode_id") is not None
    )

    support_counts = {
        "events_received": len(rows),
        "target_labelled": sum(row["target"]["available"] for row in rows),
        "B0": sum(row["support"]["B0_context_routine"] for row in rows),
        "V1": sum(row["support"]["V1_visual_pose"] for row in rows),
        "A1": sum(row["support"]["A1_vocal_audio"] for row in rows),
        "V1_A1": sum(row["support"]["V1_A1"] for row in rows),
        "B0_V1_A1": sum(row["support"]["B0_V1_A1"] for row in rows),
        "primary_complete_case_labelled": len(primary_ids),
    }

    missing_patterns: Counter[str] = Counter()
    for row in rows:
        v = row["support"]["V1_visual_pose"]
        a = row["support"]["A1_vocal_audio"]
        if v and a:
            pattern = "V1+A1"
        elif v:
            pattern = "V1_only"
        elif a:
            pattern = "A1_only"
        else:
            pattern = "neither"
        missing_patterns[pattern] += 1

    shared_ablation_episode_ids = {
        row_id: list(primary_ids) for row_id in PRIMARY_ABLATION_ROWS
    }

    return {
        "manifest_version": "M1.2-v0",
        "performance_analysis_performed": False,
        "target": {
            "name": TARGET_NAME,
            "horizon_ms": TARGET_HORIZON_MS,
        },
        "sensor_evidence_window_ms": [0, SENSOR_EVIDENCE_CUTOFF_MS],
        "primary_cohort_rule": "strict B0/CT1 + boolean termination target + provenance-valid V1 + A1 on the same episode",
        "global_integrity_errors": global_errors,
        "support_counts": support_counts,
        "modality_pattern_counts": dict(sorted(missing_patterns.items())),
        "primary_episode_ids": primary_ids,
        "primary_episode_sha256": _digest_ids(primary_ids),
        "ablation_episode_ids": shared_ablation_episode_ids,
        "events": sorted(rows, key=lambda row: (str(row.get("start_time")), str(row.get("event_id")))),
    }


def validate_manifest(manifest: dict[str, Any]) -> list[str]:
    errors = list(manifest.get("global_integrity_errors", []))
    primary = manifest.get("primary_episode_ids", [])
    if manifest.get("primary_episode_sha256") != _digest_ids(primary):
        errors.append("primary_episode_sha256 mismatch")
    matrix = manifest.get("ablation_episode_ids", {})
    for row_id in PRIMARY_ABLATION_ROWS:
        if matrix.get(row_id) != primary:
            errors.append(f"{row_id}: ablation cohort differs from frozen primary cohort")
    if manifest.get("performance_analysis_performed") is not False:
        errors.append("M1.2 manifest must remain performance-blind")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a performance-blind M1 modality-readiness and shared-cohort manifest")
    parser.add_argument("events", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    payload = json.loads(args.events.read_text(encoding="utf-8"))
    manifest = build_manifest(payload)
    errors = validate_manifest(manifest)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"manifest_valid": not errors, "errors": errors, "support_counts": manifest["support_counts"]}, indent=2))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
