from __future__ import annotations

import json
import unittest
from pathlib import Path

from identity import youtubevis_adapter as yv


class YouTubeVISSelectionSpecTests(unittest.TestCase):
    def test_frozen_spec_matches_executable_rule(self):
        spec_path = Path(__file__).with_name("id1_youtubevis_selection_spec.json")
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        self.assertEqual(spec["spec_version"], yv.SELECTION_RULE_VERSION)
        self.assertEqual(spec["category_name"], "cat")
        self.assertEqual(spec["minimum_persistent_instances"], 2)
        self.assertEqual(
            [(row["field"], row["direction"]) for row in spec["rank_order"]],
            [
                ("cat_instance_count", "descending"),
                ("co_visible_frames", "descending"),
                ("max_internal_gap_frames", "descending"),
                ("bbox_overlap_frames", "descending"),
                ("visible_track_frames", "descending"),
                ("video_id", "ascending"),
            ],
        )
        self.assertFalse(spec["claims_boundary"]["selection_uses_model_scores"])


if __name__ == "__main__":
    unittest.main()
