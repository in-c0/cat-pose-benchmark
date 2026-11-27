from __future__ import annotations

import copy
import json
import math
import tempfile
import unittest
from pathlib import Path

from synthetic.unity_roundtrip import (
    PINNED_UNITY_EDITOR_VERSION,
    UNITY_EXPORT_VERSION,
    build_mock_unity_export,
    build_report,
    compare_unity_export,
    write_mock_export,
)

UNITY_PROJECT = Path(__file__).resolve().parent / "unity" / "S0AProxy"


class S0BUnityRoundTripTests(unittest.TestCase):
    def setUp(self) -> None:
        self.payload = build_mock_unity_export()

    def test_mock_contract_passes_when_mock_is_explicitly_allowed(self) -> None:
        self.assertEqual(
            [],
            compare_unity_export(
                self.payload,
                require_unity_runtime=False,
            ),
        )
        report = build_report(self.payload, require_unity_runtime=False)
        self.assertTrue(report["contract_valid"])
        self.assertFalse(report["unity_runtime_verified"])
        self.assertFalse(report["performance_analysis_performed"])

    def test_mock_contract_cannot_satisfy_actual_unity_runtime_gate(self) -> None:
        errors = compare_unity_export(self.payload, require_unity_runtime=True)
        self.assertTrue(any("actual gate requires" in item for item in errors), errors)

    def test_wrong_editor_version_is_rejected(self) -> None:
        payload = copy.deepcopy(self.payload)
        payload["unity_editor_version"] = "6000.5.0f1"
        errors = compare_unity_export(payload, require_unity_runtime=False)
        self.assertTrue(any("unity_editor_version" in item for item in errors), errors)
        self.assertNotEqual(PINNED_UNITY_EDITOR_VERSION, payload["unity_editor_version"])

    def test_world_and_projection_mutations_are_rejected(self) -> None:
        payload = copy.deepcopy(self.payload)
        payload["frames"][1]["landmarks"][0]["world_m"]["x"] += 0.02
        payload["frames"][2]["landmarks"][1]["image_px"]["y"] += 5.0
        errors = compare_unity_export(payload, require_unity_runtime=False)
        self.assertTrue(any("world_m.x" in item for item in errors), errors)
        self.assertTrue(any("image_px.y" in item for item in errors), errors)

    def test_contact_and_visibility_mutations_are_rejected(self) -> None:
        payload = copy.deepcopy(self.payload)
        payload["frames"][2]["contacts"][2]["floor_contact"] = True
        left_ear = next(
            item
            for item in payload["frames"][2]["landmarks"]
            if item["name"] == "left_ear_tip"
        )
        left_ear["visibility"] = "visible"
        errors = compare_unity_export(payload, require_unity_runtime=False)
        self.assertTrue(any("floor_contact" in item for item in errors), errors)
        self.assertTrue(any("visibility" in item for item in errors), errors)

    def test_time_and_occluder_mutations_are_rejected(self) -> None:
        payload = copy.deepcopy(self.payload)
        payload["dt_seconds"] = 0.2
        payload["frames"][3]["timestamp_ns"] += 1
        payload["frames"][3]["occluder_world_m"]["z"] += 0.1
        errors = compare_unity_export(payload, require_unity_runtime=False)
        self.assertTrue(any("dt_seconds" in item for item in errors), errors)
        self.assertTrue(any("timestamp_ns" in item for item in errors), errors)
        self.assertTrue(any("occluder_world_m.z" in item for item in errors), errors)

    def test_duplicate_and_missing_landmark_and_contact_names_are_rejected(self) -> None:
        payload = copy.deepcopy(self.payload)
        payload["frames"][0]["landmarks"][1]["name"] = payload["frames"][0]["landmarks"][0]["name"]
        payload["frames"][0]["contacts"].pop()
        errors = compare_unity_export(payload, require_unity_runtime=False)
        self.assertTrue(any("duplicate landmark name" in item for item in errors), errors)
        self.assertTrue(any("missing names" in item for item in errors), errors)
        self.assertTrue(any("missing paw names" in item for item in errors), errors)

    def test_non_finite_numeric_values_are_rejected(self) -> None:
        payload = copy.deepcopy(self.payload)
        payload["frames"][0]["root_world_m"]["x"] = math.nan
        errors = compare_unity_export(payload, require_unity_runtime=False)
        self.assertTrue(any("finite number" in item for item in errors), errors)

    def test_report_stays_performance_blind_on_failure(self) -> None:
        payload = copy.deepcopy(self.payload)
        payload["frame_count"] = 99
        report = build_report(payload, require_unity_runtime=False)
        self.assertFalse(report["contract_valid"])
        self.assertFalse(report["unity_runtime_verified"])
        rendered = json.dumps(report).lower()
        for forbidden in (
            "balanced_accuracy",
            "log_loss",
            "macro_f1",
            "coefficient",
            "feature_importance",
        ):
            self.assertNotIn(forbidden, rendered)

    def test_json_file_round_trip_preserves_mock_contract(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "mock-unity-export.json"
            write_mock_export(path)
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(
                [],
                compare_unity_export(payload, require_unity_runtime=False),
            )

    def test_unity_project_is_pinned_to_exact_lts_patch(self) -> None:
        version_file = UNITY_PROJECT / "ProjectSettings" / "ProjectVersion.txt"
        self.assertEqual(
            f"m_EditorVersion: {PINNED_UNITY_EDITOR_VERSION}\n",
            version_file.read_text(encoding="utf-8"),
        )
        manifest = json.loads(
            (UNITY_PROJECT / "Packages" / "manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual({}, manifest["dependencies"])

    def test_exporter_static_contract_matches_python_gate(self) -> None:
        source = (
            UNITY_PROJECT
            / "Assets"
            / "Editor"
            / "S0BProxyExportCommand.cs"
        ).read_text(encoding="utf-8")
        for required in (
            f'ExportVersion = "{UNITY_EXPORT_VERSION}"',
            'runtime_source = "unity_editor"',
            'ReferenceBundleVersion = "S0A-proxy-handshake-v0"',
            'SequenceId = "s0a-proxy-sequence-0001"',
            'SubjectId = "synthetic-cat-proxy-0001"',
            "Application.unityVersion",
            "InverseTransformPoint",
            "occluderCollider.bounds.IntersectRay",
            "Physics.SyncTransforms",
        ):
            self.assertIn(required, source)


if __name__ == "__main__":
    unittest.main()
