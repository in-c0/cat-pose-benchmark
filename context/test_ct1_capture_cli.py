from __future__ import annotations

import copy
import unittest
from datetime import datetime, timezone

from context.ct1_capture import validate_capture_event
from context.ct1_capture_cli import (
    build_lock,
    build_started_event,
    finalize_event,
    predictor_fingerprint,
)
from context.ct1_strict_features import extract_strict_ct1_rows


SYNTHETIC_CONTEXT = {
    "location": "hallway",
    "objects": [
        {
            "object_id": "door-example",
            "object_type": "door",
            "state": {"open": False},
            "relation_to_subject": "subject-facing",
        }
    ],
    "social": [
        {
            "entity_id": "human-example",
            "entity_type": "human",
            "relationship": "household_member",
            "distance_m": 1.5,
        }
    ],
    "environment": {"synthetic": True},
}


def build_started():
    return build_started_event(
        context=SYNTHETIC_CONTEXT,
        subject_id="cat-test",
        household_id="hh-test",
        session_id="session-test",
        event_id="ct1-cli-test",
        started_at=datetime(2026, 8, 21, 8, 0, tzinfo=timezone.utc),
        clock_uncertainty_ms=10,
    )


class CT1CaptureCLITests(unittest.TestCase):
    def test_start_event_is_strict_capture_valid(self) -> None:
        event = build_started()
        self.assertEqual([], validate_capture_event(event))
        self.assertEqual([], event["outcomes"])
        self.assertIn("outcome", event["missing_modalities"])
        self.assertEqual("private_household", event["privacy"]["data_class"])
        self.assertEqual("restricted", event["privacy"]["consent_status"])

    def test_finalize_terminated_changes_only_outcome_side(self) -> None:
        event = build_started()
        lock = build_lock(event)
        before = predictor_fingerprint(event)
        completed, completed_lock = finalize_event(event, lock, terminated=True)
        after = predictor_fingerprint(completed)

        self.assertEqual(before, after)
        self.assertTrue(completed_lock["finalized"])
        self.assertEqual("terminated", completed_lock["outcome_state"])
        self.assertNotIn("outcome", completed["missing_modalities"])
        self.assertTrue(completed["outcomes"][0]["signalling_terminated"])
        self.assertEqual([], validate_capture_event(completed))

    def test_finalize_continued_produces_false_label(self) -> None:
        event = build_started()
        completed, _ = finalize_event(event, build_lock(event), terminated=False)
        rows = extract_strict_ct1_rows([completed])
        self.assertFalse(rows[0]["target_signalling_terminated"])

    def test_finalize_unknown_preserves_unlabelled_target(self) -> None:
        event = build_started()
        completed, _ = finalize_event(event, build_lock(event), terminated=None)
        rows = extract_strict_ct1_rows([completed])
        self.assertIsNone(rows[0]["target_signalling_terminated"])
        self.assertEqual("unknown", completed["outcomes"][0]["outcome_type"])

    def test_tampered_context_refuses_finalization(self) -> None:
        event = build_started()
        lock = build_lock(event)
        tampered = copy.deepcopy(event)
        tampered["context"]["location"] = "kitchen"
        with self.assertRaisesRegex(ValueError, "fingerprint changed"):
            finalize_event(tampered, lock, terminated=True)

    def test_tampered_start_time_refuses_finalization(self) -> None:
        event = build_started()
        lock = build_lock(event)
        tampered = copy.deepcopy(event)
        tampered["time"]["start_time"] = "2026-08-21T08:00:01+00:00"
        with self.assertRaisesRegex(ValueError, "fingerprint changed"):
            finalize_event(tampered, lock, terminated=True)

    def test_second_finalization_is_rejected(self) -> None:
        event = build_started()
        lock = build_lock(event)
        completed, completed_lock = finalize_event(event, lock, terminated=True)
        with self.assertRaisesRegex(ValueError, "already been finalized"):
            finalize_event(completed, completed_lock, terminated=True)

    def test_explicit_consent_record_switches_status(self) -> None:
        event = build_started_event(
            context=SYNTHETIC_CONTEXT,
            subject_id="cat-test",
            household_id="hh-test",
            session_id="session-test",
            event_id="ct1-cli-consent-test",
            started_at=datetime(2026, 8, 21, 8, 0, tzinfo=timezone.utc),
            consent_record_id="consent-record-test",
        )
        self.assertEqual("recorded", event["privacy"]["consent_status"])
        self.assertEqual("consent-record-test", event["privacy"]["consent_record_id"])


if __name__ == "__main__":
    unittest.main()
