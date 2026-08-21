from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from identity.remind_adapter import ID1ValidationError, build_result_packet, load_spec


class RemindAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.spec = load_spec()

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _write_manifest(self, **overrides):
        manifest = {
            "run_id": "id1-fixture-run",
            "system_id": "remind_unmodified",
            "upstream_commit": self.spec["upstream"]["commit"],
            "sequence_id": "fixture-sequence",
            "sequence_sha256": "a" * 64,
            "ground_truth_sha256": "b" * 64,
            "subject_ids": ["cat-001", "cat-002"],
            "stress_strata": ["long_gap_reentry", "lookalike_multicat"],
            "quantitative": True,
            "persistent_subject_ground_truth": True,
        }
        manifest.update(overrides)
        path = self.root / "manifest.json"
        path.write_text(json.dumps(manifest), encoding="utf-8")
        return path

    def _write_summary(self, *, omit=()):
        values = {
            "idf1": "0.81",
            "idsw": "2",
            "frag": "3",
            "tracking_recall": "0.79",
            "reopen_rate_existing": "0.08",
            "objects_recovered_reference": "4",
            "coverage_firm": "0.76",
            "firm_accuracy": "0.91",
            "uncertain_rate": "0.24",
            "total_runtime_seconds": "12.5",
            "avg_loop_ms": "34.2",
        }
        for key in omit:
            values.pop(key, None)
        path = self.root / "summary_global.csv"
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(values))
            writer.writeheader()
            writer.writerow(values)
        return path

    def test_valid_quantitative_packet_is_identity_only(self):
        packet = build_result_packet(
            summary_global=self._write_summary(),
            manifest_path=self._write_manifest(),
        )
        self.assertEqual(packet["spec_version"], "ID1.0")
        self.assertEqual(packet["metrics"]["idf1"], 0.81)
        self.assertEqual(packet["metrics"]["idsw"], 2)
        self.assertTrue(packet["claims"]["identity_evaluation_performed"])
        self.assertFalse(packet["claims"]["intent_inference_performed"])
        self.assertFalse(packet["claims"]["translation_claim_performed"])

    def test_wrong_upstream_commit_fails_closed(self):
        with self.assertRaisesRegex(ID1ValidationError, "upstream commit mismatch"):
            build_result_packet(
                summary_global=self._write_summary(),
                manifest_path=self._write_manifest(upstream_commit="0" * 40),
            )

    def test_quantitative_run_requires_persistent_identity_ground_truth(self):
        with self.assertRaisesRegex(ID1ValidationError, "persistent subject ground truth"):
            build_result_packet(
                summary_global=self._write_summary(),
                manifest_path=self._write_manifest(persistent_subject_ground_truth=False),
            )

    def test_quantitative_run_requires_all_primary_metrics(self):
        with self.assertRaisesRegex(ID1ValidationError, "missing primary REMIND metrics"):
            build_result_packet(
                summary_global=self._write_summary(omit=("idf1",)),
                manifest_path=self._write_manifest(),
            )

    def test_unknown_stress_stratum_fails_closed(self):
        with self.assertRaisesRegex(ID1ValidationError, "unknown stress strata"):
            build_result_packet(
                summary_global=self._write_summary(),
                manifest_path=self._write_manifest(stress_strata=["cat_is_cute"]),
            )

    def test_software_only_packet_may_leave_metrics_empty(self):
        summary = self.root / "summary_global.csv"
        summary.write_text("note\nsoftware-only\n", encoding="utf-8")
        packet = build_result_packet(
            summary_global=summary,
            manifest_path=self._write_manifest(
                quantitative=False,
                persistent_subject_ground_truth=False,
            ),
        )
        self.assertFalse(packet["claims"]["identity_evaluation_performed"])
        self.assertIsNone(packet["metrics"]["idf1"])


if __name__ == "__main__":
    unittest.main()
