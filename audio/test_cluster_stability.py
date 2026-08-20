from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from audio.cluster_stability import analyse


class ClusterStabilityTests(unittest.TestCase):
    def test_reports_stable_structure_without_semantic_selection(self) -> None:
        rows = []
        contexts = ["brushing", "waiting_for_food", "isolation_unfamiliar_environment"]
        for cat_index in range(6):
            for context_index, context in enumerate(contexts):
                for replicate in range(3):
                    rows.append({
                        "path": f"cat{cat_index}/{context_index}-{replicate}.wav",
                        "filename": f"x-{cat_index}-{context_index}-{replicate}.wav",
                        "context": context,
                        "cat_id": f"cat{cat_index}",
                        "owner_id": f"owner{cat_index // 2}",
                        "breed": "EU" if cat_index < 3 else "MC",
                        "sex": "female" if cat_index % 2 == 0 else "male",
                        "sequence_group": f"cat{cat_index}:{replicate}",
                        "duration_s": str(0.5 + 0.6 * context_index + 0.01 * cat_index),
                        "f0_median_hz": str(250 + 240 * context_index + 2 * cat_index),
                        "f0_range_hz": str(20 + 10 * context_index),
                        "voiced_fraction": str(0.7 + 0.05 * context_index),
                        "spectral_centroid_hz_mean": str(700 + 600 * context_index + cat_index),
                        "mfcc_01_mean": str(-30 + 30 * context_index + cat_index * 0.1),
                        "mfcc_01_std": str(4 + context_index),
                    })

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "features.csv"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
            report = analyse(path, feature_set="all_acoustic", k_min=2, k_max=4, repeats=5, seed=7)

        self.assertEqual(report["k_range"], [2, 4])
        self.assertEqual(set(report["by_k"]), {"2", "3", "4"})
        self.assertGreater(report["by_k"]["3"]["subsample_stability_mean_pairwise_ari"], 0.5)
        self.assertGreater(report["by_k"]["3"]["metadata_adjusted_mutual_information"]["context"], 0.5)
        self.assertIn("not semantic intents", report["interpretation_rule"])


if __name__ == "__main__":
    unittest.main()
