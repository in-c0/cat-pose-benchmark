from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from intervention.validate_i1_plan import validate

ROOT = Path(__file__).resolve().parent
SCHEMA = json.loads((ROOT / "i1-plan.schema.json").read_text(encoding="utf-8"))
EXAMPLE = json.loads((ROOT / "examples" / "i1-plan-access-vs-social.json").read_text(encoding="utf-8"))


class I1PlanValidationTests(unittest.TestCase):
    def test_example_is_valid(self) -> None:
        self.assertEqual(validate(EXAMPLE, SCHEMA), [])

    def test_plan_must_precede_action(self) -> None:
        plan = copy.deepcopy(EXAMPLE)
        plan["recorded_offset_ms"] = plan["action"]["scheduled_offset_ms"]
        errors = validate(plan, SCHEMA)
        self.assertTrue(any("recorded before" in error for error in errors))

    def test_probabilities_must_sum_to_one(self) -> None:
        plan = copy.deepcopy(EXAMPLE)
        plan["hypotheses"][0]["probability"] = 0.2
        errors = validate(plan, SCHEMA)
        self.assertTrue(any("sum to 1.0" in error for error in errors))

    def test_food_action_requires_due_routine(self) -> None:
        plan = copy.deepcopy(EXAMPLE)
        plan["action"]["action_type"] = "continue_due_feeding_routine"
        plan["action"]["parameters"] = {"feeding_due": False}
        errors = validate(plan, SCHEMA)
        self.assertTrue(any("feeding_due=true" in error for error in errors))

    def test_information_gain_is_not_allowed_before_i1_2(self) -> None:
        plan = copy.deepcopy(EXAMPLE)
        plan["selection_policy"] = "expected_information_gain"
        errors = validate(plan, SCHEMA)
        self.assertTrue(any("reserved for I1.2" in error for error in errors))

    def test_no_action_cannot_delay_care_or_run_long(self) -> None:
        plan = copy.deepcopy(EXAMPLE)
        plan["action"]["action_type"] = "brief_no_action_observation"
        plan["action"]["parameters"] = {"necessary_care_pending": True, "duration_ms": 30000}
        errors = validate(plan, SCHEMA)
        self.assertTrue(any("necessary_care_pending=false" in error for error in errors))
        self.assertTrue(any("1..10000" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
