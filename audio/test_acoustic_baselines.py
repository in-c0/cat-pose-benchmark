from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from audio.acoustic_baselines import evaluate


class AcousticBaselineTests(unittest.TestCase):
    def test_leave_one_cat_out_evaluation_covers_all_rows(self) -> None:
        rows = []
        contexts = ["brushing", "waiting_for_food", "isolation_unfamiliar_environment"]
        for cat_index in range(6):
            for context_index, context in enumerate(contexts):
                for replicate in range(2):
                    rows.append({
                        "path": f"cat{cat_index}/{context_index}-{replicate}.wav",
                        "filename": f"x{cat_index}_{context_index}_{replicate}.wav",
                        "context": context,
                        "cat_id": f"cat{cat_index}",
                        "owner_id": f"owner{cat_index // 2}",
                        "sequence_group": f"cat{cat_index}:{replicate + 1}",
                        "duration_s": str(0.5 + context_index * 0.4 + cat_index * 0.01),
                        "f0_median_hz": str(250 + context_index * 220 + cat_index),
                        "f0_range_hz": str(20 + context_index * 15),
                        "voiced_fraction": str(0.7 + context_index * 0.05),
                        "spectral_centroid_hz_mean": str(600 + context_index * 500 + cat_index),
                        "mfcc_01_mean": str(-30 + context_index * 25 + cat_index * 0.1),
                        "mfcc_01_std": str(4 + context_index),
                    })

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "features.csv"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
            report = evaluate(path, "cat_id")

        self.assertEqual(report["n_groups"], 6)
        self.assertIn("majority", report["models"])
        self.assertIn("prevalence_prior", report["models"])
        self.assertIn("logistic_duration_f0", report["models"])
        self.assertIn("logistic_mfcc", report["models"])
        for model in report["models"].values():
            self.assertIn("balanced_accuracy", model["overall"])
            self.assertIn("log_loss", model["overall"])
            self.assertIn("multiclass_brier", model["overall"])
            self.assertIn("top_label_ece", model["overall"])


if __name__ == "__main__":
    unittest.main()
