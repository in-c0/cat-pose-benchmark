from __future__ import annotations

import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from detail.evaluate import _validate_curve, evaluate_sequence


ROOT = Path(__file__).resolve().parents[1]


class FelineDetailTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schema = json.loads(
            (ROOT / "detail" / "feline-detail.schema.json").read_text(encoding="utf-8")
        )
        cls.reference = json.loads(
            (ROOT / "detail" / "fixtures" / "reference.json").read_text(encoding="utf-8")
        )
        cls.prediction = json.loads(
            (ROOT / "detail" / "fixtures" / "prediction.json").read_text(encoding="utf-8")
        )

    def test_reference_and_prediction_conform_to_schema(self) -> None:
        validator = Draft202012Validator(self.schema)
        self.assertEqual(list(validator.iter_errors(self.reference)), [])
        self.assertEqual(list(validator.iter_errors(self.prediction)), [])

    def test_ordered_curve_resampling_allows_different_control_point_counts(self) -> None:
        result = evaluate_sequence(self.reference, self.prediction)
        first_tail = result["frames"][0]["tail"]
        self.assertEqual(first_tail["reference_sample_count"], 5)
        self.assertEqual(first_tail["prediction_sample_count"], 6)
        self.assertIsNotNone(first_tail["normalized_ordered_curve_mean_error"])
        self.assertLess(first_tail["normalized_ordered_curve_mean_error"], 0.01)
        self.assertLess(first_tail["normalized_base_error"], 0.01)
        self.assertLess(first_tail["normalized_tip_error"], 0.01)

    def test_hidden_reference_curve_is_not_scored_as_observed_truth(self) -> None:
        result = evaluate_sequence(self.reference, self.prediction)
        second_tail = result["frames"][1]["tail"]
        self.assertLess(second_tail["reference_observable_fraction"], 1.0)
        self.assertIsNone(second_tail["normalized_ordered_curve_mean_error"])
        self.assertIsNone(second_tail["normalized_ordered_curve_max_error"])
        self.assertEqual(result["summary"]["fully_observable_tail_frames"], 1)

    def test_ear_geometry_reports_small_point_and_axis_errors(self) -> None:
        result = evaluate_sequence(self.reference, self.prediction)
        self.assertIsNotNone(result["summary"]["mean_normalized_ear_point_error"])
        self.assertLess(result["summary"]["mean_normalized_ear_point_error"], 0.01)
        self.assertIsNotNone(result["summary"]["mean_ear_axis_error_degrees"])
        self.assertLess(result["summary"]["mean_ear_axis_error_degrees"], 5.0)

    def test_curve_requires_strict_base_to_tip_parameterization(self) -> None:
        with self.assertRaisesRegex(ValueError, "strictly increasing"):
            _validate_curve(
                [
                    {"u": 0.0, "x_px": 0.0, "y_px": 0.0},
                    {"u": 0.5, "x_px": 1.0, "y_px": 1.0},
                    {"u": 0.5, "x_px": 2.0, "y_px": 2.0},
                    {"u": 1.0, "x_px": 3.0, "y_px": 3.0},
                ]
            )


if __name__ == "__main__":
    unittest.main()
