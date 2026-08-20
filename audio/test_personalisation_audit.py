from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from audio.personalisation_audit import audit


FIELDS = ["path", "cat_id", "session", "context"]


class PersonalisationAuditTests(unittest.TestCase):
    def _write_manifest(self, rows: list[dict[str, object]]) -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "manifest.csv"
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(rows)
        return path

    def test_primary_fold_requires_two_test_contexts_and_adaptation_support(self) -> None:
        path = self._write_manifest([
            {"path": "a.wav", "cat_id": "CAT1", "session": 1, "context": "brushing"},
            {"path": "b.wav", "cat_id": "CAT1", "session": 1, "context": "waiting_for_food"},
            {"path": "c.wav", "cat_id": "CAT1", "session": 2, "context": "brushing"},
            {"path": "d.wav", "cat_id": "CAT1", "session": 2, "context": "waiting_for_food"},
            {"path": "e.wav", "cat_id": "CAT1", "session": 2, "context": "waiting_for_food"},
        ])
        report = audit(path, unlabelled_budgets=[1, 4], labelled_budgets=[1, 2])
        self.assertEqual(2, report["summary"]["n_session_disjoint_folds"])
        self.assertEqual(2, report["summary"]["n_primary_feasible_folds"])
        folds = report["cats"]["CAT1"]["folds"]
        by_test = {fold["test_session"]: fold for fold in folds}
        self.assertTrue(by_test[1]["primary_feasible"])
        self.assertEqual(1, by_test[1]["max_labelled_budget_per_test_context"])
        self.assertFalse(by_test[1]["labelled_budget_support"]["2"])
        self.assertTrue(by_test[1]["unlabelled_budget_support"]["1"])

    def test_single_context_test_session_is_not_primary_feasible(self) -> None:
        path = self._write_manifest([
            {"path": "a.wav", "cat_id": "CAT1", "session": 1, "context": "brushing"},
            {"path": "b.wav", "cat_id": "CAT1", "session": 2, "context": "brushing"},
            {"path": "c.wav", "cat_id": "CAT1", "session": 2, "context": "waiting_for_food"},
        ])
        report = audit(path)
        folds = report["cats"]["CAT1"]["folds"]
        session1 = next(fold for fold in folds if fold["test_session"] == 1)
        self.assertFalse(session1["test_has_at_least_two_contexts"])
        self.assertFalse(session1["primary_feasible"])

    def test_missing_test_context_in_adaptation_is_rejected(self) -> None:
        path = self._write_manifest([
            {"path": "a.wav", "cat_id": "CAT1", "session": 1, "context": "brushing"},
            {"path": "b.wav", "cat_id": "CAT1", "session": 1, "context": "waiting_for_food"},
            {"path": "c.wav", "cat_id": "CAT1", "session": 2, "context": "brushing"},
            {"path": "d.wav", "cat_id": "CAT1", "session": 2, "context": "isolation_unfamiliar_environment"},
        ])
        report = audit(path)
        self.assertEqual(0, report["summary"]["n_primary_feasible_folds"])
        for fold in report["cats"]["CAT1"]["folds"]:
            self.assertFalse(fold["all_test_contexts_supported"])

    def test_single_session_cat_is_reported_not_silently_dropped(self) -> None:
        path = self._write_manifest([
            {"path": "a.wav", "cat_id": "CAT1", "session": 1, "context": "brushing"},
            {"path": "b.wav", "cat_id": "CAT2", "session": 1, "context": "waiting_for_food"},
            {"path": "c.wav", "cat_id": "CAT2", "session": 2, "context": "waiting_for_food"},
        ])
        report = audit(path)
        self.assertIn("CAT1", report["cats"])
        self.assertEqual("fewer_than_two_recording_sessions", report["cats"]["CAT1"]["infeasible_reason"])
        self.assertEqual(1, report["summary"]["n_cats_with_at_least_two_sessions"])


if __name__ == "__main__":
    unittest.main()
