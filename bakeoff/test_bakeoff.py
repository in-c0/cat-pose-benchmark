from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from bakeoff.adapters.mock import MockAdapter
from bakeoff.adapters.rtmpose_animal import AP10K_NAMES, canonical_keypoints
from bakeoff.evaluate import evaluate
from bakeoff.validate import validate


ROOT = Path(__file__).resolve().parents[1]


class BakeoffTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest_path = ROOT / "bakeoff" / "fixtures" / "mock-clip.json"
        self.requirements = json.loads(
            (ROOT / "bakeoff" / "feline-requirements.json").read_text(encoding="utf-8")
        )
        self.prediction = MockAdapter().predict_file(self.manifest_path)

    def test_mock_prediction_conforms_to_schema(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            prediction_path = Path(directory) / "prediction.json"
            prediction_path.write_text(json.dumps(self.prediction), encoding="utf-8")
            errors = validate(
                prediction_path,
                ROOT / "bakeoff" / "prediction.schema.json",
            )
            self.assertEqual(errors, [])

    def test_clip_manifest_conforms_to_schema(self) -> None:
        errors = validate(
            self.manifest_path,
            ROOT / "bakeoff" / "clip-manifest.schema.json",
        )
        self.assertEqual(errors, [])

    def test_metrics_surface_feline_topology_gap_and_recovery(self) -> None:
        result = evaluate(self.prediction, self.requirements, confidence=0.2)

        self.assertEqual(result["model_id"], "mock_model")
        self.assertEqual(result["two_d"]["native_keypoint_count"], 8)
        self.assertLess(result["two_d"]["coverage"], 1.0)
        self.assertEqual(
            result["two_d"]["dropout"]["left_front_paw"]["bounded_recoveries"],
            1,
        )
        self.assertEqual(result["feline_topology"]["ears"]["coverage"], 1.0)
        self.assertEqual(result["feline_topology"]["paws"]["coverage"], 1.0)
        self.assertAlmostEqual(result["feline_topology"]["tail"]["coverage"], 1 / 3)
        self.assertFalse(result["feline_topology"]["tail_curve_capability"]["satisfied"])

    def test_translation_motion_has_near_zero_second_difference(self) -> None:
        result = evaluate(self.prediction, self.requirements, confidence=0.2)
        value = result["two_d"]["mean_normalized_second_difference"]
        self.assertIsNotNone(value)
        self.assertLess(value, 1e-12)
        self.assertEqual(result["two_d"]["acceleration_spike_rate"], 0.0)

    def test_constant_3d_geometry_has_stable_bone_lengths(self) -> None:
        result = evaluate(self.prediction, self.requirements, confidence=0.2)
        for edge in result["three_d"]["bone_length_stability"].values():
            if edge["samples"] >= 2:
                self.assertLess(edge["coefficient_of_variation"], 1e-12)
        for pair in result["three_d"]["diagnostic_depth_flips"].values():
            self.assertEqual(pair["flips"], 0)

    def test_rtmpose_ap10k_mapping_exposes_feline_topology_gap(self) -> None:
        coordinates = [[float(index), float(index + 1)] for index in range(len(AP10K_NAMES))]
        scores = [0.9 for _ in AP10K_NAMES]
        scores[0] = 1.08  # Preserve native score scale; do not silently clamp.
        converted = canonical_keypoints(
            {"keypoints": coordinates, "keypoint_scores": scores}
        )
        by_native = {point["native_name"]: point for point in converted}

        self.assertEqual(len(converted), 17)
        self.assertEqual(by_native["tail_root"]["canonical_name"], "tail_base")
        self.assertEqual(by_native["left_back_paw"]["canonical_name"], "left_hind_paw")
        self.assertEqual(by_native["right_back_paw"]["canonical_name"], "right_hind_paw")
        self.assertEqual(by_native["left_eye"]["score"], 1.08)
        self.assertNotIn("left_ear_tip", {point["canonical_name"] for point in converted})
        self.assertNotIn("tail_tip", {point["canonical_name"] for point in converted})


if __name__ == "__main__":
    unittest.main()
