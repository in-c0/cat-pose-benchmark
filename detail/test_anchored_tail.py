from __future__ import annotations

import unittest

import cv2
import numpy as np

from detail.anchored_tail import (
    ROOT_NAME,
    body_region,
    cat_prompts,
    evaluate_candidate,
    keypoint_map,
    root_component,
    select_candidate,
)

H, W = 400, 600
BBOX = [100.0, 100.0, 500.0, 300.0]  # 400 x 200, diag ~447


def _scene() -> tuple[np.ndarray, dict[str, tuple[float, float]]]:
    """A synthetic side-on cat: thick trunk, a head blob, four leg bars, and a thin
    curved tail leaving the rump. Keypoints sit where RTMPose would put them."""
    cat = np.zeros((H, W), dtype=np.uint8)
    cv2.ellipse(cat, (300, 200), (150, 60), 0, 0, 360, 1, -1)  # trunk
    cv2.circle(cat, (470, 170), 45, 1, -1)  # head
    for x in (200, 240, 360, 400):  # legs, 22 px wide
        cv2.rectangle(cat, (x - 11, 240), (x + 11, 300), 1, -1)
    # tail: 16 px wide polyline from the rump up and back
    pts = np.array([[150, 190], [110, 150], [90, 110], [95, 70]], dtype=np.int32)
    cv2.polylines(cat, [pts], False, 1, thickness=16)
    kps = {
        "nose": (505.0, 175.0),
        "left_eye": (475.0, 160.0),
        "right_eye": (480.0, 155.0),
        "neck": (430.0, 180.0),
        ROOT_NAME: (155.0, 190.0),
        "left_shoulder": (390.0, 200.0),
        "right_shoulder": (395.0, 210.0),
        "left_elbow": (400.0, 265.0),
        "right_elbow": (360.0, 265.0),
        "left_front_paw": (400.0, 295.0),
        "right_front_paw": (360.0, 295.0),
        "left_hip": (210.0, 200.0),
        "right_hip": (215.0, 210.0),
        "left_knee": (200.0, 265.0),
        "right_knee": (240.0, 265.0),
        "left_back_paw": (200.0, 295.0),
        "right_back_paw": (240.0, 295.0),
    }
    return cat.astype(bool), kps


class BodyRegionTests(unittest.TestCase):
    def test_opening_keeps_trunk_and_drops_tail(self) -> None:
        cat, kps = _scene()
        body = body_region(kps, cat, BBOX)
        self.assertTrue(body[200, 300])  # trunk centre
        self.assertTrue(body[170, 470])  # head
        self.assertTrue(body[280, 200])  # a leg, covered by the tube
        self.assertFalse(body[110, 90])  # tail mid-point

    def test_root_component_respects_tolerance(self) -> None:
        mask = np.zeros((H, W), dtype=bool)
        mask[50:60, 50:60] = True
        self.assertIsNotNone(root_component(mask, (62.0, 55.0), tolerance=5.0))
        self.assertIsNone(root_component(mask, (100.0, 55.0), tolerance=5.0))
        self.assertIsNone(root_component(np.zeros((H, W), dtype=bool), (0.0, 0.0), tolerance=5.0))


class CandidateRuleTests(unittest.TestCase):
    def test_synthetic_tail_is_accepted_and_curve_starts_at_root(self) -> None:
        cat, kps = _scene()
        record = evaluate_candidate(cat, sam_iou=0.9, kps=kps, bbox_xyxy=BBOX, previous_mask=None, sample_count=12)
        self.assertEqual(record["rejections"], [], record)
        self.assertLess(record["curve_start_to_root_px"], 30)
        self.assertGreater(record["elongation"], 3.0)
        tip = record["tip_xy"]
        self.assertLess(tip[1], 100)  # tip is up near the end of the polyline

    def test_leg_is_never_a_tail(self) -> None:
        # Drop the hind-leg keypoints that would draw the tubes, so the leg survives the
        # subtraction; move the root next to that leg. The leg keypoints are still in
        # the map for the contains-leg rule.
        cat, kps = _scene()
        kps = dict(kps)
        kps[ROOT_NAME] = (200.0, 245.0)
        for name in ("left_hip", "left_knee"):
            kps.pop(name)
        cat_no_tail = cat.copy()
        cat_no_tail[:, :170] = False
        record = evaluate_candidate(cat_no_tail, sam_iou=0.9, kps=kps, bbox_xyxy=BBOX, previous_mask=None, sample_count=12)
        self.assertTrue(
            record["rejections"] == ["nothing_at_root"] or "contains_leg_keypoint" in record["rejections"],
            record,
        )

    def test_sliver_along_body_is_rejected(self) -> None:
        cat, kps = _scene()
        cat_no_tail = cat.copy()
        cat_no_tail[:, :170] = False
        # a 6 px sliver hugging the top of the trunk, attached at the rump
        sliver = np.zeros((H, W), dtype=np.uint8)
        cv2.ellipse(sliver, (300, 200), (156, 66), 0, 180, 360, 1, -1)
        sliver = np.logical_and(sliver.astype(bool), np.logical_not(cat_no_tail))
        candidate = np.logical_or(cat_no_tail, sliver)
        kps = dict(kps)
        kps[ROOT_NAME] = (150.0, 190.0)
        record = evaluate_candidate(candidate, sam_iou=0.9, kps=kps, bbox_xyxy=BBOX, previous_mask=None, sample_count=12)
        self.assertNotEqual(record["rejections"], [], record)
        self.assertTrue(
            {"attached_along_body", "nothing_at_root", "not_elongated", "too_small"} & set(record["rejections"]),
            record,
        )

    def test_speckle_is_rejected(self) -> None:
        cat, kps = _scene()
        cat_no_tail = cat.copy()
        cat_no_tail[:, :170] = False
        rng = np.random.default_rng(0)
        speck = rng.random((H, W)) < 0.35
        speck[:, 170:] = False
        speck[:, :60] = False
        speck[:50, :] = False
        speck[250:, :] = False
        candidate = np.logical_or(cat_no_tail, speck)
        record = evaluate_candidate(candidate, sam_iou=0.9, kps=kps, bbox_xyxy=BBOX, previous_mask=None, sample_count=12)
        self.assertNotEqual(record["rejections"], [], record)

    def test_selection_prefers_temporal_agreement(self) -> None:
        a = {"rejections": [], "selection_score": 1.0}
        b = {"rejections": [], "selection_score": 1.4}
        c = {"rejections": ["too_large"], "selection_score": 9.0}
        self.assertEqual(select_candidate([a, b, c]), 1)
        self.assertIsNone(select_candidate([c]))


class PromptTests(unittest.TestCase):
    def test_keypoint_map_applies_threshold(self) -> None:
        kps = keypoint_map(
            [
                {"name": ROOT_NAME, "x_px": 1, "y_px": 2, "score": 0.9},
                {"name": "nose", "x_px": 3, "y_px": 4, "score": 0.1},
            ]
        )
        self.assertEqual(set(kps), {ROOT_NAME})

    def test_previous_tip_adds_a_prompt(self) -> None:
        _, kps = _scene()
        self.assertEqual(len(cat_prompts(kps, BBOX, None)), 2)
        self.assertEqual(len(cat_prompts(kps, BBOX, (10.0, 10.0))), 3)


if __name__ == "__main__":
    unittest.main()
