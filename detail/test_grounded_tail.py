from __future__ import annotations

import unittest

import numpy as np

from detail.grounded_tail import (
    MAX_BODY_CONTACT_FRACTION,
    MAX_TAIL_TO_CAT_AREA,
    MIN_ELONGATION,
    MIN_TAIL_SCORE,
    base_point,
    geometry_features,
    geometry_rejections,
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

    def test_merged_cat_tail_label_counts_as_cat(self) -> None:
        merged = {"label": "cat tail", "score": 0.66, "box": [0.0, 0.0, 300.0, 200.0]}
        self.assertIs(pick_cat_box([merged], None), merged)

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


class GeometryTests(unittest.TestCase):
    def _cat_and_tail(self, tail_along_body: bool) -> tuple[np.ndarray, np.ndarray, list[dict]]:
        import cv2

        cat = np.zeros((300, 500), dtype=np.uint8)
        cv2.ellipse(cat, (250, 150), (150, 60), 0, 0, 360, 1, -1)
        tail = np.zeros_like(cat)
        if tail_along_body:
            # a strip lying along the top edge of the trunk
            cv2.rectangle(tail, (120, 88), (380, 100), 1, -1)
        else:
            # a thin tail leaving the rump and going up
            cv2.line(tail, (100, 150), (40, 40), 1, thickness=10)
        cat_all = np.logical_or(cat.astype(bool), tail.astype(bool))
        ys, xs = np.nonzero(tail)
        order = np.argsort(xs)
        samples = [{"x_px": float(xs[i]), "y_px": float(ys[i])} for i in order[:: max(1, len(order) // 12)]]
        return tail.astype(bool), cat_all, samples

    def test_extended_tail_passes_and_strip_fails(self) -> None:
        box = [90.0, 30.0, 400.0, 210.0]
        tail, cat, samples = self._cat_and_tail(tail_along_body=False)
        f = geometry_features(tail, cat, box, samples)
        self.assertLessEqual(f["body_contact_fraction"], MAX_BODY_CONTACT_FRACTION)
        self.assertGreaterEqual(f["elongation"], MIN_ELONGATION)
        self.assertEqual(geometry_rejections(f), [])
        strip, cat2, samples2 = self._cat_and_tail(tail_along_body=True)
        f2 = geometry_features(strip, cat2, box, samples2)
        self.assertIn("attached_along_body", geometry_rejections(f2))


if __name__ == "__main__":
    unittest.main()
