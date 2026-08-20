from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent
HTML = (ROOT / "capture_station" / "index.html").read_text(encoding="utf-8")
JS = (ROOT / "capture_station" / "app.js").read_text(encoding="utf-8")


class CaptureStationUIContractTests(unittest.TestCase):
    def test_ordinary_context_uses_structured_controls(self) -> None:
        for element_id in (
            "location",
            "door-state",
            "toy-present",
            "food-area-present",
            "human-count",
            "nearest-human-distance",
            "other-cat-count",
            "human-audio",
            "context-preview",
        ):
            self.assertIn(f'id="{element_id}"', HTML)
        self.assertNotIn('id="objects"', HTML)
        self.assertNotIn('id="social"', HTML)

    def test_advanced_json_is_optional_and_outside_ordinary_path(self) -> None:
        self.assertIn("<details>", HTML)
        self.assertIn("Advanced context (optional JSON)", HTML)
        self.assertIn('id="extra-objects"', HTML)
        self.assertIn('id="extra-social"', HTML)
        self.assertIn('id="environment"', HTML)
        self.assertIn("Ordinary H0 capture does not require editing them", HTML)

    def test_structured_controls_use_tokens_understood_by_frozen_ct1_extractor(self) -> None:
        for literal in (
            'object_id: "door-primary"',
            'object_type: "door"',
            'object_id: "toy-context"',
            'object_type: "toy"',
            'object_id: "food-area-context"',
            'object_type: "food_area"',
            'entity_type: "human"',
            'entity_type: "cat"',
        ):
            self.assertIn(literal, JS)
        self.assertIn("state.open = true", JS)
        self.assertIn("state.open = false", JS)

    def test_context_contract_shape_is_unchanged(self) -> None:
        match = re.search(r"function currentContext\(\) \{(?P<body>.*?)\n\}", JS, re.DOTALL)
        self.assertIsNotNone(match)
        body = match.group("body")
        for key in ("location:", "objects,", "social,", "environment,"):
            self.assertIn(key, body)
        self.assertIn('postJSON("/api/start"', JS)
        self.assertIn("context,", JS)

    def test_context_is_validated_before_start_and_start_button_tracks_validity(self) -> None:
        self.assertIn("let contextValid = false", JS)
        self.assertIn("Boolean(activeEvent) || !contextValid", JS)
        self.assertIn('throw new Error("Fix prediction-time context before starting an episode")', JS)
        self.assertIn("ensureUniqueIds(objects", JS)
        self.assertIn("ensureUniqueIds(social", JS)

    def test_browser_persistence_is_defaults_only(self) -> None:
        self.assertIn('const CONTEXT_DEFAULTS_KEY = "catpose.ct1.context-defaults.v1"', JS)
        match = re.search(
            r"function contextDefaultsPayload\(\) \{(?P<body>.*?)\n\}",
            JS,
            re.DOTALL,
        )
        self.assertIsNotNone(match)
        body = match.group("body").lower()
        for forbidden in (
            "event_id",
            "episode_id",
            "outcome",
            "terminated",
            "continued",
            "wav",
            "samples",
            "sha256",
            "hypothesis",
            "prediction",
            "model",
            "performance",
        ):
            self.assertNotIn(forbidden, body)
        self.assertIn("human_audio_may_be_present", body)
        self.assertIn("localStorage.setItem(CONTEXT_DEFAULTS_KEY", JS)

    def test_advanced_entries_are_appended_not_overwritten(self) -> None:
        self.assertIn("[...structuredObjects(), ...extraObjects]", JS)
        self.assertIn("[...structuredSocial(humanCount, nearestHumanDistance, otherCatCount), ...extraSocial]", JS)
        self.assertIn("duplicate ${key}", JS)

    def test_no_capture_timing_or_outcome_horizon_was_relaxed(self) -> None:
        self.assertIn("Math.round(audioContext.sampleRate * 5)", JS)
        self.assertIn("Math.max(0, 60000 - elapsed)", JS)
        self.assertIn("measuredOffsetMs >= config.sensor_cutoff_ms", JS)
        self.assertIn("setOutcomeEnabled(false)", JS)


if __name__ == "__main__":
    unittest.main()
