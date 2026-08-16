from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from stage0.generate_target import generate


class TargetGeneratorTests(unittest.TestCase):
    def test_target_generation_is_unique_and_partitioned(self) -> None:
        spec_path = Path(__file__).with_name("target_spec.json")
        with tempfile.TemporaryDirectory() as directory:
            output_dir = Path(directory)
            manifest = generate(spec_path, output_dir, dpi_override=72)
            self.assertEqual(len(manifest["panels"]), 3)
            marker_ids = [marker_id for panel in manifest["panels"] for marker_id in panel["marker_ids"]]
            self.assertEqual(len(marker_ids), len(set(marker_ids)))
            for panel in manifest["panels"]:
                with Image.open(output_dir / panel["file"]) as image:
                    self.assertEqual(list(image.size), panel["pixel_size"])
            points = json.loads((output_dir / "target-nominal-points.json").read_text(encoding="utf-8"))["points"]
            self.assertEqual({point["partition"] for point in points}, {"calibration", "validation", "holdout"})
            self.assertTrue(all(point["truth_status"] == "construction_nominal_only" for point in points))


if __name__ == "__main__":
    unittest.main()
