from __future__ import annotations

import unittest

from detail.prompt_from_prediction import select_tail_prompt


def _point(name: str, x: float, y: float, score: float) -> dict:
    return {
        "native_name": name,
        "canonical_name": name,
        "x_px": x,
        "y_px": y,
        "score": score,
    }


def _frame(index: int, base_score: float, tip_score: float, tip_x: float) -> dict:
    return {
        "frame_index": index,
        "timestamp_s": index / 2,
        "inference_ms": 1.0,
        "keypoints_2d": [
            _point("tail_base", 100.0, 100.0, base_score),
            _point("tail_tip", tip_x, 100.0, tip_score),
            _point("nose", 400.0, 300.0, 0.9),
            _point("neck_base", 350.0, 280.0, 0.8),
            _point("back_middle", 220.0, 220.0, 0.85),
            _point("left_hind_paw", 260.0, 330.0, 0.7),
        ],
    }


class TailPromptSelectionTests(unittest.TestCase):
    def test_selects_best_minimum_endpoint_confidence(self) -> None:
        prediction = {
            "clip_id": "mock",
            "model": {
                "id": "superanimal_quadruped",
                "version": "test",
                "checkpoint": "test",
                "commercial_status": "research_only",
            },
            "source": {"width_px": 640, "height_px": 480, "fps": 2.0},
            "frames": [
                _frame(0, 0.95, 0.25, 180.0),
                _frame(1, 0.72, 0.80, 210.0),
                _frame(2, 0.65, 0.95, 240.0),
            ],
        }
        prompt = select_tail_prompt(
            prediction,
            source_video="mock.mp4",
            min_score=0.2,
            min_separation_fraction=0.03,
        )
        self.assertEqual(prompt["source_frame"]["smoke_frame_index"], 1)
        self.assertEqual(prompt["positive_points"][0]["semantic_name"], "tail_base")
        self.assertEqual(prompt["positive_points"][1]["semantic_name"], "tail_tip")
        self.assertGreaterEqual(len(prompt["negative_points"]), 2)
        self.assertEqual(prompt["prompt_provenance"]["evidence_tier"], "R3")

    def test_rejects_collapsed_or_low_confidence_endpoints(self) -> None:
        prediction = {
            "clip_id": "mock",
            "model": {
                "id": "superanimal_quadruped",
                "version": "test",
                "checkpoint": "test",
                "commercial_status": "research_only",
            },
            "source": {"width_px": 640, "height_px": 480, "fps": 2.0},
            "frames": [
                _frame(0, 0.9, 0.1, 220.0),
                _frame(1, 0.9, 0.9, 105.0),
            ],
        }
        with self.assertRaisesRegex(ValueError, "No frame"):
            select_tail_prompt(
                prediction,
                source_video="mock.mp4",
                min_score=0.2,
                min_separation_fraction=0.03,
            )


if __name__ == "__main__":
    unittest.main()
