from __future__ import annotations

import copy
import unittest
from datetime import datetime, timedelta

from context.ct1_h0_audit import audit_h0
from context.ct1_h1_sizing import CONSERVATIVE_SD, size_h1
from context.fixtures.ct1_capture_template import build_capture_event


def build_h0_events(n: int = 10) -> list[dict]:
    base = build_capture_event(include_outcome=True)
    base_start = datetime.fromisoformat(base["time"]["start_time"])
    events: list[dict] = []
    for index in range(n):
        event = copy.deepcopy(base)
        start = base_start + timedelta(minutes=10 * index)
        end = start + timedelta(seconds=60)
        event["event_id"] = f"h0-{index:03d}"
        event["session_id"] = f"h0-session-{index // 5:02d}"
        event["episode_id"] = f"h0-episode-{index:03d}"
        event["time"]["start_time"] = start.isoformat()
        event["time"]["end_time"] = end.isoformat()
        event["observations"][0]["features"]["captured_at"] = start.isoformat()
        event["observations"][0]["observation_ref"] = f"h0-context-{index:03d}"
        event["observations"][0]["record_ids"] = [f"h0-context-record-{index:03d}"]
        event["hypotheses"][0]["evidence_refs"] = [f"h0-context-{index:03d}"]
        event["outcomes"][0]["outcome_id"] = f"h0-outcome-{index:03d}"
        event["outcomes"][0]["signalling_terminated"] = bool(index % 2)
        event["provenance"]["source_ids"] = [f"h0-source-{index:03d}"]
        event["observations"][0]["features"]["provenance"]["source_ids"] = [
            f"h0-context-source-{index:03d}"
        ]
        events.append(event)
    return events


class CT1PilotAuditTests(unittest.TestCase):
    def test_h0_audit_is_performance_blind(self) -> None:
        report = audit_h0(build_h0_events())
        self.assertFalse(report["performance_analysis_performed"])
        self.assertEqual(10, report["counts"]["strict_valid_events"])
        self.assertEqual(10, report["counts"]["labelled_termination_events"])
        self.assertAlmostEqual(0.5, report["outcome_instrumentation"]["termination_prevalence"])
        self.assertEqual(1.0, report["outcome_instrumentation"]["usable_label_rate"])
        self.assertTrue(report["readiness"]["h0_target_reached"])
        rendered = str(report).lower()
        self.assertNotIn("coefficient_", rendered)
        self.assertNotIn("held_out_score", rendered)

    def test_invalid_capture_is_reported_not_silently_dropped(self) -> None:
        events = build_h0_events()
        events[3]["observations"][0]["features"]["captured_at"] = (
            datetime.fromisoformat(events[3]["time"]["start_time"]) + timedelta(seconds=1)
        ).isoformat()
        report = audit_h0(events)
        self.assertEqual(9, report["counts"]["strict_valid_events"])
        self.assertEqual(1, report["counts"]["strict_invalid_events"])
        self.assertEqual("h0-003", report["strict_invalid_events"][0]["event_id"])
        self.assertTrue(report["strict_invalid_events"][0]["reasons"])

    def test_h1_sizing_uses_frozen_sd_grid_and_h0_yield_only(self) -> None:
        h0 = audit_h0(build_h0_events())
        sizing = size_h1(h0)
        self.assertFalse(sizing["performance_analysis_performed"])
        self.assertEqual([0.075, 0.1, 0.15], sizing["frozen_before_h0"]["paired_logloss_difference_sd_grid"])
        conservative = next(
            row
            for row in sizing["sensitivity_table"]
            if row["paired_logloss_difference_sd"] == CONSERVATIVE_SD
        )
        self.assertEqual(
            conservative["required_total_h1_strict_valid_episodes"],
            sizing["conservative_plan"]["required_total_h1_strict_valid_episodes"],
        )
        self.assertEqual(
            "exceeds_provisional_range_do_not_cap",
            sizing["conservative_plan"]["range_status"],
        )

    def test_positive_serial_dependence_inflates_required_h1(self) -> None:
        h0 = audit_h0(build_h0_events())
        independent = copy.deepcopy(h0)
        dependent = copy.deepcopy(h0)
        independent["outcome_instrumentation"]["planning_design_effect"] = 1.0
        dependent["outcome_instrumentation"]["planning_design_effect"] = 3.0
        n_independent = size_h1(independent)["conservative_plan"]["required_total_h1_strict_valid_episodes"]
        n_dependent = size_h1(dependent)["conservative_plan"]["required_total_h1_strict_valid_episodes"]
        self.assertGreater(n_dependent, n_independent)

    def test_missing_dependence_is_disclosed_not_invented(self) -> None:
        h0 = audit_h0(build_h0_events())
        h0["outcome_instrumentation"]["planning_design_effect"] = None
        h0["outcome_instrumentation"]["lag1_outcome_autocorrelation"] = None
        sizing = size_h1(h0)
        self.assertTrue(any("not estimable" in item for item in sizing["limitations"]))


if __name__ == "__main__":
    unittest.main()
