from __future__ import annotations

import copy
import unittest

from context.ct1_features import extract_ct1_row
from context.fixtures.ct1_synthetic_events import build_events

try:
    from context.ct1_capture import context_snapshot, validate_capture_event
    from context.fixtures.ct1_capture_template import build_capture_event
except ModuleNotFoundError:  # Isolated local development copy; repository CI has programme/.
    context_snapshot = None
    validate_capture_event = None
    build_capture_event = None


@unittest.skipIf(validate_capture_event is None, "shared programme validator unavailable in isolated local copy")
class CT1CaptureTests(unittest.TestCase):
    def test_preoutcome_template_is_capture_ready(self) -> None:
        assert build_capture_event is not None
        assert validate_capture_event is not None
        event = build_capture_event(include_outcome=False)
        self.assertEqual([], validate_capture_event(event))

        row = extract_ct1_row(event, [], require_timestamped_context=True)
        self.assertEqual("timestamped_object_environment_snapshot", row["leakage_audit"]["context_source"])
        self.assertEqual("hallway", row["features"]["location"])
        self.assertIsNone(row["target_signalling_terminated"])

    def test_completed_template_keeps_outcome_label_only(self) -> None:
        assert build_capture_event is not None
        event = build_capture_event(include_outcome=False)
        completed = build_capture_event(include_outcome=True)

        row_before = extract_ct1_row(event, [], require_timestamped_context=True)
        row_after = extract_ct1_row(completed, [], require_timestamped_context=True)
        self.assertEqual(row_before["features"], row_after["features"])
        self.assertIsNone(row_before["target_signalling_terminated"])
        self.assertTrue(row_after["target_signalling_terminated"])

    def test_context_mismatch_is_rejected(self) -> None:
        assert build_capture_event is not None
        assert validate_capture_event is not None
        event = build_capture_event()
        event["context"]["location"] = "different-location"
        errors = validate_capture_event(event)
        self.assertTrue(any("does not match top-level context.location" in error for error in errors), errors)

    def test_post_cutoff_snapshot_offset_is_rejected(self) -> None:
        assert build_capture_event is not None
        assert validate_capture_event is not None
        event = build_capture_event()
        event["observations"][0]["start_offset_ms"] = 1
        event["observations"][0]["end_offset_ms"] = 1
        errors = validate_capture_event(event)
        self.assertTrue(any("instantaneous at offset 0" in error for error in errors), errors)

    def test_captured_at_must_equal_prediction_time(self) -> None:
        assert build_capture_event is not None
        assert validate_capture_event is not None
        event = build_capture_event()
        event["observations"][0]["features"]["captured_at"] = "2026-08-21T07:30:01+10:00"
        errors = validate_capture_event(event)
        self.assertTrue(any("captured_at must equal event.time.start_time exactly" in error for error in errors), errors)

    def test_duplicate_snapshot_is_rejected(self) -> None:
        assert build_capture_event is not None
        assert validate_capture_event is not None
        event = build_capture_event()
        duplicate = copy.deepcopy(event["observations"][0])
        duplicate["observation_ref"] = "ctx-snapshot-duplicate"
        duplicate["record_ids"] = ["synthetic-context-snapshot-duplicate"]
        event["observations"].append(duplicate)
        errors = validate_capture_event(event)
        self.assertTrue(any("expected exactly one" in error for error in errors), errors)

    def test_ct1_1_event_requires_snapshot_only_in_strict_mode(self) -> None:
        event = build_events()[0]
        relaxed = extract_ct1_row(event, [])
        self.assertEqual("top_level_context", relaxed["leakage_audit"]["context_source"])
        with self.assertRaises(ValueError):
            extract_ct1_row(event, [], require_timestamped_context=True)


if __name__ == "__main__":
    unittest.main()
