from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from temporal.appearance_assignment import assign_candidates


class AppearanceAssignmentTests(unittest.TestCase):
    def _write_frame(self, directory: Path, index: int, rgb: tuple[int, int, int]) -> None:
        Image.new("RGB", (100, 80), rgb).save(directory / f"{index:05d}.jpg")

    def _seed(self) -> dict:
        return {
            "clip_id": "fixture",
            "target_id": "grey-cat",
            "source_frame": {"smoke_frame_index": 5, "width_px": 100, "height_px": 80},
            "positive_points": [
                {"x_px": 20.0, "y_px": 20.0},
                {"x_px": 70.0, "y_px": 60.0},
            ],
            "prompt_provenance": {"evidence_tier": "R3"},
        }

    def test_rejects_wrong_only_candidate_and_reacquires_matching_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            directory = Path(directory_name)
            # Seed / correct target = grey; wrong candidate = black.
            self._write_frame(directory, 5, (130, 130, 130))
            self._write_frame(directory, 8, (130, 130, 130))
            self._write_frame(directory, 9, (0, 0, 0))
            self._write_frame(directory, 10, (0, 0, 0))

            multi = {
                "frames": [
                    {"frame_index": 8, "candidates": []},
                    {
                        "frame_index": 9,
                        "candidates": [
                            {
                                "individual": "wrong",
                                "bbox_xyxy": [0, 0, 99, 79],
                                "mean_keypoint_score": 0.95,
                                "high_confidence_keypoint_count": 30,
                            }
                        ],
                    },
                    {
                        "frame_index": 10,
                        "candidates": [
                            {
                                "individual": "wrong",
                                "bbox_xyxy": [0, 0, 45, 79],
                                "mean_keypoint_score": 0.99,
                                "high_confidence_keypoint_count": 35,
                            },
                            {
                                "individual": "target",
                                "bbox_xyxy": [50, 0, 99, 79],
                                "mean_keypoint_score": 0.6,
                                "high_confidence_keypoint_count": 20,
                            },
                        ],
                    },
                ]
            }
            # Make the right half of frame 10 grey so the lower-confidence target wins.
            image = Image.new("RGB", (100, 80), (0, 0, 0))
            for x in range(50, 100):
                for y in range(80):
                    image.putpixel((x, y), (130, 130, 130))
            image.save(directory / "00010.jpg")

            result = assign_candidates(
                multi,
                self._seed(),
                frames_dir=directory,
                appearance_threshold=0.10,
                seed_padding_fraction=0.0,
                histogram_bins=4,
            )

            self.assertEqual([frame["state"] for frame in result["frames"]], ["lost", "lost", "target"])
            self.assertEqual(result["frames"][2]["transition"], "reacquired")
            self.assertEqual(result["frames"][2]["selected_candidate"]["individual"], "target")

    def test_seed_must_remain_r3(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            directory = Path(directory_name)
            self._write_frame(directory, 5, (130, 130, 130))
            seed = self._seed()
            seed["prompt_provenance"]["evidence_tier"] = "G"
            with self.assertRaisesRegex(ValueError, "R3"):
                assign_candidates(
                    {"frames": []},
                    seed,
                    frames_dir=directory,
                    appearance_threshold=0.3,
                )


if __name__ == "__main__":
    unittest.main()
