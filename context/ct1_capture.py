from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from programme.validate_intent_event import validate_instance

SNAPSHOT_SCHEMA_REF = "context/ct1_context_snapshot.schema.json"
SNAPSHOT_SCHEMA_PATH = Path(__file__).with_name("ct1_context_snapshot.schema.json")


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _parse_time(value: str) -> datetime:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError(f"timestamp must be offset-aware: {value}")
    return dt


def _snapshot_observations(event: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        observation
        for observation in event.get("observations", [])
        if observation.get("modality") == "object_environment"
        and observation.get("schema_ref") == SNAPSHOT_SCHEMA_REF
    ]


def validate_capture_event(
    event: dict[str, Any],
    snapshot_schema: dict[str, Any] | None = None,
) -> list[str]:
    """Validate a prospective CT1 event and its timestamped prediction-time context."""
    errors = [f"intent-event: {error}" for error in validate_instance(event)]

    snapshots = _snapshot_observations(event)
    if len(snapshots) != 1:
        errors.append(
            f"context_snapshot: expected exactly one {SNAPSHOT_SCHEMA_REF} observation, found {len(snapshots)}"
        )
        return errors

    observation = snapshots[0]
    ref = observation.get("observation_ref", "<unknown>")
    if observation.get("start_offset_ms") != 0 or observation.get("end_offset_ms") != 0:
        errors.append(f"context_snapshot.{ref}: snapshot observation must be instantaneous at offset 0")

    features = observation.get("features")
    if not isinstance(features, dict):
        errors.append(f"context_snapshot.{ref}: features must contain the CT1 snapshot object")
        return errors

    schema = snapshot_schema or _load(SNAPSHOT_SCHEMA_PATH)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    for error in sorted(validator.iter_errors(features), key=lambda item: list(item.absolute_path)):
        path = ".".join(str(part) for part in error.absolute_path) or "<root>"
        errors.append(f"context_snapshot.{ref}.{path}: {error.message}")

    if errors:
        return errors

    try:
        event_start = _parse_time(event["time"]["start_time"])
        captured_at = _parse_time(features["captured_at"])
    except (KeyError, TypeError, ValueError) as exc:
        errors.append(f"context_snapshot.{ref}: invalid captured_at/start_time: {exc}")
        return errors

    if captured_at != event_start:
        errors.append(
            f"context_snapshot.{ref}: captured_at must equal event.time.start_time exactly"
        )

    event_context = event.get("context", {})
    for field in ("location", "objects", "social"):
        if event_context.get(field) != features.get(field):
            errors.append(
                f"context_snapshot.{ref}: snapshot {field} does not match top-level context.{field}"
            )

    event_environment = event_context.get("environment", {})
    if event_environment != features.get("environment", {}):
        errors.append(
            f"context_snapshot.{ref}: snapshot environment does not match top-level context.environment"
        )

    return errors


def context_snapshot(event: dict[str, Any]) -> dict[str, Any]:
    """Return the validated prediction-time context payload or raise ValueError."""
    errors = validate_capture_event(event)
    if errors:
        raise ValueError("; ".join(errors))
    observation = _snapshot_observations(event)[0]
    features = observation["features"]
    return {
        "location": features["location"],
        "objects": features["objects"],
        "social": features["social"],
        "environment": features.get("environment", {}),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate a timestamped CT1 prospective capture event")
    parser.add_argument("event", type=Path)
    args = parser.parse_args()

    payload = _load(args.event)
    events = payload if isinstance(payload, list) else [payload]
    all_errors: list[str] = []
    for event in events:
        event_id = event.get("event_id", "<unknown>")
        for error in validate_capture_event(event):
            all_errors.append(f"{event_id}: {error}")

    for error in all_errors:
        print(f"ERROR: {error}")
    raise SystemExit(1 if all_errors else 0)


if __name__ == "__main__":
    main()
