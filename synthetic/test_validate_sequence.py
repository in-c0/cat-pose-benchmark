from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from synthetic.validate_sequence import canonical_sha256, validate_sequence


def valid_sequence() -> dict:
    frame_template = {
        "timestamp_ns": 0,
        "subject_root_world_m": [0.0, 0.0, 0.0],
        "subject_velocity_world_mps": [0.2, 0.0, 0.0],
        "landmarks": [
            {
                "semantic_name": "nose",
                "world_m": [0.0, 0.5, 0.4],
                "camera_m": [0.0, 0.0, 3.0],
                "image_px": [320.0, 240.0],
                "visibility": "visible"
            },
            {
                "semantic_name": "tail_tip",
                "world_m": [0.0, 0.4, -0.8],
                "camera_m": [0.0, 0.0, 2.0],
                "image_px": [300.0, 220.0],
                "visibility": "visible"
            }
        ],
        "tail_curve_world_m": [
            [0.0, 0.3, -0.3],
            [0.0, 0.35, -0.5],
            [0.0, 0.38, -0.65],
            [0.0, 0.4, -0.8]
        ],
        "contacts": [
            {
                "semantic_name": "left_front_paw_contact",
                "active": True,
                "support_surface_id": "floor"
            }
        ],
        "spatial_relations": [
            {
                "subject_id": "proxy-cat-001",
                "relation": "on",
                "object_id": "floor"
            }
        ]
    }
    first = copy.deepcopy(frame_template)
    first["frame_index"] = 0
    second = copy.deepcopy(frame_template)
    second["frame_index"] = 1
    second["timestamp_ns"] = 100_000_000
    second["subject_root_world_m"] = [0.02, 0.0, 0.0]
    second["landmarks"][0]["world_m"][0] = 0.02
    second["landmarks"][1]["world_m"][0] = 0.02
    second["tail_curve_world_m"] = [
        [point[0] + 0.02, point[1], point[2]]
        for point in second["tail_curve_world_m"]
    ]

    return {
        "schema_version": "0.1.0",
        "sequence_id": "stage-s0-validator-test",
        "subject_id": "proxy-cat-001",
        "evidence_tier": "S",
        "quality": "gold",
        "units": "metres",
        "engine": {
            "name": "Unity",
            "project": "cat-pose-benchmark/unity-viewer",
            "required_editor": "6000.0.75f1",
            "exporter": "StageS0SyntheticExporter-v0.1"
        },
        "determinism": {
            "seed": 17,
            "fixed_timestep_ns": 100_000_000,
            "frame_count": 2,
            "coordinate_convention": "unity-left-handed-x-right-y-up-z-forward"
        },
        "camera": {
            "camera_id": "synthetic-camera-0",
            "resolution_px": [640, 480],
            "vertical_fov_degrees": 60.0,
            "position_world_m": [0.0, 1.1, -3.0],
            "look_at_world_m": [0.0, 0.4, 0.0],
            "screen_origin": "bottom_left"
        },
        "scene": {
            "support_surfaces": [
                {
                    "object_id": "floor",
                    "plane_world": {
                        "normal": [0.0, 1.0, 0.0],
                        "offset_m": 0.0
                    }
                }
            ],
            "objects": [
                {
                    "object_id": "box-left",
                    "type": "box",
                    "position_world_m": [-0.8, 0.25, 0.4]
                }
            ]
        },
        "lineage": [
            "generator:procedural-proxy-v0.1",
            "seed:17"
        ],
        "frames": [first, second]
    }


class SyntheticSequenceValidatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schema = json.loads(
            (
                Path(__file__).parents[1]
                / "schemas"
                / "synthetic-sequence.schema.json"
            ).read_text(encoding="utf-8")
        )

    def test_valid_sequence_passes(self) -> None:
        self.assertEqual(validate_sequence(valid_sequence(), self.schema), [])

    def test_hash_is_canonical(self) -> None:
        first = valid_sequence()
        second = json.loads(json.dumps(first, sort_keys=True))
        self.assertEqual(canonical_sha256(first), canonical_sha256(second))

    def test_unknown_support_surface_fails(self) -> None:
        sequence = valid_sequence()
        sequence["frames"][0]["contacts"][0]["support_surface_id"] = "missing"
        errors = validate_sequence(sequence, self.schema)
        self.assertTrue(any("unknown support surface" in error for error in errors))

    def test_duplicate_landmark_fails(self) -> None:
        sequence = valid_sequence()
        sequence["frames"][0]["landmarks"][1]["semantic_name"] = "nose"
        errors = validate_sequence(sequence, self.schema)
        self.assertTrue(any("duplicate semantic_name" in error for error in errors))

    def test_visible_landmark_outside_frame_fails(self) -> None:
        sequence = valid_sequence()
        sequence["frames"][0]["landmarks"][0]["image_px"] = [-1.0, 240.0]
        errors = validate_sequence(sequence, self.schema)
        self.assertTrue(any("outside the frame" in error for error in errors))

    def test_velocity_mismatch_fails(self) -> None:
        sequence = valid_sequence()
        sequence["frames"][0]["subject_velocity_world_mps"] = [0.0, 0.0, 0.0]
        errors = validate_sequence(sequence, self.schema)
        self.assertTrue(any("finite difference" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
