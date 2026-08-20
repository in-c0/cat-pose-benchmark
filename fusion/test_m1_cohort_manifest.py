from __future__ import annotations

import copy
import unittest

from fusion.fixtures.m1_cohort_events import build_events
from fusion.m1_cohort_manifest import (
    PRIMARY_ABLATION_ROWS,
    build_manifest,
    validate_manifest,
)


def _row(manifest: dict, token: str) -> dict:
    return next(row for row in manifest["events"] if token in row["event_id"])


def _visual_observation(event: dict) -> dict:
    return next(
        observation
        for observation in event["observations"]
        if observation["modality"] == "visual_pose"
    )


class M1CohortManifestTests(unittest.TestCase):
    def test_primary_cohort_is_exact_complete_case_intersection(self) -> None:
        manifest = build_manifest(build_events())
        self.assertEqual([], validate_manifest(manifest))
        self.assertEqual(2, manifest["support_counts"]["primary_complete_case_labelled"])
        self.assertEqual(
            [
                "m1-episode-complete-false-01",
                "m1-episode-complete-true-00",
            ],
            manifest["primary_episode_ids"],
        )
        for row_id in PRIMARY_ABLATION_ROWS:
            self.assertEqual(
                manifest["primary_episode_ids"],
                manifest["ablation_episode_ids"][row_id],
            )

    def test_support_counts_do_not_hide_missing_modalities(self) -> None:
        manifest = build_manifest(build_events())
        self.assertEqual(7, manifest["support_counts"]["events_received"])
        self.assertEqual(6, manifest["support_counts"]["target_labelled"])
        self.assertEqual(7, manifest["support_counts"]["B0"])
        self.assertEqual(6, manifest["support_counts"]["V1"])
        self.assertEqual(4, manifest["support_counts"]["A1"])
        self.assertEqual(3, manifest["support_counts"]["V1_A1"])
        self.assertEqual(
            {"A1_only": 1, "V1+A1": 3, "V1_only": 3},
            manifest["modality_pattern_counts"],
        )

    def test_modality_name_alone_cannot_create_v1_support(self) -> None:
        events = build_events()
        event = next(item for item in events if "complete-true" in item["event_id"])
        visual = _visual_observation(event)
        visual["schema_ref"] = "schemas/observation.schema.json"
        visual["features"] = {"synthetic_hand_authored_pose": True}

        manifest = build_manifest(events)
        row = _row(manifest, "complete-true")
        self.assertFalse(row["support"]["V1_visual_pose"])
        self.assertFalse(row["primary_cohort_eligible"])
        self.assertEqual([visual["observation_ref"]], row["invalid_provenance_observation_refs"]["V1"])
        self.assertTrue(any("lacks_valid_pose_package_provenance" in reason for reason in row["exclusion_reasons"]))

    def test_forged_pose_package_identity_cannot_create_v1_support(self) -> None:
        events = build_events()
        event = next(item for item in events if "complete-true" in item["event_id"])
        visual = _visual_observation(event)
        visual["features"]["media_metadata"]["subject_id"] = "other-cat"

        manifest = build_manifest(events)
        row = _row(manifest, "complete-true")
        self.assertFalse(row["support"]["V1_visual_pose"])
        self.assertFalse(row["primary_cohort_eligible"])
        self.assertEqual([visual["observation_ref"]], row["invalid_provenance_observation_refs"]["V1"])

    def test_non_sha_provenance_marker_cannot_create_v1_support(self) -> None:
        events = build_events()
        event = next(item for item in events if "complete-true" in item["event_id"])
        visual = _visual_observation(event)
        visual["features"]["artifact_sha256"] = "g" * 64

        manifest = build_manifest(events)
        row = _row(manifest, "complete-true")
        self.assertFalse(row["support"]["V1_visual_pose"])
        self.assertFalse(row["primary_cohort_eligible"])
        self.assertEqual([visual["observation_ref"]], row["invalid_provenance_observation_refs"]["V1"])

    def test_post_cutoff_audio_is_flagged_and_not_used(self) -> None:
        manifest = build_manifest(build_events())
        row = _row(manifest, "late-audio")
        self.assertFalse(row["support"]["A1_vocal_audio"])
        self.assertTrue(row["post_evidence_cutoff_observation_refs"]["A1"])
        self.assertTrue(any("0_5000ms" in reason for reason in row["exclusion_reasons"]))
        self.assertFalse(row["primary_cohort_eligible"])

    def test_present_but_declared_missing_modality_is_excluded(self) -> None:
        manifest = build_manifest(build_events())
        row = _row(manifest, "audio-conflict")
        self.assertIn("audio_vocalisation", row["modality_conflicts"])
        self.assertFalse(row["support"]["A1_vocal_audio"])
        self.assertFalse(row["primary_cohort_eligible"])

    def test_unknown_target_is_retained_with_explicit_reason(self) -> None:
        manifest = build_manifest(build_events())
        row = _row(manifest, "unknown-target")
        self.assertFalse(row["target"]["available"])
        self.assertIsNone(row["target"]["value"])
        self.assertTrue(any("missing_or_unknown" in reason for reason in row["exclusion_reasons"]))

    def test_false_label_must_be_observed_at_horizon(self) -> None:
        events = build_events()
        event = next(item for item in events if "complete-false" in item["event_id"])
        event["outcomes"][0]["start_offset_ms"] = 30_000
        event["outcomes"][0]["end_offset_ms"] = 30_000
        manifest = build_manifest(events)
        row = _row(manifest, "complete-false")
        self.assertFalse(row["target"]["available"])
        self.assertTrue(any("frozen 60 s horizon" in reason for reason in row["exclusion_reasons"]))

    def test_contradictory_termination_labels_are_excluded(self) -> None:
        events = build_events()
        event = next(item for item in events if "complete-true" in item["event_id"])
        event["outcomes"].append(
            {
                "outcome_id": "synthetic-contradiction",
                "outcome_type": "signalling_termination",
                "start_offset_ms": 60_000,
                "end_offset_ms": 60_000,
                "observation_source": "human_annotation",
                "signalling_terminated": False,
            }
        )
        manifest = build_manifest(events)
        row = _row(manifest, "complete-true")
        self.assertFalse(row["target"]["available"])
        self.assertTrue(any("contradictory" in reason for reason in row["exclusion_reasons"]))

    def test_duplicate_episode_id_is_global_integrity_failure(self) -> None:
        events = build_events()
        events[1]["episode_id"] = events[0]["episode_id"]
        manifest = build_manifest(events)
        errors = validate_manifest(manifest)
        self.assertTrue(any("duplicate episode_id" in error for error in errors), errors)

    def test_invalid_shared_event_is_flagged_not_silently_scored(self) -> None:
        events = build_events()
        events[0]["time"]["end_offset_ms"] = 2_000
        manifest = build_manifest(events)
        row = _row(manifest, "complete-true")
        self.assertFalse(row["support"]["B0_context_routine"])
        self.assertFalse(row["primary_cohort_eligible"])
        self.assertTrue(any(reason.startswith("event_contract:") for reason in row["exclusion_reasons"]))

    def test_manifest_remains_performance_blind(self) -> None:
        manifest = build_manifest(build_events())
        self.assertFalse(manifest["performance_analysis_performed"])
        rendered = str(manifest).lower()
        for forbidden in ("log_loss", "balanced_accuracy", "macro_f1", "coefficient", "feature_importance"):
            self.assertNotIn(forbidden, rendered)


if __name__ == "__main__":
    unittest.main()
