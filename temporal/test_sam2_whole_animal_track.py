from __future__ import annotations

import unittest

import numpy as np

from temporal.sam2_whole_animal_track import (
    _candidate_rank,
    _js_divergence,
    _summary,
)


class WholeAnimalIdentityTests(unittest.TestCase):
    def test_semantic_candidate_beats_higher_score_background_mask(self) -> None:
        target = {
            "positive_prompt_inside_fraction": 1.0,
            "negative_prompt_outside_fraction": 1.0,
            "sam2_predicted_iou": 0.55,
            "mask_area_fraction": 0.03,
        }
        background = {
            "positive_prompt_inside_fraction": 1.0,
            "negative_prompt_outside_fraction": 0.5,
            "sam2_predicted_iou": 0.95,
            "mask_area_fraction": 0.40,
        }
        self.assertGreater(_candidate_rank(target), _candidate_rank(background))

    def test_js_divergence_zero_for_identical_histograms(self) -> None:
        hist = np.array([0.25, 0.25, 0.5], dtype=np.float64)
        self.assertAlmostEqual(_js_divergence(hist, hist), 0.0)

    def test_summary_passes_clean_mask_continuity(self) -> None:
        records = [
            {
                "frame_index": index,
                "mask_area_px": 1000,
                "mask_area_fraction": 0.03,
                "centroid_xy": [100.0 + index * 3.0, 200.0],
                "seed_appearance_jsd": 0.02 * index,
            }
            for index in range(4)
        ]
        result = _summary(
            records,
            seed_frame_idx=1,
            seed_area_fraction=0.03,
            seed_mask_iou=0.96,
            image_diagonal=1000.0,
        )
        self.assertEqual(result["engineering_feasibility"], "pass")
        self.assertEqual(result["empty_frames"], [])
        self.assertEqual(result["expansion_frames"], [])
        self.assertEqual(result["collapse_frames"], [])

    def test_summary_revises_on_collapse(self) -> None:
        records = [
            {
                "frame_index": 0,
                "mask_area_px": 1000,
                "mask_area_fraction": 0.03,
                "centroid_xy": [100.0, 200.0],
                "seed_appearance_jsd": 0.0,
            },
            {
                "frame_index": 1,
                "mask_area_px": 10,
                "mask_area_fraction": 0.001,
                "centroid_xy": [105.0, 200.0],
                "seed_appearance_jsd": 0.5,
            },
        ]
        result = _summary(
            records,
            seed_frame_idx=0,
            seed_area_fraction=0.03,
            seed_mask_iou=0.96,
            image_diagonal=1000.0,
        )
        self.assertEqual(result["engineering_feasibility"], "revise")
        self.assertEqual(result["collapse_frames"], [1])

    def test_summary_revises_on_bad_seed_preservation(self) -> None:
        records = [
            {
                "frame_index": 0,
                "mask_area_px": 1000,
                "mask_area_fraction": 0.03,
                "centroid_xy": [100.0, 200.0],
                "seed_appearance_jsd": 0.0,
            }
        ]
        result = _summary(
            records,
            seed_frame_idx=0,
            seed_area_fraction=0.03,
            seed_mask_iou=0.5,
            image_diagonal=1000.0,
        )
        self.assertEqual(result["engineering_feasibility"], "revise")
        self.assertFalse(result["seed_preserved"])


if __name__ == "__main__":
    unittest.main()
