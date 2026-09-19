from __future__ import annotations

import unittest

from detail.tail_audit import anchors
from detail.tail_track import runs


def _statuses(s: str) -> list[str]:
    m = {"C": "no_cat", "N": "temporal_none", "B": "no_tail_box", "O": "ok", "P": "all_look_like_paw"}
    return [m[c] for c in s]


class RunAndAnchorTests(unittest.TestCase):
    def test_runs_classify_by_bounding_seeds(self) -> None:
        got = [(g["first"], g["last"], g["kind"]) for g in runs(_statuses("CCNNBNNOOOOOOBNBOOBBOOOO"))]
        self.assertEqual(got, [(0, 6, "one_sided"), (13, 15, "two_sided"), (18, 19, "two_sided")])

    def test_runs_paw_bounded_is_unseeded_or_one_sided(self) -> None:
        got = [(g["first"], g["last"], g["kind"]) for g in runs(_statuses("NNNNNOOOOPNPPNPNNNNOOPPP"))]
        self.assertEqual(got, [(0, 4, "one_sided"), (10, 10, "unseeded"), (13, 13, "unseeded"), (15, 18, "one_sided")])

    def test_anchors_within_horizon(self) -> None:
        ok = [1, 2, 5, 9, 10]
        self.assertEqual(anchors(ok, 5, 3), (2, None))
        self.assertEqual(anchors(ok, 2, 3), (1, 5))
        self.assertEqual(anchors(ok, 9, 3), (None, 10))
        self.assertEqual(anchors(ok, 1, 3), (None, 2))


if __name__ == "__main__":
    unittest.main()
