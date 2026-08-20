from __future__ import annotations

import argparse
import json
from pathlib import Path

from jsonschema import Draft202012Validator


def semantic_errors(plan: dict) -> list[str]:
    errors: list[str] = []

    recorded = plan["recorded_offset_ms"]
    action = plan["action"]
    action_offset = action["scheduled_offset_ms"]
    if recorded >= action_offset:
        errors.append("prospective plan must be recorded before the scheduled action")

    hypotheses = plan["hypotheses"]
    ids = [item["hypothesis_id"] for item in hypotheses]
    if len(set(ids)) != len(ids):
        errors.append("hypothesis_id values must be unique")

    probability_sum = sum(float(item["probability"]) for item in hypotheses)
    if abs(probability_sum - 1.0) > 1e-6:
        errors.append(f"hypothesis probabilities must sum to 1.0, got {probability_sum:.6f}")

    prediction_refs = [item["hypothesis_ref"] for item in plan["predictions"]]
    unknown_refs = sorted(set(prediction_refs) - set(ids))
    if unknown_refs:
        errors.append(f"prediction references unknown hypotheses: {unknown_refs}")
    missing_refs = sorted(set(ids) - set(prediction_refs))
    if missing_refs:
        errors.append(f"each hypothesis requires a prospective prediction: {missing_refs}")
    if len(prediction_refs) != len(set(prediction_refs)):
        errors.append("each hypothesis may have only one prediction block")

    action_type = action["action_type"]
    parameters = action.get("parameters", {})
    if action_type == "continue_due_feeding_routine" and parameters.get("feeding_due") is not True:
        errors.append("feeding action requires feeding_due=true")

    if action_type == "brief_no_action_observation":
        if parameters.get("necessary_care_pending") is not False:
            errors.append("no-action observation requires necessary_care_pending=false")
        duration = parameters.get("duration_ms")
        if not isinstance(duration, int) or duration <= 0 or duration > 10000:
            errors.append("no-action observation duration_ms must be an integer in 1..10000")

    phase = plan["phase"]
    policy = plan.get("selection_policy", "naturalistic")
    if policy == "expected_information_gain" and phase != "I1.2":
        errors.append("expected_information_gain is reserved for I1.2")
    if policy == "randomized_safe_set" and phase == "I1.0":
        errors.append("randomized_safe_set begins at I1.1")

    return errors


def validate(plan: dict, schema: dict) -> list[str]:
    validator = Draft202012Validator(schema)
    errors = [
        f"schema:{'.'.join(str(part) for part in error.absolute_path) or '<root>'}: {error.message}"
        for error in sorted(validator.iter_errors(plan), key=lambda item: list(item.absolute_path))
    ]
    if not errors:
        errors.extend(f"semantic:{message}" for message in semantic_errors(plan))
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate an I1 prospective intervention plan")
    parser.add_argument("plan", type=Path)
    parser.add_argument(
        "--schema",
        type=Path,
        default=Path(__file__).with_name("i1-plan.schema.json"),
    )
    args = parser.parse_args()
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    schema = json.loads(args.schema.read_text(encoding="utf-8"))
    errors = validate(plan, schema)
    for error in errors:
        print(f"ERROR: {error}")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
