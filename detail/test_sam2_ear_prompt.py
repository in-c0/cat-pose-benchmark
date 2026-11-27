from __future__ import annotations

import unittest

from detail.sam2_ear_prompt import _rank


class EarPromptCandidateTests(unittest.TestCase):
    def test_semantic_part_mask_beats_higher_iou_head_mask(self) -> None:
        ear = {
            "positive_prompt_inside_fraction": 1.0,
            "negative_prompt_outside_fraction": 1.0,
            "geometry_valid": True,
            "mask_area_fraction": 0.001,
            "sam2_predicted_iou": 0.2,
        }
        head = {
            "positive_prompt_inside_fraction": 1.0,
            "negative_prompt_outside_fraction": 0.5,
            "geometry_valid": True,
            "mask_area_fraction": 0.02,
            "sam2_predicted_iou": 0.9,
        }
        self.assertGreater(_rank(ear), _rank(head))

    def test_smaller_valid_part_mask_wins_when_prompt_consistency_ties(self) -> None:
        small = {
            "positive_prompt_inside_fraction": 1.0,
            "negative_prompt_outside_fraction": 1.0,
            "geometry_valid": True,
            "mask_area_fraction": 0.001,
            "sam2_predicted_iou": 0.3,
        }
        large = {
            "positive_prompt_inside_fraction": 1.0,
            "negative_prompt_outside_fraction": 1.0,
            "geometry_valid": True,
            "mask_area_fraction": 0.01,
            "sam2_predicted_iou": 0.95,
        }
        self.assertGreater(_rank(small), _rank(large))

    def test_valid_geometry_beats_invalid_geometry(self) -> None:
        valid = {
            "positive_prompt_inside_fraction": 1.0,
            "negative_prompt_outside_fraction": 1.0,
            "geometry_valid": True,
            "mask_area_fraction": 0.002,
            "sam2_predicted_iou": 0.2,
        }
        invalid = {
            "positive_prompt_inside_fraction": 1.0,
            "negative_prompt_outside_fraction": 1.0,
            "geometry_valid": False,
            "mask_area_fraction": 0.0005,
            "sam2_predicted_iou": 0.95,
        }
        self.assertGreater(_rank(valid), _rank(invalid))


if __name__ == "__main__":
    unittest.main()
