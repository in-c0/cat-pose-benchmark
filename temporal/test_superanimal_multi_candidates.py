from __future__ import annotations

import unittest

import pandas as pd

from temporal.superanimal_multi_candidates import dataframe_to_candidate_frames


class MultiCandidateConversionTests(unittest.TestCase):
    def _dataframe(self) -> pd.DataFrame:
        columns = pd.MultiIndex.from_tuples(
            [
                ("model", "cat_a", "nose", "x"),
                ("model", "cat_a", "nose", "y"),
                ("model", "cat_a", "nose", "likelihood"),
                ("model", "cat_a", "tail_base", "x"),
                ("model", "cat_a", "tail_base", "y"),
                ("model", "cat_a", "tail_base", "likelihood"),
                ("model", "cat_b", "nose", "x"),
                ("model", "cat_b", "nose", "y"),
                ("model", "cat_b", "nose", "likelihood"),
                ("model", "cat_b", "tail_base", "x"),
                ("model", "cat_b", "tail_base", "y"),
                ("model", "cat_b", "tail_base", "likelihood"),
            ],
            names=["scorer", "individuals", "bodyparts", "coords"],
        )
        return pd.DataFrame(
            [
                [100, 200, 0.9, 150, 220, 0.8, 500, 250, 0.7, 550, 270, 0.6],
                [110, 205, 0.9, 160, 225, 0.8, float("nan"), float("nan"), 0.0, float("nan"), float("nan"), 0.0],
            ],
            columns=columns,
        )

    def test_two_individuals_are_preserved_as_candidates(self) -> None:
        frames = dataframe_to_candidate_frames(
            self._dataframe(), fps=2.0, frame_offset=8, confidence_threshold=0.2
        )
        self.assertEqual(frames[0]["frame_index"], 8)
        self.assertEqual(frames[0]["candidate_count"], 2)
        self.assertEqual({candidate["individual"] for candidate in frames[0]["candidates"]}, {"cat_a", "cat_b"})

    def test_empty_allocated_individual_is_not_manufactured(self) -> None:
        frames = dataframe_to_candidate_frames(
            self._dataframe(), fps=2.0, frame_offset=8, confidence_threshold=0.2
        )
        self.assertEqual(frames[1]["candidate_count"], 1)
        self.assertEqual(frames[1]["candidates"][0]["individual"], "cat_a")

    def test_frame_offset_and_timestamp_are_explicit(self) -> None:
        frames = dataframe_to_candidate_frames(
            self._dataframe(), fps=2.0, frame_offset=8, confidence_threshold=0.2
        )
        self.assertEqual(frames[1]["frame_index"], 9)
        self.assertEqual(frames[1]["timestamp_s"], 4.5)


if __name__ == "__main__":
    unittest.main()
