from __future__ import annotations

import copy
import json
import math
import tempfile
import unittest
from pathlib import Path

from synthetic.reference_stage_s0 import (
    camera_basis,
    compare_values,
    editor_version,
    generate_reference,
)
from synthetic.validate_sequence import validate_sequence


class StageS0ReferenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(__file__).parents[1]
        cls.schema = json.loads(
            (cls.root / "schemas" / "synthetic-sequence.schema.json").read_text(
                encoding="utf-8"
            )
        )

    def test_reference_is_schema_and_invariant_valid(self) -> None:
        reference = generate_reference("6000.0.75f1")
        self.assertEqual(validate_sequence(reference, self.schema), [])

    def test_camera_basis_is_orthonormal(self) -> None:
        right, up, forward = camera_basis()
        for vector in (right, up, forward):
            self.assertAlmostEqual(math.sqrt(sum(value * value for value in vector)), 1.0)
        self.assertAlmostEqual(sum(a * b for a, b in zip(right, up)), 0.0)
        self.assertAlmostEqual(sum(a * b for a, b in zip(right, forward)), 0.0)
        self.assertAlmostEqual(sum(a * b for a, b in zip(up, forward)), 0.0)

    def test_reference_projects_visible_landmarks_inside_image(self) -> None:
        reference = generate_reference("6000.0.75f1")
        width, height = reference["camera"]["resolution_px"]
        for frame in reference["frames"]:
            for landmark in frame["landmarks"]:
                if landmark["visibility"] != "visible":
                    continue
                self.assertGreaterEqual(landmark["camera_m"]["z"], 0.0)
                self.assertGreaterEqual(landmark["image_px"]["x"], 0.0)
                self.assertLessEqual(landmark["image_px"]["x"], width)
                self.assertGreaterEqual(landmark["image_px"]["y"], 0.0)
                self.assertLessEqual(landmark["image_px"]["y"], height)

    def test_comparison_detects_projection_drift(self) -> None:
        expected = generate_reference("6000.0.75f1")
        actual = copy.deepcopy(expected)
        actual["frames"][0]["landmarks"][0]["image_px"]["x"] += 0.25
        errors = compare_values(expected, actual, abs_tol=1e-4, rel_tol=1e-6)
        self.assertTrue(any("image_px.x" in error for error in errors))

    def test_comparison_accepts_float_noise_within_tolerance(self) -> None:
        expected = generate_reference("6000.0.75f1")
        actual = copy.deepcopy(expected)
        actual["frames"][0]["landmarks"][0]["image_px"]["x"] += 5e-5
        self.assertEqual(
            compare_values(expected, actual, abs_tol=1e-4, rel_tol=1e-6),
            [],
        )

    def test_project_version_parser(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ProjectVersion.txt"
            path.write_text("m_EditorVersion: 6000.0.75f1\n", encoding="utf-8")
            self.assertEqual(editor_version(path), "6000.0.75f1")


if __name__ == "__main__":
    unittest.main()
