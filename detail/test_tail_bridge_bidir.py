from __future__ import annotations

import unittest

from detail.tail_bridge_bidir import two_sided_gaps


class GapTests(unittest.TestCase):
    def test_two_sided_gaps_respect_length_and_paw_refusals(self) -> None:
        s = ["ok", "temporal_none", "temporal_none", "ok", "no_tail_box", "no_tail_box", "no_tail_box", "ok", "all_look_like_paw", "ok", "temporal_none"]
        self.assertEqual(two_sided_gaps(s, 2), [(0, 1, 2, 3)])
        self.assertEqual(two_sided_gaps(s, 3), [(0, 1, 2, 3), (3, 4, 6, 7)])
        # a paw refusal is not fillable and the trailing gap has no right seed
        self.assertNotIn((7, 8, 8, 9), two_sided_gaps(s, 3))

    def test_gap_at_sequence_edge_is_one_sided(self) -> None:
        self.assertEqual(two_sided_gaps(["temporal_none", "ok", "ok"], 2), [])
        self.assertEqual(two_sided_gaps(["ok", "ok", "temporal_none"], 2), [])


if __name__ == "__main__":
    unittest.main()
