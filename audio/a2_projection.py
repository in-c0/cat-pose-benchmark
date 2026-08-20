from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
from jsonschema import Draft202012Validator, FormatChecker

PACKET_VERSION = "A2-score-packet-v0"
PROJECTION_VERSION = "A2-passive-context-v0"
SCHEMA_PATH = Path(__file__).with_name("a2_score_packet.schema.json")
EVIDENCE_CUTOFF_MS = 5_000
ACTIVE_SCORE_THRESHOLD = 0.25

# Exact external-taxonomy display names only. These are acoustic proxies, not feline
# action labels. In particular, generic surface/ingestion/liquid classes do not imply
# the cat caused the sound.
PROJECTION_GROUPS: dict[str, dict[str, Any]] = {
    "purr_acoustic": {
        "source_specificity": "cat_specific_acoustic",
        "source_classes": ("Purr",),
    },
    "surface_contact_proxy": {
        "source_specificity": "generic_sound_proxy",
        "source_classes": ("Scratch", "Scrape", "Rub"),
    },
    "ingestion_sound_proxy": {
        "source_specificity": "generic_sound_proxy",
        "source_classes": ("Chewing, mastication", "Biting"),
    },
    "liquid_sound_proxy": {
        "source_specificity": "generic_sound_proxy",
        "source_classes": (
            "Liquid",
            "Splash, splatter",
            "Drip",
            "Pour",
            "Fill (with liquid)",
        ),
    },
}

# These would turn a weak acoustic proxy into an unsupported feline/affective claim.
# The report is allowed to contain explicit metadata such as
# `intent_inference_performed: false` and prose saying intent ground truth was *not*
# produced, so the generic word "intent" is intentionally not banned here.
FORBIDDEN_OUTPUT_TOKENS = (
    "cat_eating",
    "cat_drinking",
    "cat_scratching",
    "contentment",
    "relaxed_pleasure",
    "hunger_state",
    "thirst_state",
)


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _canonical_json(payload: Any) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def validate_score_packet(
    payload: Any,
    *,
    expected_event_id: str | None = None,
    expected_episode_id: str | None = None,
    expected_audio_artifact_sha256: str | None = None,
    expected_audio_seal_sha256: str | None = None,
) -> list[str]:
    schema = _load_json(SCHEMA_PATH)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors: list[str] = []
    for error in sorted(validator.iter_errors(payload), key=lambda item: list(item.absolute_path)):
        path = ".".join(str(part) for part in error.absolute_path) or "<root>"
        errors.append(f"schema.{path}: {error.message}")
    if errors or not isinstance(payload, dict):
        return errors or ["schema.<root>: A2 score packet must be an object"]

    if expected_event_id is not None and payload["event_id"] != expected_event_id:
        errors.append("event_id does not match expected CT1/A1 event")
    if expected_episode_id is not None and payload["episode_id"] != expected_episode_id:
        errors.append("episode_id does not match expected CT1/A1 episode")

    source_audio = payload["source_audio"]
    if expected_audio_artifact_sha256 is not None and (
        source_audio["artifact_sha256"].lower() != expected_audio_artifact_sha256.lower()
    ):
        errors.append("source_audio.artifact_sha256 does not match expected immutable A1 audio artifact")
    if expected_audio_seal_sha256 is not None and (
        source_audio["sealed_record_sha256"].lower() != expected_audio_seal_sha256.lower()
    ):
        errors.append("source_audio.sealed_record_sha256 does not match expected A1 seal")

    audio_start = float(source_audio["start_offset_ms"])
    audio_end = float(source_audio["end_offset_ms"])
    if audio_start >= audio_end:
        errors.append("source_audio: start_offset_ms must precede end_offset_ms")
    if audio_end > EVIDENCE_CUTOFF_MS:
        errors.append(f"source_audio: end_offset_ms exceeds frozen {EVIDENCE_CUTOFF_MS} ms evidence cutoff")

    class_map = payload["class_map"]
    class_ids = [item["class_id"] for item in class_map]
    display_names = [item["display_name"] for item in class_map]
    if len(class_ids) != len(set(class_ids)):
        errors.append("class_map: class_id values must be unique")
    if len(display_names) != len(set(display_names)):
        errors.append("class_map: display_name values must be unique for deterministic projection")

    frames = payload["frames"]
    frame_indices = [item["frame_index"] for item in frames]
    if len(frame_indices) != len(set(frame_indices)):
        errors.append("frames: frame_index values must be unique")

    previous_start = -math.inf
    previous_end = -math.inf
    for index, frame in enumerate(frames):
        start = float(frame["start_offset_ms"])
        end = float(frame["end_offset_ms"])
        if start >= end:
            errors.append(f"frames.{index}: start_offset_ms must precede end_offset_ms")
        if start < audio_start or end > audio_end:
            errors.append(
                f"frames.{index}: frame interval {start}-{end} ms lies outside immutable source-audio window {audio_start}-{audio_end} ms"
            )
        if end > EVIDENCE_CUTOFF_MS:
            errors.append(f"frames.{index}: post-{EVIDENCE_CUTOFF_MS}ms evidence is forbidden")
        if start < previous_start or end < previous_end:
            errors.append("frames: frame timing must be non-decreasing")
        previous_start = start
        previous_end = end
        if len(frame["scores"]) != len(class_map):
            errors.append(
                f"frames.{index}.scores: length {len(frame['scores'])} does not match class_map length {len(class_map)}"
            )
        for score_index, score in enumerate(frame["scores"]):
            if not math.isfinite(float(score)):
                errors.append(f"frames.{index}.scores.{score_index}: score must be finite")

    return errors


