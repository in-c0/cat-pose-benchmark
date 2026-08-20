from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from audio.personalisation_audit import audit
from audio.unlabelled_personalisation import _stable_order, evaluate


class UnlabelledPersonalisationTests(unittest.TestCase):
    def _synthetic_tables(self) -> tuple[Path, Path]:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        features = root / "features.csv"
        audit_path = root / "audit.json"

        fieldnames = [
            "path", "filename", "context", "cat_id", "owner_id", "session", "sequence_group",
            "duration_s",
        ]
        rows = []
        for cat_index, cat_id in enumerate(["CAT1", "CAT2", "CAT3", "CAT4"]):
            offset = float(cat_index * 100)
            for session in [1, 2]:
                for repeat in [1, 2]:
                    for context, delta in [("context_a", -1.0), ("context_b", 1.0)]:
                        name = f"{cat_id}-{session}-{repeat}-{context}.wav"
                        rows.append({
                            "path": name,
                            "filename": name,
                            "context": context,
                            "cat_id": cat_id,
                            "owner_id": f"OWNER{cat_index}",
                            "session": str(session),
                            "sequence_group": f"{cat_id}:{session}",
                            "duration_s": str(offset + delta),
                        })

        with features.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        audit_report = audit(features, unlabelled_budgets=[4], labelled_budgets=[1])
        audit_path.write_text(json.dumps(audit_report), encoding="utf-8")
        return features, audit_path

    def test_stable_order_is_deterministic_and_label_blind(self) -> None:
        rows = [
            {"path": "b.wav", "context": "x"},
            {"path": "a.wav", "context": "y"},
            {"path": "c.wav", "context": "z"},
        ]
        first = _stable_order(rows, seed=7, repeat=2, cat_id="CAT", test_session=1)
        relabelled = [{**row, "context": "changed"} for row in rows]
        second = _stable_order(relabelled, seed=7, repeat=2, cat_id="CAT", test_session=1)
        self.assertEqual([row["path"] for row in first], [row["path"] for row in second])

    def test_target_adaptation_beats_zero_shot_when_identity_offset_is_large(self) -> None:
        features, audit_path = self._synthetic_tables()
        report = evaluate(
            features,
            audit_path,
            budgets=[4],
            repeats=1,
            seed=123,
            shrinkage_tau=4.0,
            bootstrap_reps=100,
            bootstrap_seed=456,
        )
        result = report["by_budget"]["4"]
        self.assertEqual(8, result["supported_folds"])
        zero_shot = result["models"]["centered_zero_shot"]["balanced_accuracy"]
        adapted = result["models"]["centered_unshrunk"]["balanced_accuracy"]
        self.assertGreater(adapted, zero_shot)
        self.assertGreaterEqual(adapted, 0.99)
        self.assertGreater(
            result["target_adaptation_delta_vs_zero_shot"]["centered_unshrunk"]["balanced_accuracy"],
            0.0,
        )

    def test_cat_equal_summary_is_reported_separately_from_clip_pooled_metrics(self) -> None:
        features, audit_path = self._synthetic_tables()
        report = evaluate(
            features,
            audit_path,
            budgets=[4],
            repeats=1,
            bootstrap_reps=50,
            bootstrap_seed=999,
        )
        robustness = report["by_budget"]["4"]["cat_equal_robustness"]
        comparison = robustness["centered_unshrunk_vs_zero_shot"]
        self.assertEqual(4, comparison["n_cats"])
        self.assertEqual(50, comparison["bootstrap_reps"])
        self.assertEqual("cat", comparison["bootstrap_unit"])
        ci = comparison["metrics"]["balanced_accuracy"]["bootstrap_mean_ci95"]
        self.assertEqual(2, len(ci))

    def test_budget_support_uses_only_other_target_cat_sessions(self) -> None:
        features, audit_path = self._synthetic_tables()
        report = evaluate(features, audit_path, budgets=[4], repeats=2, bootstrap_reps=0)
        for fold in report["folds"]:
            self.assertEqual(4, fold["n_test"])
            self.assertEqual(4, fold["n_adaptation_available"])
            self.assertTrue(fold["by_budget"]["4"]["supported"])


if __name__ == "__main__":
    unittest.main()
