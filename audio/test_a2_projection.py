from __future__ import annotations

import copy
import json
import unittest

from audio.a2_projection import project_passive_context, validate_score_packet


CLASSES = [
    {"class_id": "/m/purr", "display_name": "Purr"},
    {"class_id": "/m/scratch", "display_name": "Scratch"},
    {"class_id": "/m/dj-scratch", "display_name": "Scratching (performance technique)"},
    {"class_id": "/m/chew", "display_name": "Chewing, mastication"},
    {"class_id": "/m/liquid", "display_name": "Liquid"},
    {"class_id": "/m/speech", "display_name": "Speech"},
]


def build_packet() -> dict:
    return {
        "packet_version": "A2-score-packet-v0",
        "event_id": "event-a2-001",
        "episode_id": "episode-a2-001",
        "source_audio": {
            "artifact_sha256": "a" * 64,
            "sealed_record_sha256": "b" * 64,
            "start_offset_ms": 0,
            "end_offset_ms": 5_000,
        },
        "source_model": {
            "name": "synthetic-generic-audio-fixture",
            "version": "0",
            "model_family": "software_test_only",
            "weights_sha256": "c" * 64,
            "class_map_sha256": "d" * 64,
            "code_revision": "test-fixture",
        },
        "class_map": copy.deepcopy(CLASSES),
        "frames": [
            {
                "frame_index": 0,
                "start_offset_ms": 0,
                "end_offset_ms": 960,
                "scores": [0.80, 0.10, 0.90, 0.20, 0.05, 0.10],
            },
            {
                "frame_index": 1,
                "start_offset_ms": 480,
                "end_offset_ms": 1_440,
                "scores": [0.60, 0.70, 0.95, 0.40, 0.30, 0.05],
            },
            {
                "frame_index": 2,
                "start_offset_ms": 960,
                "end_offset_ms": 1_920,
                "scores": [0.20, 0.30, 0.99, 0.90, 0.75, 0.15],
            },
        ],
        "semantic_ground_truth": False,
        "notes": "Synthetic model-score fixture; no audio or feline evidence.",
    }


