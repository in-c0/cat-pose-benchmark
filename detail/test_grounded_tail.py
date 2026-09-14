from __future__ import annotations

import unittest

import numpy as np

from detail.grounded_tail import (
    MAX_TAIL_TO_CAT_AREA,
    MIN_TAIL_SCORE,
    base_point,
    keypoints_inside,
    pick_cat_box,
    pick_tail_box,
)

CAT = {"label": "cat", "score": 0.8, "box": [100.0, 100.0, 500.0, 400.0]}
OTHER_CAT = {"label": "cat", "score": 0.9, "box": [700.0, 100.0, 900.0, 300.0]}


class CatBoxTests(unittest.TestCase):
    def test_highest_score_without_preference(self) -> None:
        self.assertIs(pick_cat_box([CAT, OTHER_CAT], None), OTHER_CAT)

    def test_preference_picks_the_overlapping_cat(self) -> None:
        self.assertIs(pick_cat_box([CAT, OTHER_CAT], [120.0, 110.0, 480.0, 390.0]), CAT)

    def test_preference_falls_back_when_nothing_overlaps(self) -> None:
        self.assertIs(pick_cat_box([CAT, OTHER_CAT], [0.0, 900.0, 10.0, 950.0]), OTHER_CAT)

    def test_low_score_and_non_cat_labels_ignored(self) -> None:
        weak = {"label": "cat", "score": 0.1, "box": [0.0, 0.0, 10.0, 10.0]}
        tail = {"label": "tail", "score": 0.9, "box": [0.0, 0.0, 10.0, 10.0]}
        self.assertIsNone(pick_cat_box([weak, tail], None))


class TailBoxTests(unittest.TestCase):
    def test_whole_cat_grounded_as_tail_is_rejected(self) -> None:
        whole = {"label": "cat tail", "score": 0.9, "box": [100.0, 100.0, 500.0, 400.0]}
        small = {"label": "tail", "score": 0.4, "box": [420.0, 150.0, 500.0, 200.0]}
        self.assertIs(pick_tail_box([whole, small], CAT), small)

    def test_tail_outside_cat_is_rejected(self) -> None:
        far = {"label": "tail", "score": 0.9, "box": [800.0, 800.0, 850.0, 850.0]}
        self.assertIsNone(pick_tail_box([far], CAT))

    def test_tail_may_poke_just_past_the_cat_box(self) -> None:
        edge = {"label": "tail", "score": 0.5, "box": [480.0, 150.0, 530.0, 200.0]}
        self.assertIs(pick_tail_box([edge], CAT), edge)

    def test_score_threshold_and_area_cap(self) -> None:
        weak = {"label": "tail", "score": MIN_TAIL_SCORE - 0.01, "box": [420.0, 150.0, 500.0, 200.0]}
        self.assertIsNone(pick_tail_box([weak], CAT))
        cat_area = 400.0 * 300.0
        side = (MAX_TAIL_TO_CAT_AREA * cat_area) ** 0.5 + 5
        big = {"label": "tail", "score": 0.9, "box": [150.0, 120.0, 150.0 + side, 120.0 + side]}
        self.assertIsNone(pick_tail_box([big], CAT))

    def test_highest_scoring_valid_tail_wins(self) -> None:
        a = {"label": "tail", "score": 0.4, "box": [420.0, 150.0, 500.0, 200.0]}
        b = {"label": "tail", "score": 0.6, "box": [120.0, 300.0, 200.0, 380.0]}
        self.assertIs(pick_tail_box([a, b], CAT), b)


class MaskHelperTests(unittest.TestCase):
    def test_base_point_prefers_root_keypoint(self) -> None:
        mask = np.zeros((10, 10), dtype=bool)
        self.assertEqual(base_point(mask, (3.0, 4.0), CAT["box"]), (3.0, 4.0))
        self.assertEqual(base_point(mask, None, CAT["box"]), (300.0, 250.0))

    def test_keypoints_inside_reports_only_hits(self) -> None:
        mask = np.zeros((20, 20), dtype=bool)
        mask[5:10, 5:10] = True
        kps = {"left_front_paw": (7.0, 7.0), "right_front_paw": (15.0, 15.0), "nose": (7.2, 8.9)}
        self.assertEqual(keypoints_inside(mask, kps, ["left_front_paw", "right_front_paw"]), ["left_front_paw"])
        self.assertEqual(keypoints_inside(mask, kps, ["nose", "left_eye"]), ["nose"])


if __name__ == "__main__":
    unittest.main()
