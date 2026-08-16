from __future__ import annotations

import unittest

from temporal.heldout_identity_eval import select_seed


class HeldoutIdentityProtocolTests(unittest.TestCase):
    def test_first_two_candidate_frame_leftmost_is_deterministic(self) -> None:
        multi = {
            "frames": [
                {
                    "frame_index": 0,
                    "candidates": [
                        {"individual": "only", "centroid_xy": [300.0, 200.0]}
                    ],
                },
                {
                    "frame_index": 1,
                    "candidates": [
                        {"individual": "right", "centroid_xy": [420.0, 180.0]},
                        {"individual": "left", "centroid_xy": [120.0, 210.0]},
                    ],
                },
                {
                    "frame_index": 2,
                    "candidates": [
                        {"individual": "later-left", "centroid_xy": [80.0, 190.0]},
                        {"individual": "later-right", "centroid_xy": [500.0, 190.0]},
                    ],
                },
            ]
        }
        frame_index, candidate = select_seed(multi)
        self.assertEqual(frame_index, 1)
        self.assertEqual(candidate["individual"], "left")

    def test_seed_rule_rejects_single_candidate_only_sequence(self) -> None:
        multi = {
            "frames": [
                {
                    "frame_index": 0,
                    "candidates": [
                        {"individual": "only", "centroid_xy": [100.0, 100.0]}
                    ],
                }
            ]
        }
        with self.assertRaisesRegex(ValueError, "no frame contains two candidates"):
            select_seed(multi)


if __name__ == "__main__":
    unittest.main()
