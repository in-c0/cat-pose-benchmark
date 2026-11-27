from __future__ import annotations

import unittest

from detail.tail_bridge import FILLABLE, plan_fills


class PlanTests(unittest.TestCase):
    def test_nearest_seed_within_reach(self) -> None:
        statuses = ["ok", "temporal_none", "temporal_none", "ok", "no_cat", "no_cat", "no_cat"]
        self.assertEqual(plan_fills(statuses, max_reach=1), {1: (0, 1), 2: (3, 1), 4: (3, 1)})
        self.assertEqual(plan_fills(statuses, max_reach=2), {1: (0, 1), 2: (3, 1), 4: (3, 1), 5: (3, 2)})

    def test_paw_refusals_are_never_filled(self) -> None:
        statuses = ["ok", "all_look_like_paw", "ok"]
        self.assertEqual(plan_fills(statuses, max_reach=2), {})
        self.assertNotIn("all_look_like_paw", FILLABLE)

    def test_no_seeds_no_plan(self) -> None:
        self.assertEqual(plan_fills(["no_cat", "temporal_none"], max_reach=3), {})


if __name__ == "__main__":
    unittest.main()
