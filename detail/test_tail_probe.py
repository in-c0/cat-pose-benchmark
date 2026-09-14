from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from detail.tail_probe import harvest, probability, train


class ProbeTests(unittest.TestCase):
    def test_harvest_labels_accepted_box_positive_and_rest_negative(self) -> None:
        result = {
            "frames": [
                {"file": "a.jpg", "status": "ok", "tail": {"box": [1, 1, 2, 2]}, "candidates": [{"box": [1, 1, 2, 2]}, {"box": [5, 5, 6, 6]}]},
                {"file": "b.jpg", "status": "all_look_like_paw", "candidates": [{"box": [7, 7, 8, 8]}]},
                {"file": "c.jpg", "status": "no_cat", "candidates": []},
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "result.json"
            path.write_text(json.dumps(result), encoding="utf-8")
            pos, neg = harvest(path, Path(tmp))
        self.assertEqual(pos, [("a.jpg", [1, 1, 2, 2])])
        self.assertEqual(neg, [("a.jpg", [5, 5, 6, 6]), ("b.jpg", [7, 7, 8, 8])])

    def test_train_and_probability_round_trip(self) -> None:
        rng = np.random.default_rng(0)
        pos = rng.normal(loc=1.0, size=(40, 8)).astype(np.float32)
        neg = rng.normal(loc=-1.0, size=(40, 8)).astype(np.float32)
        probe = train(np.vstack([pos, neg]), np.array([1] * 40 + [0] * 40))
        self.assertGreater(probability(probe, np.full(8, 1.0, dtype=np.float32)), 0.9)
        self.assertLess(probability(probe, np.full(8, -1.0, dtype=np.float32)), 0.1)
        self.assertEqual(len(probe["weights"]), 8)


if __name__ == "__main__":
    unittest.main()
