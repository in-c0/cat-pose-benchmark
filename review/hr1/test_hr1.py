from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from review.hr1.agreement import cohen_kappa, krippendorff_alpha_nominal, pairwise
import hashlib

from review.hr1.score import check_locks, load_stage_a, load_stage_b, score, unanimous


def _two_raters(yy: int, yn: int, ny: int, nn: int) -> tuple[dict, dict]:
    a, b, i = {}, {}, 0
    for la, lb, n in (("y", "y", yy), ("y", "n", yn), ("n", "y", ny), ("n", "n", nn)):
        for _ in range(n):
            a[i], b[i] = la, lb
            i += 1
    return a, b


class AgreementTests(unittest.TestCase):
    def test_textbook_kappa_and_alpha(self):
        # po = 0.70; Cohen pe = 0.25*... = 0.50 -> kappa 0.40.
        # Krippendorff: n = 100 pairable values, Do = 30, De = 2*55*45/99 = 50 -> alpha 0.40.
        a, b = _two_raters(20, 5, 10, 15)
        self.assertAlmostEqual(cohen_kappa(a, b), 0.40, places=6)
        self.assertAlmostEqual(krippendorff_alpha_nominal({"a": a, "b": b}), 0.40, places=6)

    def test_perfect_agreement(self):
        a = {1: "x", 2: "y", 3: "x"}
        self.assertEqual(cohen_kappa(a, dict(a)), 1.0)
        self.assertEqual(krippendorff_alpha_nominal({"a": a, "b": dict(a), "c": dict(a)}), 1.0)

    def test_missing_items_are_dropped(self):
        a = {1: "x", 2: "y", 3: "x"}
        b = {1: "x", 2: "y"}
        self.assertEqual(krippendorff_alpha_nominal({"a": a, "b": b}), 1.0)
        self.assertEqual(pairwise({"a": a, "b": b})[0]["n_shared"], 2)

    def test_single_category_is_undefined(self):
        a = {1: "x", 2: "x"}
        self.assertIsNone(cohen_kappa(a, dict(a)))


class ConsensusTests(unittest.TestCase):
    def test_unanimous_or_uncertain(self):
        self.assertEqual(unanimous(["positive", "positive"]), "positive")
        self.assertEqual(unanimous(["positive", "negative"]), "uncertain")


def _write(path: Path, cols: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as h:
        w = csv.DictWriter(h, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)


class ScoreTests(unittest.TestCase):
    """A four-frame synthetic key on a real holdout clip id; labels are test fixtures."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        clip = "holdout-larry-nails"
        self.key = {
            "methods": ["tail_grounded_v1", "tail_grounded_v3"],
            "items": {"B001": {"clip_id": clip, "frame_index": 0}, "B002": {"clip_id": clip, "frame_index": 1}, "B003": {"clip_id": clip, "frame_index": 2}},
            "repeat_of": {"B004": "B001"},
            "frames": [
                {"set": "holdout1", "clip_id": clip, "frame_index": 0, "methods": {m: {"asserted": True, "item_id": "B001"} for m in ("tail_grounded_v1", "tail_grounded_v3")}},
                {"set": "holdout1", "clip_id": clip, "frame_index": 1, "methods": {m: {"asserted": True, "item_id": "B002"} for m in ("tail_grounded_v1", "tail_grounded_v3")}},
                {"set": "holdout1", "clip_id": clip, "frame_index": 2, "methods": {"tail_grounded_v1": {"asserted": False, "item_id": None}, "tail_grounded_v3": {"asserted": True, "item_id": "B003"}}},
                {"set": "holdout1", "clip_id": clip, "frame_index": 3, "methods": {m: {"asserted": False, "item_id": None} for m in ("tail_grounded_v1", "tail_grounded_v3")}},
            ],
        }
        (self.tmp / "key.json").write_text(json.dumps(self.key), encoding="utf-8")
        a_cols = ["clip_id", "frame_index", "timestamp_s", "sheet", "tail", "note"]
        a1 = ["visible", "visible", "partial", "not_visible"]
        a2 = ["visible", "visible", "visible", "cannot_tell"]
        for name, labels in (("r1", a1), ("r2", a2)):
            _write(self.tmp / "stage_a" / f"{name}.csv", a_cols, [{"clip_id": clip, "frame_index": i, "timestamp_s": "0", "sheet": "s", "tail": v, "note": ""} for i, v in enumerate(labels)])
        b1 = {"B001": "on_tail", "B002": "not_on_tail", "B003": "on_tail", "B004": "on_tail"}
        b2 = {"B001": "on_tail", "B002": "not_on_tail", "B003": "cannot_tell", "B004": "not_on_tail"}
        for name, labels in (("r1", b1), ("r2", b2)):
            _write(self.tmp / "stage_b" / f"{name}.csv", ["item_id", "on_tail", "note"], [{"item_id": k, "on_tail": v, "note": ""} for k, v in labels.items()])

    def test_end_to_end(self):
        r = score(sorted((self.tmp / "stage_a").glob("*.csv")), sorted((self.tmp / "stage_b").glob("*.csv")), self.tmp / "key.json")
        # frames 0-2 positive by both (partial and visible collapse), frame 3 disagrees -> uncertain
        self.assertEqual(r["stage_a"]["consensus_counts"], {"positive": 3, "uncertain": 1})
        v1 = r["methods"]["tail_grounded_v1"]["holdout1"]
        self.assertEqual((v1["TP"], v1["FPv"], v1["FN"], v1["FPn"], v1["excluded_frame"]), (1, 1, 1, 0, 1))
        v3 = r["methods"]["tail_grounded_v3"]["holdout1"]
        # frame 2's curve is disputed in Stage B -> excluded, not counted either way
        self.assertEqual((v3["TP"], v3["FPv"], v3["FN"], v3["excluded_assertion"]), (1, 1, 0, 1))
        self.assertEqual(r["stage_b"]["self_consistency"]["r1"], {"n": 1, "same": 1})
        self.assertEqual(r["stage_b"]["self_consistency"]["r2"], {"n": 1, "same": 0})

    def test_lock_check(self):
        p = self.tmp / "stage_a" / "r1.csv"
        good = hashlib.sha256(p.read_bytes()).hexdigest()
        check_locks([p], {"stage_a/r1.csv": good})
        with self.assertRaises(SystemExit):
            check_locks([p], {"stage_a/r1.csv": "0" * 64})
        with self.assertRaises(SystemExit):
            check_locks([p], {})

    def test_blank_label_is_an_error(self):
        p = self.tmp / "bad.csv"
        _write(p, ["clip_id", "frame_index", "tail"], [{"clip_id": "c", "frame_index": 0, "tail": ""}])
        with self.assertRaises(ValueError):
            load_stage_a(p)

    def test_unknown_label_is_an_error(self):
        p = self.tmp / "bad_b.csv"
        _write(p, ["item_id", "on_tail"], [{"item_id": "B001", "on_tail": "maybe"}])
        with self.assertRaises(ValueError):
            load_stage_b(p)


if __name__ == "__main__":
    unittest.main()
