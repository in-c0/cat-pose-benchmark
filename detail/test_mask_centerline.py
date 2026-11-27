from __future__ import annotations

import math
import unittest

import numpy as np
from skimage.draw import line
from skimage.morphology import binary_dilation, disk

from detail.mask_centerline import mask_to_tail_samples


class TailMaskBaselineTests(unittest.TestCase):
    def _mask(self) -> np.ndarray:
        mask = np.zeros((72, 72), dtype=bool)
        path_xy = [(10, 12), (22, 20), (34, 19), (46, 30), (58, 44)]
        for (x0, y0), (x1, y1) in zip(path_xy, path_xy[1:]):
            rows, cols = line(y0, x0, y1, x1)
            mask[rows, cols] = True
        # Add a short segmentation spur; the longest-path rule should still choose the
        # true far endpoint rather than the small branch.
        rows, cols = line(19, 34, 12, 38)
        mask[rows, cols] = True
        return binary_dilation(mask, disk(2))

    def test_extracts_ordered_curve_from_base_to_longest_endpoint(self) -> None:
        samples = mask_to_tail_samples(
            self._mask(), base_xy=(10.0, 12.0), sample_count=16
        )
        self.assertEqual(len(samples), 16)
        self.assertEqual(samples[0]["u"], 0.0)
        self.assertEqual(samples[-1]["u"], 1.0)
        self.assertTrue(
            all(left["u"] < right["u"] for left, right in zip(samples, samples[1:]))
        )

        base_error = math.hypot(
            samples[0]["x_px"] - 10.0, samples[0]["y_px"] - 12.0
        )
        tip_error = math.hypot(
            samples[-1]["x_px"] - 58.0, samples[-1]["y_px"] - 44.0
        )
        self.assertLess(base_error, 4.0)
        self.assertLess(tip_error, 5.0)

    def test_rejects_empty_mask(self) -> None:
        with self.assertRaisesRegex(ValueError, "empty"):
            mask_to_tail_samples(
                np.zeros((16, 16), dtype=bool), base_xy=(1.0, 1.0)
            )

    def test_output_is_schema_compatible_tail_sample_shape(self) -> None:
        samples = mask_to_tail_samples(
            self._mask(), base_xy=(10.0, 12.0), sample_count=8
        )
        for sample in samples:
            self.assertEqual(sample["visibility"], "visible")
            self.assertEqual(sample["confidence"], 1.0)
            self.assertIn("provenance", sample)


if __name__ == "__main__":
    unittest.main()