class A2ProjectionTests(unittest.TestCase):
    def test_valid_packet_projects_only_weak_context_features(self) -> None:
        packet = build_packet()
        self.assertEqual([], validate_score_packet(packet))
        report = project_passive_context(packet)

        self.assertFalse(report["semantic_ground_truth"])
        self.assertFalse(report["intent_inference_performed"])
        self.assertFalse(report["performance_analysis_performed"])
        self.assertEqual("a" * 64, report["source_audio_artifact_sha256"])
        self.assertEqual("b" * 64, report["source_audio_sealed_record_sha256"])

        features = report["fit_features"]
        self.assertAlmostEqual((0.80 + 0.60 + 0.20) / 3.0, features["a2_purr_acoustic_mean"])
        self.assertAlmostEqual(0.80, features["a2_purr_acoustic_max"])
        self.assertAlmostEqual((0.10 + 0.70 + 0.30) / 3.0, features["a2_surface_contact_proxy_mean"])
        self.assertAlmostEqual(0.70, features["a2_surface_contact_proxy_max"])
        self.assertAlmostEqual((0.20 + 0.40 + 0.90) / 3.0, features["a2_ingestion_sound_proxy_mean"])
        self.assertAlmostEqual(0.90, features["a2_ingestion_sound_proxy_max"])
        self.assertAlmostEqual((0.05 + 0.30 + 0.75) / 3.0, features["a2_liquid_sound_proxy_mean"])
        self.assertAlmostEqual(0.75, features["a2_liquid_sound_proxy_max"])

    def test_dj_scratching_does_not_count_as_surface_contact(self) -> None:
        packet = build_packet()
        report = project_passive_context(packet)
        surface = report["projection_groups"]["surface_contact_proxy"]
        self.assertEqual(["Scratch"], surface["matched_source_classes"])
        self.assertNotIn("Scratching (performance technique)", surface["matched_source_classes"])
        # The deliberately huge DJ-scratching scores therefore cannot drive this proxy.
        self.assertAlmostEqual(0.70, report["fit_features"]["a2_surface_contact_proxy_max"])

    def test_purr_score_does_not_create_affective_claim(self) -> None:
        report = project_passive_context(build_packet())
        rendered = json.dumps(report).lower()
        self.assertIn("purr_acoustic", rendered)
        for forbidden in (
            "contentment",
            "relaxed pleasure",
            "cat_eating",
            "cat_drinking",
            "cat_scratching",
            "hunger_state",
            "thirst_state",
        ):
            self.assertNotIn(forbidden, rendered)

    def test_missing_taxonomy_group_is_explicit_null_not_silent_zero(self) -> None:
        packet = build_packet()
        keep = [0, 1, 2, 3, 5]  # remove Liquid
        packet["class_map"] = [packet["class_map"][index] for index in keep]
        for frame in packet["frames"]:
            frame["scores"] = [frame["scores"][index] for index in keep]
        report = project_passive_context(packet)
        self.assertFalse(report["projection_groups"]["liquid_sound_proxy"]["available"])
        self.assertIsNone(report["fit_features"]["a2_liquid_sound_proxy_mean"])
        self.assertIsNone(report["fit_features"]["a2_liquid_sound_proxy_max"])

    def test_score_vector_must_match_declared_class_map(self) -> None:
        packet = build_packet()
        packet["frames"][0]["scores"].pop()
        errors = validate_score_packet(packet)
        self.assertTrue(any("does not match class_map length" in error for error in errors), errors)

    def test_frame_must_remain_inside_frozen_audio_window(self) -> None:
        packet = build_packet()
        packet["source_audio"]["end_offset_ms"] = 1_500
        errors = validate_score_packet(packet)
        self.assertTrue(any("outside immutable source-audio window" in error for error in errors), errors)

    def test_post_5000ms_evidence_fails_closed(self) -> None:
        packet = build_packet()
        packet["frames"][-1]["start_offset_ms"] = 4_500
        packet["frames"][-1]["end_offset_ms"] = 5_001
        errors = validate_score_packet(packet)
        self.assertTrue(errors)
        self.assertTrue(any("5000" in error for error in errors), errors)

    def test_packet_can_be_bound_to_exact_ct1_a1_event_and_audio_seal(self) -> None:
        packet = build_packet()
        self.assertEqual(
            [],
            validate_score_packet(
                packet,
                expected_event_id="event-a2-001",
                expected_episode_id="episode-a2-001",
                expected_audio_artifact_sha256="a" * 64,
                expected_audio_seal_sha256="b" * 64,
            ),
        )
        errors = validate_score_packet(
            packet,
            expected_event_id="wrong-event",
            expected_audio_artifact_sha256="e" * 64,
            expected_audio_seal_sha256="f" * 64,
        )
        self.assertTrue(any("event_id" in error for error in errors), errors)
        self.assertTrue(any("artifact_sha256" in error for error in errors), errors)
        self.assertTrue(any("seal" in error for error in errors), errors)

    def test_semantic_ground_truth_true_is_rejected_by_schema(self) -> None:
        packet = build_packet()
        packet["semantic_ground_truth"] = True
        errors = validate_score_packet(packet)
        self.assertTrue(any("semantic_ground_truth" in error for error in errors), errors)

    def test_projection_fingerprint_is_sensitive_to_provenance_not_scores(self) -> None:
        packet = build_packet()
        original = project_passive_context(packet)

        changed_scores = copy.deepcopy(packet)
        changed_scores["frames"][0]["scores"][0] = 0.01
        changed_score_report = project_passive_context(changed_scores)
        # Fingerprint identifies the source/model/frame-timing contract; feature values
        # remain the separate projection output and can vary without changing lineage.
        self.assertEqual(
            original["projection_input_fingerprint_sha256"],
            changed_score_report["projection_input_fingerprint_sha256"],
        )
        self.assertNotEqual(original["fit_features"], changed_score_report["fit_features"])

        changed_provenance = copy.deepcopy(packet)
        changed_provenance["source_audio"]["artifact_sha256"] = "e" * 64
        changed_provenance_report = project_passive_context(changed_provenance)
        self.assertNotEqual(
            original["projection_input_fingerprint_sha256"],
            changed_provenance_report["projection_input_fingerprint_sha256"],
        )

    def test_frame_timing_must_be_monotone_but_overlap_is_allowed(self) -> None:
        packet = build_packet()
        self.assertEqual([], validate_score_packet(packet))  # 0.96 s window / 0.48 s hop overlaps.
        packet["frames"][2]["start_offset_ms"] = 100
        packet["frames"][2]["end_offset_ms"] = 1_800
        errors = validate_score_packet(packet)
        self.assertTrue(any("non-decreasing" in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main()
