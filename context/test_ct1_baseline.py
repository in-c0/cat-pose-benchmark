from __future__ import annotations

import unittest

from context.ct1_baseline import evaluate_single_household_chronological
from context.ct1_features import extract_ct1_rows
from context.fixtures.ct1_synthetic_events import build_events


class CT1BaselineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        events = build_events()
        cls.rows = extract_ct1_rows(events)

    def test_chronological_split_is_contiguous(self) -> None:
        report = evaluate_single_household_chronological(self.rows, train_fraction=0.67)
        self.assertLess(report["train_end"], report["test_start"])
        self.assertEqual(18, report["n_rows"])
        self.assertGreaterEqual(report["n_train"], 2)
        self.assertGreaterEqual(report["n_test"], 2)

    def test_context_signal_beats_prevalence_on_synthetic_fixture(self) -> None:
        report = evaluate_single_household_chronological(self.rows, train_fraction=0.67)
        prevalence = report["models"]["prevalence"]["metrics"]
        context = report["models"]["object_location"]["metrics"]
        self.assertEqual("ok", report["models"]["object_location"]["status"])
        self.assertLess(context["log_loss"], prevalence["log_loss"])
        self.assertGreater(context["balanced_accuracy"], prevalence["balanced_accuracy"])

    def test_all_non_prevalence_models_use_same_test_rows(self) -> None:
        report = evaluate_single_household_chronological(self.rows, train_fraction=0.67)
        for name in ("routine_history", "object_location", "context_routine"):
            self.assertIn(report["models"][name]["status"], {"ok", "unsupported"})


if __name__ == "__main__":
    unittest.main()
