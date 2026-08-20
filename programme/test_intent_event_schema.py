from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from programme.validate_intent_event import SCHEMA_PATH, validate_instance

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples" / "intent-events"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class IntentEventSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schema = load_json(SCHEMA_PATH)
        Draft202012Validator.check_schema(cls.schema)
        cls.pose = load_json(EXAMPLES / "pose-only.json")
        cls.audio = load_json(EXAMPLES / "audio-only.json")
        cls.multimodal = load_json(EXAMPLES / "multimodal-intervention.json")

    def test_required_examples_validate(self) -> None:
        for name, instance in (
            ("pose-only", self.pose),
            ("audio-only", self.audio),
            ("multimodal-intervention", self.multimodal),
        ):
            with self.subTest(name=name):
                self.assertEqual([], validate_instance(instance, self.schema))

    def test_pose_example_references_v1_without_embedding_it(self) -> None:
        observation = self.pose["observations"][0]
        self.assertEqual("visual_pose", observation["modality"])
        self.assertEqual("schemas/observation.schema.json", observation["schema_ref"])
        self.assertNotIn("mean", observation)
        self.assertEqual("unknown", self.pose["hypotheses"][0]["kind"])

    def test_audio_only_does_not_require_visual_data(self) -> None:
        modalities = {item["modality"] for item in self.audio["observations"]}
        self.assertEqual({"audio_vocalisation"}, modalities)
        self.assertIn("visual_pose", self.audio["missing_modalities"])
        self.assertEqual([], validate_instance(self.audio, self.schema))

    def test_unknown_hypothesis_cannot_smuggle_in_human_label(self) -> None:
        instance = copy.deepcopy(self.pose)
        instance["hypotheses"][0]["label"] = "feed me"
        errors = validate_instance(instance, self.schema)
        self.assertTrue(any("hypotheses.0" in error for error in errors), errors)

    def test_intervention_requires_existing_action(self) -> None:
        instance = copy.deepcopy(self.multimodal)
        instance["interventions"][0]["action_ref"] = "missing-action"
        errors = validate_instance(instance, self.schema)
        self.assertIn("interventions.int-022: action_ref does not exist", errors)

    def test_candidate_hypotheses_require_predictions(self) -> None:
        instance = copy.deepcopy(self.multimodal)
        instance["interventions"][0]["predictions"] = instance["interventions"][0]["predictions"][:-1]
        errors = validate_instance(instance, self.schema)
        self.assertIn(
            "interventions.int-022: candidate hypothesis h-unknown has no prediction",
            errors,
        )

    def test_dangling_outcome_hypothesis_is_rejected(self) -> None:
        instance = copy.deepcopy(self.multimodal)
        instance["outcomes"][0]["supports_hypotheses"] = ["missing-hypothesis"]
        errors = validate_instance(instance, self.schema)
        self.assertIn(
            "outcomes.out-022-a: supports_hypotheses references unknown hypothesis missing-hypothesis",
            errors,
        )

    def test_duplicate_hypothesis_ids_are_rejected(self) -> None:
        instance = copy.deepcopy(self.audio)
        instance["hypotheses"][1]["hypothesis_id"] = instance["hypotheses"][0]["hypothesis_id"]
        errors = validate_instance(instance, self.schema)
        self.assertIn("hypotheses: hypothesis_id values must be unique", errors)


if __name__ == "__main__":
    unittest.main()
