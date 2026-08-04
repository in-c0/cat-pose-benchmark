from __future__ import annotations

import json
import unittest
from pathlib import Path

from stage0.compare_reports import compare_values
from stage0.hardware_feasibility import evaluate, field_of_view_degrees, raw_rate_bytes_per_second


class HardwareFeasibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(__file__).parents[1]
        cls.config = json.loads(
            (Path(__file__).with_name("hardware_candidates.json")).read_text(
                encoding="utf-8"
            )
        )

    def test_committed_report_matches_calculation(self) -> None:
        expected = json.loads(
            (Path(__file__).with_name("hardware-feasibility-report.json")).read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(compare_values(expected, evaluate(self.config)), [])

    def test_purchase_is_rejected(self) -> None:
        report = evaluate(self.config)
        self.assertFalse(report["purchase_feasible"])
        self.assertGreater(report["budget_multiple"], 5.0)

    def test_candidate_fields_cover_nominal_width_at_one_metre(self) -> None:
        report = evaluate(self.config)
        for candidate in report["candidates"]:
            at_one_metre = next(
                span for span in candidate["spans"] if span["distance_m"] == 1.0
            )
            self.assertGreater(at_one_metre["horizontal_span_m"], 1.5)
            self.assertGreater(at_one_metre["vertical_span_m"], 1.0)

    def test_raw_bayer8_rate_at_sixty_fps(self) -> None:
        rate = raw_rate_bytes_per_second(1920, 1200, 60.0, 8)
        self.assertEqual(rate, 138_240_000.0)

    def test_fov_is_monotonic_with_focal_length(self) -> None:
        self.assertGreater(
            field_of_view_degrees(6.624, 4.0),
            field_of_view_degrees(6.624, 6.0),
        )


if __name__ == "__main__":
    unittest.main()
