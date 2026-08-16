from __future__ import annotations

import unittest

from detail.sam2_tail_video import _summary


class TailVideoSummaryTests(unittest.TestCase):
    def _summary(self, records, *, seed_iou: float = 0.98, seed_area: float = 0.004):
        return _summary(
            records,
            seed_frame_idx=0,
            image_diagonal=1000.0,
            input_seed_area_fraction=seed_area,
            seed_mask_iou=seed_iou,
        )

    def test_feasibility_pass_requires_preserved_seed_and_clean_sequence(self) -> None:
        records = [
            {
                "frame_index": index,
                "curve_status": "ok",
                "mask_area_fraction": 0.004 + index * 0.0001,
                "curve_length_px": 120.0,
                "root_xy": [100.0 + index, 200.0],
                "tip_xy": [150.0 + index * 2, 220.0],
            }
            for index in range(4)
        ]
        result = self._summary(records)
        self.assertEqual(result["engineering_feasibility"], "pass")
        self.assertTrue(result["video_seed_preserved"])
        self.assertEqual(result["suspicious_expansion_frames"], [])
        self.assertEqual(result["degenerate_curve_frames"], [])

    def test_low_seed_iou_forces_revise(self) -> None:
        records = [
            {
                "frame_index": 0,
                "curve_status": "ok",
                "mask_area_fraction": 0.004,
                "curve_length_px": 120.0,
                "root_xy": [100.0, 200.0],
                "tip_xy": [150.0, 220.0],
            }
        ]
        result = self._summary(records, seed_iou=0.4)
        self.assertEqual(result["engineering_feasibility"], "revise")
        self.assertFalse(result["video_seed_preserved"])

    def test_large_mask_expansion_forces_revise(self) -> None:
        records = [
            {
                "frame_index": 0,
                "curve_status": "ok",
                "mask_area_fraction": 0.004,
                "curve_length_px": 120.0,
                "root_xy": [100.0, 200.0],
                "tip_xy": [150.0, 220.0],
            },
            {
                "frame_index": 1,
                "curve_status": "ok",
                "mask_area_fraction": 0.03,
                "curve_length_px": 130.0,
                "root_xy": [101.0, 200.0],
                "tip_xy": [152.0, 220.0],
            },
        ]
        result = self._summary(records)
        self.assertEqual(result["engineering_feasibility"], "revise")
        self.assertEqual(result["suspicious_expansion_frames"], [1])

    def test_degenerate_curve_forces_revise(self) -> None:
        records = [
            {
                "frame_index": 0,
                "curve_status": "ok",
                "mask_area_fraction": 0.004,
                "curve_length_px": 120.0,
                "root_xy": [100.0, 200.0],
                "tip_xy": [150.0, 220.0],
            },
            {
                "frame_index": 1,
                "curve_status": "ok",
                "mask_area_fraction": 0.003,
                "curve_length_px": 3.0,
                "root_xy": [101.0, 200.0],
                "tip_xy": [102.0, 201.0],
            },
        ]
        result = self._summary(records)
        self.assertEqual(result["engineering_feasibility"], "revise")
        self.assertEqual(result["degenerate_curve_frames"], [1])

    def test_missing_curves_reduce_coverage(self) -> None:
        records = [
            {
                "frame_index": 0,
                "curve_status": "ok",
                "mask_area_fraction": 0.004,
                "curve_length_px": 120.0,
                "root_xy": [100.0, 200.0],
                "tip_xy": [150.0, 220.0],
            },
            {"frame_index": 1, "curve_status": "failed", "mask_area_fraction": 0.0},
            {"frame_index": 2, "curve_status": "failed", "mask_area_fraction": 0.0},
            {"frame_index": 3, "curve_status": "failed", "mask_area_fraction": 0.0},
        ]
        result = self._summary(records)
        self.assertEqual(result["curve_coverage"], 0.25)
        self.assertEqual(result["engineering_feasibility"], "revise")


if __name__ == "__main__":
    unittest.main()
