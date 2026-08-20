from __future__ import annotations

import argparse
import json
import math
from datetime import datetime
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "schemas" / "intent-event.schema.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def validate_instance(instance: dict, schema: dict | None = None) -> list[str]:
    schema = schema or _load(SCHEMA_PATH)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(instance), key=lambda error: list(error.absolute_path))
    rendered = []
    for error in errors:
        path = ".".join(str(part) for part in error.absolute_path) or "<root>"
        rendered.append(f"{path}: {error.message}")

    if rendered:
        return rendered

    time = instance["time"]
    if _parse_time(time["end_time"]) < _parse_time(time["start_time"]):
        rendered.append("time: end_time precedes start_time")
    if time["end_offset_ms"] < time["start_offset_ms"]:
        rendered.append("time: end_offset_ms precedes start_offset_ms")

    episode_end = time["end_offset_ms"]
    for observation in instance["observations"]:
        ref = observation["observation_ref"]
        if observation["end_offset_ms"] < observation["start_offset_ms"]:
            rendered.append(f"observations.{ref}: end_offset_ms precedes start_offset_ms")
        if observation["end_offset_ms"] > episode_end:
            rendered.append(f"observations.{ref}: interval exceeds episode end")

    hypothesis_ids = [hypothesis["hypothesis_id"] for hypothesis in instance["hypotheses"]]
    if len(set(hypothesis_ids)) != len(hypothesis_ids):
        rendered.append("hypotheses: hypothesis_id values must be unique")
    hypothesis_set = set(hypothesis_ids)

    for hypothesis in instance["hypotheses"]:
        probability = hypothesis["probability"]
        if not math.isfinite(probability):
            rendered.append(f"hypotheses.{hypothesis['hypothesis_id']}: probability must be finite")

    action_ids = [action["action_id"] for action in instance["human_actions"]]
    if len(set(action_ids)) != len(action_ids):
        rendered.append("human_actions: action_id values must be unique")
    action_set = set(action_ids)

    intervention_ids: set[str] = set()
    for intervention in instance["interventions"]:
        intervention_id = intervention["intervention_id"]
        if intervention_id in intervention_ids:
            rendered.append(f"interventions: duplicate intervention_id {intervention_id}")
        intervention_ids.add(intervention_id)

        if intervention["action_ref"] not in action_set:
            rendered.append(f"interventions.{intervention_id}: action_ref does not exist")

        candidate_set = set(intervention["candidate_hypotheses"])
        missing_candidates = candidate_set - hypothesis_set
        for hypothesis_id in sorted(missing_candidates):
            rendered.append(f"interventions.{intervention_id}: unknown candidate hypothesis {hypothesis_id}")

        prediction_refs = {prediction["hypothesis_ref"] for prediction in intervention["predictions"]}
        for hypothesis_id in sorted(prediction_refs - candidate_set):
            rendered.append(
                f"interventions.{intervention_id}: prediction {hypothesis_id} is not a candidate hypothesis"
            )
        for hypothesis_id in sorted(candidate_set - prediction_refs):
            rendered.append(
                f"interventions.{intervention_id}: candidate hypothesis {hypothesis_id} has no prediction"
            )

    outcome_ids: set[str] = set()
    for outcome in instance["outcomes"]:
        outcome_id = outcome["outcome_id"]
        if outcome_id in outcome_ids:
            rendered.append(f"outcomes: duplicate outcome_id {outcome_id}")
        outcome_ids.add(outcome_id)
        if outcome.get("end_offset_ms") is not None and outcome["end_offset_ms"] < outcome["start_offset_ms"]:
            rendered.append(f"outcomes.{outcome_id}: end_offset_ms precedes start_offset_ms")
        if outcome.get("end_offset_ms", outcome["start_offset_ms"]) > episode_end:
            rendered.append(f"outcomes.{outcome_id}: interval exceeds episode end")
        for field in ("supports_hypotheses", "contradicts_hypotheses"):
            for hypothesis_id in outcome.get(field, []):
                if hypothesis_id not in hypothesis_set:
                    rendered.append(f"outcomes.{outcome_id}: {field} references unknown hypothesis {hypothesis_id}")

    return rendered


def validate_path(instance_path: Path, schema_path: Path = SCHEMA_PATH) -> list[str]:
    return validate_instance(_load(instance_path), _load(schema_path))


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate a feline intent programme event")
    parser.add_argument("instance", type=Path)
    parser.add_argument("--schema", type=Path, default=SCHEMA_PATH)
    args = parser.parse_args()

    errors = validate_path(args.instance, args.schema)
    for error in errors:
        print(f"ERROR: {error}")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
