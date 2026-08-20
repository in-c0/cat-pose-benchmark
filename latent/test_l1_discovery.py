from __future__ import annotations

import copy
import inspect
import json
import math
import unittest

from sklearn.metrics import adjusted_rand_score

from latent.fixtures import build_identity_confounded_fixture, build_recoverable_fixture
from latent.l1_discovery import (
    K_VALUES,
    RANDOM_SEED,
    STABILITY_REPEATS,
    _fit_latent_structure,
    extract_fit_matrix,
    run_discovery,
    validate_input,
)


class L1DiscoveryTests(unittest.TestCase):
    def test_recoverable_fixture_is_valid_and_recovers_opaque_three_state_structure(self) -> None:
        payload, truth = build_recoverable_fixture()
        self.assertEqual([], validate_input(payload))
        report = run_discovery(payload)
        row = next(item for item in report["per_k"] if item["k"] == 3)
        self.assertTrue(row["eligible"])
        self.assertGreater(row["stability_mean_pairwise_ari"], 0.80)
        ari = adjusted_rand_score(truth, row["cluster_ids"])
        self.assertGreater(ari, 0.90)
        self.assertFalse(row["identity_confound_warning"])
        self.assertTrue(all(cluster.startswith("L1-Z03-c") for cluster in row["cluster_ids"]))

    def test_identity_dominated_fixture_is_flagged_as_nuisance_not_named(self) -> None:
        payload = build_identity_confounded_fixture()
        report = run_discovery(payload)
        row = next(item for item in report["per_k"] if item["k"] == 4)
        self.assertGreater(row["stability_mean_pairwise_ari"], 0.80)
        self.assertGreater(row["audit_associations"]["subject_id_ami"], 0.90)
        self.assertTrue(row["identity_confound_warning"])
        self.assertFalse(report["semantic_naming_performed"])
        rendered = json.dumps(report).lower()
        for forbidden in (
            "intent_name",
            "cluster_name",
            "translation_text",
            "hunger_state",
            "play_state",
        ):
            self.assertNotIn(forbidden, rendered)

    def test_fitter_signature_cannot_receive_audit_columns(self) -> None:
        signature = inspect.signature(_fit_latent_structure)
        parameters = set(signature.parameters)
        for forbidden in (
            "subject_id",
            "household_id",
            "session_id",
            "context_bucket",
            "observable_outcome",
            "audit_only",
            "labels",
        ):
            self.assertNotIn(forbidden, parameters)

        payload, _ = build_recoverable_fixture(60)
        X, names, families = extract_fit_matrix(payload)
        self.assertEqual((60, 3), X.shape)
        self.assertEqual(["audio_shape_0", "visual_motion_0", "routine_phase_0"], names)
        self.assertEqual(["audio", "visual", "routine"], families)

    def test_forbidden_semantic_or_future_feature_names_fail_closed(self) -> None:
        payload, _ = build_recoverable_fixture(60)
        payload["feature_manifest"][0]["name"] = "human_intent_label"
        for episode in payload["episodes"]:
            value = episode["fit_features"].pop("audio_shape_0")
            episode["fit_features"]["human_intent_label"] = value
        errors = validate_input(payload)
        self.assertTrue(any("forbidden semantic/future" in error for error in errors), errors)

        payload, _ = build_recoverable_fixture(60)
        payload["feature_manifest"][0]["name"] = "outcome_after_60s"
        for episode in payload["episodes"]:
            value = episode["fit_features"].pop("audio_shape_0")
            episode["fit_features"]["outcome_after_60s"] = value
        errors = validate_input(payload)
        self.assertTrue(any("forbidden semantic/future" in error for error in errors), errors)

    def test_feature_keys_must_exactly_match_manifest(self) -> None:
        payload, _ = build_recoverable_fixture(60)
        payload["episodes"][0]["fit_features"]["mystery"] = 1.0
        errors = validate_input(payload)
        self.assertTrue(any("keys must exactly match" in error for error in errors), errors)

    def test_non_finite_and_all_null_predictors_fail_closed(self) -> None:
        payload, _ = build_recoverable_fixture(60)
        payload["episodes"][0]["fit_features"]["audio_shape_0"] = math.inf
        errors = validate_input(payload)
        self.assertTrue(any("finite or null" in error for error in errors), errors)

        payload, _ = build_recoverable_fixture(60)
        for episode in payload["episodes"]:
            episode["fit_features"]["audio_shape_0"] = None
        errors = validate_input(payload)
        self.assertTrue(any("null for every episode" in error for error in errors), errors)

    def test_audit_only_mutation_cannot_change_cluster_assignments(self) -> None:
        payload, _ = build_recoverable_fixture(90)
        original = run_discovery(payload)
        mutated = copy.deepcopy(payload)
        for index, episode in enumerate(mutated["episodes"]):
            episode["audit_only"]["context_bucket"] = f"rewritten-{index % 7}"
            episode["audit_only"]["observable_outcome"] = f"changed-{index % 5}"
            episode["subject_id"] = f"renamed-cat-{index % 11}"
            episode["household_id"] = f"renamed-hh-{index % 4}"
            episode["session_id"] = f"renamed-session-{index // 3}"
        changed = run_discovery(mutated)
        for k in K_VALUES:
            a = next(item for item in original["per_k"] if item["k"] == k)
            b = next(item for item in changed["per_k"] if item["k"] == k)
            self.assertEqual(a.get("cluster_ids"), b.get("cluster_ids"))
            self.assertEqual(a.get("silhouette"), b.get("silhouette"))
            self.assertEqual(
                a.get("stability_mean_pairwise_ari"),
                b.get("stability_mean_pairwise_ari"),
            )

    def test_method_is_frozen_and_report_does_not_claim_advancement(self) -> None:
        payload, _ = build_recoverable_fixture(60)
        report = run_discovery(payload)
        self.assertEqual(list(K_VALUES), report["frozen_method"]["k_values"])
        self.assertEqual(STABILITY_REPEATS, report["frozen_method"]["stability_repeats"])
        self.assertEqual(RANDOM_SEED, report["frozen_method"]["random_seed"])
        self.assertFalse(report["performance_analysis_performed"])
        self.assertEqual(
            "not_evaluated_l1_0_requires_downstream_predictive_value_beyond_B0",
            report["advancement_decision"],
        )
        for row in report["per_k"]:
            if row.get("eligible"):
                self.assertEqual(
                    {"audio", "routine", "visual"},
                    set(row["drop_one_feature_family"]),
                )

    def test_run_is_deterministic(self) -> None:
        payload, _ = build_recoverable_fixture(60)
        a = run_discovery(payload)
        b = run_discovery(payload)
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
