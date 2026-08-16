from __future__ import annotations

import unittest

import numpy as np
from skimage.draw import polygon

from detail.ear_mask_geometry import mask_to_ear_geometry


class EarMaskGeometryTests(unittest.TestCase):
    def _triangle(self) -> np.ndarray:
        mask = np.zeros((90, 90), dtype=np.uint8)
        rows, cols = polygon([62, 62, 14], [18, 66, 43], shape=mask.shape)
        mask[rows, cols] = 1
        return mask

    def test_triangle_yields_two_base_endpoints_and_tip(self) -> None:
        geometry = mask_to_ear_geometry(
            self._triangle(),
            base_seed_xy=(43.0, 56.0),
            tip_seed_xy=(43.0, 15.0),
            face_reference_xy=(28.0, 78.0),
            side="right",
        )
        medial = geometry["base_medial"]
        lateral = geometry["base_lateral"]
        tip = geometry["tip"]
        diagnostics = geometry["diagnostics"]

        self.assertLess(medial["x_px"], lateral["x_px"])
        self.assertLess(tip["y_px"], medial["y_px"])
        self.assertGreater(diagnostics["base_width_px"], 25.0)
        self.assertGreater(diagnostics["visible_length_px"], 30.0)
        self.assertGreater(diagnostics["triangle_area_px2"], 500.0)

    def test_face_reference_controls_medial_assignment(self) -> None:
        mask = self._triangle()
        left_face = mask_to_ear_geometry(
            mask,
            base_seed_xy=(43.0, 56.0),
            tip_seed_xy=(43.0, 15.0),
            face_reference_xy=(20.0, 78.0),
            side="right",
        )
        right_face = mask_to_ear_geometry(
            mask,
            base_seed_xy=(43.0, 56.0),
            tip_seed_xy=(43.0, 15.0),
            face_reference_xy=(70.0, 78.0),
            side="left",
        )
        self.assertLess(left_face["base_medial"]["x_px"], left_face["base_lateral"]["x_px"])
        self.assertGreater(right_face["base_medial"]["x_px"], right_face["base_lateral"]["x_px"])

    def test_empty_mask_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "empty"):
            mask_to_ear_geometry(
                np.zeros((30, 30), dtype=np.uint8),
                base_seed_xy=(10.0, 20.0),
                tip_seed_xy=(10.0, 5.0),
                face_reference_xy=(5.0, 25.0),
                side="left",
            )

    def test_collapsed_anchor_is_rejected(self) -> None:
        mask = np.zeros((20, 20), dtype=np.uint8)
        mask[8:13, 8:13] = 1
        with self.assertRaisesRegex(ValueError, "too close"):
            mask_to_ear_geometry(
                mask,
                base_seed_xy=(10.0, 10.0),
                tip_seed_xy=(10.5, 10.5),
                face_reference_xy=(10.0, 18.0),
                side="left",
            )


if __name__ == "__main__":
    unittest.main()
