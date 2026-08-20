from __future__ import annotations

import copy
import unittest

from fusion.fixtures.m1_synthetic_report import build_report
from fusion.m1_result_guard import validate_report, validation_summary


def _row(report: dict, row_id: str) -> dict:
    return next(row for row in report["rows"] if row["id"] == row_id)


class M1ResultGuardTests(unittest.TestCase):
    def test_complete_synthetic_report_is_contract_valid_and_advance_eligible(self) -> None:
        report = build_report(request_advance=True)
        self.assertEqual([], validate_report(report))
        summary = validation_summary(report)
        self.assertTrue(summary["contract_valid"])
        self.assertTrue(summary["advancement_eligible"])

    def test_complete_null_report_can_be_valid_without_advancement_request(self) -> None:
        report = build_report(request_advance=False)
        _row(report, "BVA")["metrics"]["log_loss"] = 0.70
        self.assertEqual([], validate_report(report))
        summary = validation_summary(report)
        self.assertTrue(summary["contract_valid"])
        self.assertFalse(summary["advancement_eligible"])

    def test_omitted_poor_ablation_is_rejected(self) -> None:
        report = build_report()
        report["rows"] = [row for row in report["rows"] if row["id"] != "A"]
        errors = validate_report(report)
        self.assertTrue(any("missing required ablation rows" in item for item in errors), errors)

    def test_primary_rows_must_use_exact_same_held_out_episodes(self) -> None:
        report = build_report()
        row = _row(report, "BA")
        row["evaluation_episode_ids"] = row["evaluation_episode_ids"][:-1]
        from fusion.m1_result_guard import _episode_digest
        row["evaluation_episode_sha256"] = _episode_digest(row["evaluation_episode_ids"])
        errors = validate_report(report)
        self.assertTrue(any("exact same held-out episodes" in item for item in errors), errors)

    def test_row_target_or_horizon_cannot_drift(self) -> None:
        report = build_report()
        _row(report, "V")["target"]["horizon_seconds"] = 30
        errors = validate_report(report)
        self.assertTrue(any("target/horizon differs" in item for item in errors), errors)

    def test_missing_leakage_probe_is_rejected(self) -> None:
        report = build_report()
        del report["leakage_probes"]["device_source"]
        errors = validate_report(report)
        self.assertIn("missing leakage probe: device_source", errors)

    def test_missing_calibration_metric_is_rejected(self) -> None:
        report = build_report()
        del _row(report, "BVA")["metrics"]["ece"]
        errors = validate_report(report)
        self.assertIn("BVA: missing metric ece", errors)

    def test_missing_dropout_row_is_rejected(self) -> None:
        report = build_report()
        report["rows"] = [row for row in report["rows"] if row["id"] != "BVA-A"]
        errors = validate_report(report)
        self.assertTrue(any("BVA-A" in item for item in errors), errors)

    def test_bad_episode_digest_is_rejected(self) -> None:
        report = build_report()
        _row(report, "V")["evaluation_episode_sha256"] = "0" * 64
        errors = validate_report(report)
        self.assertTrue(any("evaluation_episode_sha256" in item for item in errors), errors)

    def test_advance_fails_when_full_fusion_does_not_beat_strongest_constituent(self) -> None:
        report = build_report(request_advance=True)
        bva = _row(report, "BVA")
        bva["metrics"]["log_loss"] = 0.66
        report["advancement"]["evidence"] = {
            "strongest_comparator_id": "VA",
            "delta_log_loss": 0.02,
            "uncertainty_supports_improvement": True,
        }
        errors = validate_report(report)
        self.assertTrue(any("does not beat strongest constituent" in item for item in errors), errors)

    def test_advance_requires_supported_group_aware_uncertainty(self) -> None:
        report = build_report(request_advance=True)
        report["uncertainty"] = {
            "supported": False,
            "reason": "too few independent synthetic groups",
        }
        errors = validate_report(report)
        self.assertTrue(any("supported group-aware uncertainty is required" in item for item in errors), errors)

    def test_supported_uncertainty_rejects_clip_or_episode_resampling(self) -> None:
        report = build_report(request_advance=False)
        report["uncertainty"]["resampling_unit"] = "episode"
        errors = validate_report(report)
        self.assertTrue(any("allowed group-aware" in item for item in errors), errors)

    def test_material_ece_degradation_requires_disclosure_for_advancement(self) -> None:
        report = build_report(request_advance=True)
        _row(report, "BVA")["metrics"]["ece"] = 0.09
        errors = validate_report(report)
        self.assertTrue(any("ECE degradation" in item for item in errors), errors)

    def test_stress_rows_must_use_full_fusion_cohort(self) -> None:
        report = build_report(request_advance=False)
        stress = _row(report, "BVA-V")
        stress["evaluation_episode_ids"] = stress["evaluation_episode_ids"][:-1]
        from fusion.m1_result_guard import _episode_digest
        stress["evaluation_episode_sha256"] = _episode_digest(stress["evaluation_episode_ids"])
        errors = validate_report(report)
        self.assertIn("BVA-V: dropout stress must use the BVA evaluation cohort", errors)


if __name__ == "__main__":
    unittest.main()
