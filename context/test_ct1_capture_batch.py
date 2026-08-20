from __future__ import annotations

import copy
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from context.ct1_capture_batch import bundle_ready_events, inspect_directory
from context.ct1_capture_cli import build_lock, build_started_event, default_lock_path, finalize_event


CONTEXT = {
    "location": "hallway",
    "objects": [],
    "social": [],
    "environment": {"synthetic": True},
}


def make_event(index: int, *, finalized: bool = True, terminated: bool | None = True):
    event = build_started_event(
        context=CONTEXT,
        subject_id="cat-test",
        household_id="hh-test",
        session_id="session-test",
        event_id=f"batch-{index:03d}",
        started_at=datetime(2026, 8, 21, 8, 0, tzinfo=timezone.utc) + timedelta(minutes=index),
    )
    lock = build_lock(event)
    if finalized:
        event, lock = finalize_event(event, lock, terminated=terminated)
    return event, lock


def write_pair(directory: Path, event: dict, lock: dict) -> Path:
    path = directory / f"{event['event_id']}.json"
    path.write_text(json.dumps(event, indent=2) + "\n", encoding="utf-8")
    default_lock_path(path).write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")
    return path


class CT1CaptureBatchTests(unittest.TestCase):
    def test_status_counts_open_finalized_and_unknown_without_model_analysis(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            write_pair(directory, *make_event(0, finalized=True, terminated=True))
            write_pair(directory, *make_event(1, finalized=True, terminated=False))
            write_pair(directory, *make_event(2, finalized=True, terminated=None))
            write_pair(directory, *make_event(3, finalized=False))

            report = inspect_directory(directory)
            self.assertFalse(report["performance_analysis_performed"])
            self.assertEqual(4, report["counts"]["event_files"])
            self.assertEqual(3, report["counts"]["finalized_events"])
            self.assertEqual(3, report["counts"]["bundle_ready_events"])
            self.assertEqual(1, report["counts"]["open_events"])
            self.assertEqual(1, report["counts"]["terminated"])
            self.assertEqual(1, report["counts"]["continued"])
            self.assertEqual(1, report["counts"]["unknown"])
            rendered = json.dumps(report).lower()
            self.assertNotIn("coefficient", rendered)
            self.assertNotIn("feature_importance", rendered)
            self.assertNotIn("held_out_score", rendered)

    def test_bundle_is_chronological_and_ignores_valid_open_event(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            write_pair(directory, *make_event(2, finalized=True))
            write_pair(directory, *make_event(0, finalized=True))
            write_pair(directory, *make_event(1, finalized=False))

            events, manifest = bundle_ready_events(directory)
            self.assertEqual(["batch-000", "batch-002"], [event["event_id"] for event in events])
            self.assertEqual(2, manifest["n_events"])
            self.assertFalse(manifest["performance_analysis_performed"])

    def test_tampered_finalized_event_blocks_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            event, lock = make_event(0, finalized=True)
            path = write_pair(directory, event, lock)
            tampered = copy.deepcopy(event)
            tampered["context"]["location"] = "kitchen"
            path.write_text(json.dumps(tampered, indent=2) + "\n", encoding="utf-8")

            report = inspect_directory(directory)
            self.assertEqual(1, report["counts"]["invalid_or_tampered_events"])
            self.assertTrue(any("fingerprint mismatch" in item for item in report["records"][0]["problems"]))
            with self.assertRaisesRegex(ValueError, "invalid/tampered"):
                bundle_ready_events(directory)

    def test_missing_lock_is_reported_and_blocks_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            event, _ = make_event(0, finalized=True)
            path = directory / "orphan.json"
            path.write_text(json.dumps(event), encoding="utf-8")

            report = inspect_directory(directory)
            self.assertEqual(1, report["counts"]["invalid_or_tampered_events"])
            self.assertIn("missing sidecar lock", report["records"][0]["problems"])
            with self.assertRaisesRegex(ValueError, "invalid/tampered"):
                bundle_ready_events(directory)

    def test_duplicate_event_ids_block_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            event, lock = make_event(0, finalized=True)
            path_a = directory / "a.json"
            path_b = directory / "b.json"
            path_a.write_text(json.dumps(event), encoding="utf-8")
            path_b.write_text(json.dumps(event), encoding="utf-8")
            default_lock_path(path_a).write_text(json.dumps(lock), encoding="utf-8")
            default_lock_path(path_b).write_text(json.dumps(lock), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "duplicate event_id"):
                bundle_ready_events(directory)


if __name__ == "__main__":
    unittest.main()
