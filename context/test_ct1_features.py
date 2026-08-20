from __future__ import annotations

import copy
import unittest
from datetime import datetime, timedelta

from context.ct1_features import extract_ct1_row, extract_ct1_rows, validate_rows_temporal_integrity
try:
    from programme.validate_intent_event import validate_instance
except ModuleNotFoundError:  # Local isolated development copy; real repo CI has programme/.
    validate_instance = None
from context.fixtures.ct1_synthetic_events import build_events


def load_fixture() -> list[dict]:
    return build_events()


class CT1FeatureTests(unittest.TestCase):
    @unittest.skipIf(validate_instance is None, "shared programme validator unavailable in isolated local copy")
    def test_fixture_events_match_shared_event_contract(self) -> None:
        assert validate_instance is not None
        for event in load_fixture():
            with self.subTest(event_id=event["event_id"]):
                self.assertEqual([], validate_instance(event))

    def test_fixture_rows_are_temporally_valid(self) -> None:
        rows = extract_ct1_rows(load_fixture())
        self.assertEqual(18, len(rows))
        self.assertEqual([], validate_rows_temporal_integrity(rows))
        for row in rows:
            audit = row["leakage_audit"]
            self.assertIn("human_actions", audit["excluded_current_episode_fields"])
            self.assertIn("outcomes", audit["excluded_current_episode_fields"])

    def test_current_action_and_hypothesis_do_not_change_predictors(self) -> None:
        events = load_fixture()
        base = events[5]
        history = events[:5]
        changed = copy.deepcopy(base)
        changed["human_actions"] = [{
            "action_id": "post-cutoff-action",
            "action_type": "serve_meal",
            "offset_ms": 1,
            "parameters": {"future_only": True},
        }]
        changed["hypotheses"][0]["probability"] = 0.01
        changed["outcomes"][0]["signalling_terminated"] = not base["outcomes"][0]["signalling_terminated"]
        row_a = extract_ct1_row(base, history)
        row_b = extract_ct1_row(changed, history)
        self.assertEqual(row_a["features"], row_b["features"])
        self.assertNotEqual(row_a["target_signalling_terminated"], row_b["target_signalling_terminated"])

    def test_future_event_never_enters_history(self) -> None:
        events = load_fixture()
        target = events[5]
        row_with_future_supplied = extract_ct1_row(target, events[:5] + events[6:])
        row_without_future = extract_ct1_row(target, events[:5])
        self.assertEqual(row_without_future["features"], row_with_future_supplied["features"])
        self.assertEqual(
            row_without_future["leakage_audit"]["history_source_event_ids"],
            row_with_future_supplied["leakage_audit"]["history_source_event_ids"],
        )

    def test_overlapping_prior_action_after_cutoff_is_not_used(self) -> None:
        events = load_fixture()
        previous = copy.deepcopy(events[0])
        current = copy.deepcopy(events[1])

        current_start = datetime.fromisoformat(current["time"]["start_time"])
        previous_start = current_start - timedelta(seconds=10)
        previous["time"]["start_time"] = previous_start.isoformat()
        previous["time"]["end_time"] = (previous_start + timedelta(seconds=30)).isoformat()
        previous["time"]["end_offset_ms"] = 30000
        previous["human_actions"] = [{
            "action_id": "late-action",
            "action_type": "open_door",
            "offset_ms": 20000,
        }]
        previous["outcomes"][0]["start_offset_ms"] = 25000
        previous["outcomes"][0]["end_offset_ms"] = 30000

        row = extract_ct1_row(current, [previous])
        self.assertEqual(1.0, row["features"]["time_since_access_action_s_missing"])
        self.assertEqual(1.0, row["features"]["previous_signalling_terminated_missing"])

    def test_local_clock_uses_recorded_offset(self) -> None:
        events = load_fixture()
        row = extract_ct1_row(events[0], [])
        self.assertAlmostEqual(row["features"]["local_hour_sin"], 0.8660254, places=5)
        self.assertAlmostEqual(row["features"]["local_hour_cos"], -0.5, places=5)


if __name__ == "__main__":
    unittest.main()
