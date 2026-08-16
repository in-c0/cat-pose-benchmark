from __future__ import annotations

import unittest

from detail.sam2_tail_video import _summary


class TailVideoSummaryTests(unittest.TestCase):
    def test_feasibility_pass_requires_coverage_without_mask_explosion(self) -> None:
        records = [
            {
                "frame_index": index,
                "curve_status": "ok",
                "mask_area_fraction": 0.004 + index * 0.0001,
                "root_xy": [100.0 + index, 200.0],
                "tip_xy": [150.0 + index * 2, 220.0],
            }
            for index in range(4)
        ]
        result = _summary(records, seed_frame_idx=1, image_diagonal=1000.0)
        self.assertEqual(result["engineering_feasibility"], "pass")
        self.assertEqual(result["curve_coverage"], 1.0)
        self.assertEqual(result["suspicious_expansion_frames"], [])

    def test_large_mask_expansion_forces_revise(self) -> None:
        records = [
            {
                "frame_index": 0,
                "curve_status": "ok",
                "mask_area_fraction": 0.004,
                "root_xy": [100.0, 200.0],
                "tip_xy": [150.0, 220.0],
            },
            {
                "frame_index": 1,
                "curve_status": "ok",
                "mask_area_fraction": 0.004,
                "root_xy": [101.0, 200.0],
                "tip_xy": [152.0, 220.0],
            },
            {
                "frame_index": 2,
                "curve_status": "ok",
                "mask_area_fraction": 0.03,
                "root_xy": [102.0, 200.0],
                "tip_xy": [154.0, 220.0],
            },
        ]
        result = _summary(records, seed_frame_idx=0, image_diagonal=1000.0)
        self.assertEqual(result["engineering_feasibility"], "revise")
        self.assertEqual(result["suspicious_expansion_frames"], [2])

    def test_missing_curves_reduce_coverage(self) -> None:
        records = [
            {
                "frame_index": 0,
                "curve_status": "ok",
                "mask_area_fraction": 0.004,
                "root_xy": [100.0, 200.0],
                "tip_xy": [150.0, 220.0],
            },
            {
                "frame_index": 1,
                "curve_status": "failed",
                "mask_area_fraction": 0.0,
            },
            {
                "frame_index": 2,
                "curve_status": "failed",
                "mask_area_fraction": 0.0,
            },
            {
                "frame_index": 3,
                "curve_status": "failed",
                "mask_area_fraction": 0.0,
            },
        ]
        result = _summary(records, seed_frame_idx=0, image_diagonal=1000.0)
        self.assertEqual(result["curve_coverage"], 0.25)
        self.assertEqual(result["engineering_feasibility"], "revise")


if __name__ == "__main__":
    unittest.main()
