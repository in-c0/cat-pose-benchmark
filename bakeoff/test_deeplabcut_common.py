from __future__ import annotations

import unittest

import pandas as pd

from bakeoff.adapters.deeplabcut_common import (
    QUADRUPED_CANONICAL_NAME,
    dataframe_to_2d_frames,
    dataframe_to_3d_by_frame,
)
from bakeoff.adapters.fmpose3d_animal import FMPOSE_CANONICAL_NAME


class DeepLabCutDataframeTests(unittest.TestCase):
    def test_selects_highest_confidence_individual_and_maps_feline_points(self) -> None:
        columns = pd.MultiIndex.from_tuples(
            [
                ("DLC", individual, bodypart, coord)
                for individual in ("individual1", "individual2")
                for bodypart in ("nose", "left_earend", "tail_base", "tail_end")
                for coord in ("x", "y", "likelihood")
            ],
            names=["scorer", "individuals", "bodyparts", "coords"],
        )
        rows = []
        for frame in range(2):
            values = []
            for individual in ("individual1", "individual2"):
                for bodypart_index, _bodypart in enumerate(
                    ("nose", "left_earend", "tail_base", "tail_end")
                ):
                    confidence = 0.3 if individual == "individual1" else 0.9
                    values.extend(
                        [
                            100.0 + frame + bodypart_index,
                            200.0 + bodypart_index,
                            confidence,
                        ]
                    )
            rows.append(values)
        dataframe = pd.DataFrame(rows, columns=columns)

        frames = dataframe_to_2d_frames(
            dataframe,
            fps=25.0,
            inference_ms_per_frame=12.5,
            canonical_map=QUADRUPED_CANONICAL_NAME,
        )

        self.assertEqual(len(frames), 2)
        names = {point["canonical_name"] for point in frames[0]["keypoints_2d"]}
        self.assertIn("left_ear_tip", names)
        self.assertIn("tail_base", names)
        self.assertIn("tail_tip", names)
        self.assertTrue(all(point["score"] == 0.9 for point in frames[0]["keypoints_2d"]))
        self.assertEqual(frames[1]["timestamp_s"], 1 / 25.0)

    def test_converts_single_individual_fmpose_3d_without_claiming_camera_frame(self) -> None:
        bodyparts = ("nose", "root_of_tail", "left_ear", "tail_tip")
        columns = pd.MultiIndex.from_tuples(
            [
                ("DLC_fmpose3d_animals_3d", bodypart, coord)
                for bodypart in bodyparts
                for coord in ("x", "y", "z")
            ],
            names=["scorer", "bodyparts", "coords"],
        )
        dataframe = pd.DataFrame(
            [[float(index) for index in range(len(columns))]], columns=columns
        )

        frames = dataframe_to_3d_by_frame(
            dataframe,
            canonical_map=FMPOSE_CANONICAL_NAME,
            coordinate_frame="model_native",
        )
        by_native = {point["native_name"]: point for point in frames[0]}

        self.assertEqual(by_native["root_of_tail"]["canonical_name"], "tail_base")
        self.assertEqual(by_native["tail_tip"]["canonical_name"], "tail_tip")
        self.assertEqual(by_native["left_ear"]["canonical_name"], "left_ear")
        self.assertEqual(by_native["nose"]["coordinate_frame"], "model_native")


if __name__ == "__main__":
    unittest.main()
