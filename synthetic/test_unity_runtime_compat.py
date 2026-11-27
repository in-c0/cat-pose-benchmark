from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from synthetic.unity_roundtrip import (
    PINNED_UNITY_EDITOR_VERSION,
    RUNTIME_SOURCE_MOCK,
    RUNTIME_SOURCE_UNITY,
    build_mock_unity_export,
)
from synthetic.unity_runtime_compat import (
    build_compatibility_report,
    is_compatible_unity_6_3_lts,
)

RUNNER = Path(__file__).resolve().parent / "unity" / "run_s0b_windows.ps1"


class S0BUnityRuntimeCompatibilityTests(unittest.TestCase):
    def _real_runtime_fixture(self, version: str) -> dict:
        payload = build_mock_unity_export()
        # Software-only policy fixture. This does not claim Unity executed in CI.
        payload["runtime_source"] = RUNTIME_SOURCE_UNITY
        payload["unity_editor_version"] = version
        return payload

    def test_canonical_pin_sets_both_runtime_flags(self) -> None:
        report = build_compatibility_report(
            self._real_runtime_fixture(PINNED_UNITY_EDITOR_VERSION)
        )
        self.assertTrue(report["canonical_pin_verified"])
        self.assertTrue(report["compatible_runtime_verified"])
        self.assertTrue(report["unity_runtime_verified"])
        self.assertEqual("canonical_pin", report["editor_status"])
        self.assertEqual([], report["canonical_mismatches"])
        self.assertEqual([], report["compatibility_mismatches"])

    def test_6000_3_0f1_is_compatible_but_not_canonical(self) -> None:
        report = build_compatibility_report(
            self._real_runtime_fixture("6000.3.0f1")
        )
        self.assertFalse(report["canonical_pin_verified"])
        self.assertTrue(report["compatible_runtime_verified"])
        self.assertTrue(report["unity_runtime_verified"])
        self.assertFalse(report["canonical_contract_valid"])
        self.assertTrue(report["compatibility_contract_valid"])
        self.assertEqual("compatible_6000.3_lts_patch", report["editor_status"])
        self.assertEqual(
            [
                "unity_editor_version: expected '6000.3.18f1', got '6000.3.0f1'"
            ],
            report["canonical_mismatches"],
        )
        self.assertEqual([], report["compatibility_mismatches"])

    def test_other_unity_line_does_not_pass_compatibility(self) -> None:
        report = build_compatibility_report(
            self._real_runtime_fixture("6000.5.0f1")
        )
        self.assertFalse(report["canonical_pin_verified"])
        self.assertFalse(report["compatible_runtime_verified"])
        self.assertFalse(report["unity_runtime_verified"])
        self.assertTrue(report["compatibility_mismatches"])

    def test_mock_runtime_never_satisfies_compatibility_gate(self) -> None:
        payload = build_mock_unity_export()
        payload["unity_editor_version"] = "6000.3.0f1"
        payload["runtime_source"] = RUNTIME_SOURCE_MOCK
        report = build_compatibility_report(payload)
        self.assertFalse(report["compatible_runtime_verified"])
        self.assertFalse(report["unity_runtime_verified"])

    def test_geometry_mismatch_still_fails_on_compatible_patch(self) -> None:
        payload = self._real_runtime_fixture("6000.3.0f1")
        payload["frames"][0]["root_world_m"]["x"] += 0.01
        report = build_compatibility_report(payload)
        self.assertFalse(report["compatible_runtime_verified"])
        self.assertTrue(
            any("root_world_m.x" in item for item in report["compatibility_mismatches"]),
            report,
        )

    def test_version_parser_is_narrow_to_final_6000_3_releases(self) -> None:
        self.assertTrue(is_compatible_unity_6_3_lts("6000.3.0f1"))
        self.assertTrue(is_compatible_unity_6_3_lts("6000.3.18f1"))
        for rejected in (
            "6000.2.18f1",
            "6000.5.0f1",
            "6000.3.0b1",
            "2022.3.49f1",
            "6000.3",
            None,
        ):
            self.assertFalse(is_compatible_unity_6_3_lts(rejected), rejected)

    def test_report_remains_performance_blind(self) -> None:
        report = build_compatibility_report(
            self._real_runtime_fixture("6000.3.0f1")
        )
        self.assertFalse(report["performance_analysis_performed"])
        rendered = json.dumps(report).lower()
        for forbidden in (
            "balanced_accuracy",
            "log_loss",
            "macro_f1",
            "feature_importance",
            "coefficient",
        ):
            self.assertNotIn(forbidden, rendered)

    def test_windows_runner_uses_process_exit_code_not_lastexitcode_for_unity(self) -> None:
        source = RUNNER.read_text(encoding="utf-8")
        self.assertIn("Start-Process", source)
        self.assertIn("$unityProcess.ExitCode", source)
        self.assertIn("synthetic.unity_runtime_compat", source)
        self.assertIn("--require-canonical-pin", source)


if __name__ == "__main__":
    unittest.main()