def _group_frame_scores(
    scores: np.ndarray,
    class_names: list[str],
    source_classes: tuple[str, ...],
) -> tuple[np.ndarray | None, list[str]]:
    indices = [index for index, name in enumerate(class_names) if name in source_classes]
    matched = [class_names[index] for index in indices]
    if not indices:
        return None, []
    return scores[:, indices].max(axis=1), matched


def project_passive_context(payload: dict[str, Any]) -> dict[str, Any]:
    errors = validate_score_packet(payload)
    if errors:
        raise ValueError("invalid A2 score packet:\n- " + "\n- ".join(errors))

    class_names = [item["display_name"] for item in payload["class_map"]]
    scores = np.asarray([frame["scores"] for frame in payload["frames"]], dtype=float)
    fit_features: dict[str, float | None] = {}
    feature_manifest: list[dict[str, Any]] = []
    projection_groups: dict[str, Any] = {}

    for group_name, group in PROJECTION_GROUPS.items():
        frame_scores, matched = _group_frame_scores(
            scores,
            class_names,
            group["source_classes"],
        )
        available = frame_scores is not None
        mean_name = f"a2_{group_name}_mean"
        max_name = f"a2_{group_name}_max"
        fit_features[mean_name] = None if frame_scores is None else float(np.mean(frame_scores))
        fit_features[max_name] = None if frame_scores is None else float(np.max(frame_scores))
        for feature_name, aggregation in ((mean_name, "mean_of_per_frame_group_max"), (max_name, "max_of_per_frame_group_max")):
            feature_manifest.append(
                {
                    "name": feature_name,
                    "family": "audio_nonvocal_proxy",
                    "semantic_role": "predictor",
                    "source_specificity": group["source_specificity"],
                    "aggregation": aggregation,
                    "source_classes": list(group["source_classes"]),
                    "matched_source_classes": matched,
                    "semantic_ground_truth": False,
                }
            )
        projection_groups[group_name] = {
            "available": available,
            "source_specificity": group["source_specificity"],
            "configured_source_classes": list(group["source_classes"]),
            "matched_source_classes": matched,
        }

    top_scores = scores.max(axis=1)
    active_counts = (scores >= ACTIVE_SCORE_THRESHOLD).sum(axis=1)
    fit_features["a2_generic_activity_top_score_mean"] = float(np.mean(top_scores))
    fit_features["a2_generic_activity_active_class_count_mean"] = float(np.mean(active_counts))
    feature_manifest.extend(
        [
            {
                "name": "a2_generic_activity_top_score_mean",
                "family": "audio_generic_activity",
                "semantic_role": "predictor",
                "source_specificity": "generic_sound_proxy",
                "aggregation": "mean_per_frame_top_class_score",
                "source_classes": [],
                "matched_source_classes": [],
                "semantic_ground_truth": False,
            },
            {
                "name": "a2_generic_activity_active_class_count_mean",
                "family": "audio_generic_activity",
                "semantic_role": "predictor",
                "source_specificity": "generic_sound_proxy",
                "aggregation": f"mean_per_frame_count_score_gte_{ACTIVE_SCORE_THRESHOLD}",
                "source_classes": [],
                "matched_source_classes": [],
                "semantic_ground_truth": False,
            },
        ]
    )

    source_audio = payload["source_audio"]
    source_model = payload["source_model"]
    provenance_payload = {
        "event_id": payload["event_id"],
        "episode_id": payload["episode_id"],
        "source_audio": source_audio,
        "source_model": source_model,
        "class_map": payload["class_map"],
        "frames": [
            {
                "frame_index": frame["frame_index"],
                "start_offset_ms": frame["start_offset_ms"],
                "end_offset_ms": frame["end_offset_ms"],
            }
            for frame in payload["frames"]
        ],
    }

    report = {
        "projection_version": PROJECTION_VERSION,
        "event_id": payload["event_id"],
        "episode_id": payload["episode_id"],
        "performance_analysis_performed": False,
        "semantic_ground_truth": False,
        "intent_inference_performed": False,
        "evidence_window_ms": [source_audio["start_offset_ms"], source_audio["end_offset_ms"]],
        "source_audio_artifact_sha256": source_audio["artifact_sha256"].lower(),
        "source_audio_sealed_record_sha256": source_audio["sealed_record_sha256"].lower(),
        "source_model": source_model,
        "projection_groups": projection_groups,
        "feature_manifest": sorted(feature_manifest, key=lambda item: item["name"]),
        "fit_features": dict(sorted(fit_features.items())),
        "projection_input_fingerprint_sha256": hashlib.sha256(_canonical_json(provenance_payload)).hexdigest(),
        "claims_boundary": "generic acoustic proxies only; no source-attribution, feline-action, affect or intent ground truth",
    }

    rendered = json.dumps(report, sort_keys=True).lower()
    forbidden = [token for token in FORBIDDEN_OUTPUT_TOKENS if token in rendered]
    if forbidden:
        raise AssertionError(f"A2 projection emitted forbidden feline semantic token(s): {forbidden}")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Project timestamped generic acoustic event scores into A2 weak context features")
    parser.add_argument("packet", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    payload = _load_json(args.packet)
    report = project_passive_context(payload)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "projection_version": report["projection_version"],
                "feature_count": len(report["fit_features"]),
                "semantic_ground_truth": report["semantic_ground_truth"],
                "intent_inference_performed": report["intent_inference_performed"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
