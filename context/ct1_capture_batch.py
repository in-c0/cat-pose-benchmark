from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from context.ct1_capture import validate_capture_event
from context.ct1_capture_cli import (
    LOCK_VERSION,
    action_log_fingerprint,
    default_lock_path,
    predictor_fingerprint,
)


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _canonical_hash(payload: Any) -> str:
    data = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def _parse_time(value: str) -> datetime:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError(f"timestamp must be timezone-aware: {value}")
    return dt


def discover_event_paths(directory: Path) -> list[Path]:
    paths: list[Path] = []
    for path in sorted(directory.rglob("*.json")):
        if path.name.endswith(".ct1-lock.json"):
            continue
        try:
            payload = _load_json(path)
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict) and payload.get("schema_version") == "0.1.0" and payload.get("event_id"):
            paths.append(path)
    return paths


def inspect_event(path: Path) -> dict[str, Any]:
    event = _load_json(path)
    if not isinstance(event, dict):
        raise ValueError(f"{path}: event file must contain one JSON object")

    lock_path = default_lock_path(path)
    problems: list[str] = []
    lock: dict[str, Any] | None = None
    if not lock_path.exists():
        problems.append("missing sidecar lock")
    else:
        candidate = _load_json(lock_path)
        if not isinstance(candidate, dict):
            problems.append("sidecar lock is not a JSON object")
        else:
            lock = candidate

    strict_errors = validate_capture_event(event)
    problems.extend(f"strict validation: {error}" for error in strict_errors)

    finalized = False
    integrity_ok = False
    if lock is not None:
        if lock.get("lock_version") != LOCK_VERSION:
            problems.append("unsupported lock version")
        if lock.get("event_id") != event.get("event_id"):
            problems.append("lock event_id mismatch")
        if lock.get("predictor_fingerprint_sha256") != predictor_fingerprint(event):
            problems.append("t0 predictor fingerprint mismatch")
        if lock.get("action_log_fingerprint_sha256") != action_log_fingerprint(event):
            problems.append("action log fingerprint mismatch")
        if lock.get("action_count") != len(event.get("human_actions", [])):
            problems.append("action count mismatch")
        finalized = lock.get("finalized") is True
        if finalized:
            expected_completed = lock.get("completed_event_sha256")
            if expected_completed != _canonical_hash(event):
                problems.append("completed event hash mismatch")
            if not event.get("outcomes"):
                problems.append("lock says finalized but event has no outcome")
        elif event.get("outcomes"):
            problems.append("event has outcome but lock is not finalized")
        integrity_ok = not problems

    outcome_state = "open"
    if finalized:
        outcomes = event.get("outcomes", [])
        if outcomes:
            outcome = outcomes[0]
            if outcome.get("outcome_type") == "signalling_termination":
                outcome_state = "terminated" if outcome.get("signalling_terminated") is True else "continued"
            elif outcome.get("outcome_type") == "unknown":
                outcome_state = "unknown"
            else:
                outcome_state = "other"

    start_time = event.get("time", {}).get("start_time")
    return {
        "event_id": event.get("event_id"),
        "path": str(path),
        "lock_path": str(lock_path),
        "start_time": start_time,
        "finalized": finalized,
        "outcome_state": outcome_state,
        "strict_valid": not strict_errors,
        "integrity_ok": integrity_ok,
        "problems": problems,
        "event_sha256": _canonical_hash(event),
        "event": event,
    }


def inspect_directory(directory: Path) -> dict[str, Any]:
    records = [inspect_event(path) for path in discover_event_paths(directory)]
    event_ids = [record["event_id"] for record in records]
    duplicate_ids = sorted({event_id for event_id in event_ids if event_ids.count(event_id) > 1})

    finalized = [record for record in records if record["finalized"]]
    ready = [record for record in finalized if record["strict_valid"] and record["integrity_ok"]]
    invalid = [record for record in records if not record["strict_valid"] or not record["integrity_ok"]]

    return {
        "protocol": "CT1.3-capture-batch-v0",
        "performance_analysis_performed": False,
        "directory": str(directory),
        "counts": {
            "event_files": len(records),
            "open_events": sum(not record["finalized"] for record in records),
            "finalized_events": len(finalized),
            "bundle_ready_events": len(ready),
            "invalid_or_tampered_events": len(invalid),
            "terminated": sum(record["outcome_state"] == "terminated" for record in ready),
            "continued": sum(record["outcome_state"] == "continued" for record in ready),
            "unknown": sum(record["outcome_state"] == "unknown" for record in ready),
        },
        "duplicate_event_ids": duplicate_ids,
        "h0_target": {
            "strict_valid_finalized_target": 10,
            "reached": len(ready) >= 10,
        },
        "records": [
            {key: value for key, value in record.items() if key != "event"}
            for record in records
        ],
    }


def bundle_ready_events(directory: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    paths = discover_event_paths(directory)
    records = [inspect_event(path) for path in paths]
    event_ids = [record["event_id"] for record in records]
    duplicates = sorted({event_id for event_id in event_ids if event_ids.count(event_id) > 1})
    if duplicates:
        raise ValueError(f"duplicate event_id values in capture directory: {duplicates}")

    invalid = [record for record in records if not record["strict_valid"] or not record["integrity_ok"]]
    if invalid:
        rendered = "; ".join(
            f"{record['event_id']}: {', '.join(record['problems'])}" for record in invalid
        )
        raise ValueError("capture directory contains invalid/tampered events: " + rendered)

    ready = [record for record in records if record["finalized"]]
    ready.sort(key=lambda record: _parse_time(record["start_time"]))
    events = [record["event"] for record in ready]
    manifest = {
        "protocol": "CT1.3-capture-bundle-v0",
        "performance_analysis_performed": False,
        "n_events": len(events),
        "event_ids": [event["event_id"] for event in events],
        "entries": [
            {
                "event_id": record["event_id"],
                "path": record["path"],
                "start_time": record["start_time"],
                "event_sha256": record["event_sha256"],
                "outcome_state": record["outcome_state"],
            }
            for record in ready
        ],
    }
    return events, manifest


def status_command(args: argparse.Namespace) -> None:
    report = inspect_directory(args.directory)
    if args.output:
        _write_json(args.output, report)
    print(json.dumps(report["counts"], indent=2, sort_keys=True))
    if report["duplicate_event_ids"]:
        print(f"duplicate event IDs: {report['duplicate_event_ids']}")
    for record in report["records"]:
        if record["problems"]:
            print(f"INVALID {record['event_id']}: {'; '.join(record['problems'])}")


def bundle_command(args: argparse.Namespace) -> None:
    events, manifest = bundle_ready_events(args.directory)
    _write_json(args.output, events)
    if args.manifest:
        _write_json(args.manifest, manifest)
    print(f"bundled {len(events)} finalized strict-valid events to {args.output}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Performance-blind status/bundle utilities for local CT1.3 captures"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    status = sub.add_parser("status", help="show integrity/readiness counts without model analysis")
    status.add_argument("--directory", type=Path, required=True)
    status.add_argument("--output", type=Path)
    status.set_defaults(func=status_command)

    bundle = sub.add_parser("bundle", help="assemble finalized strict-valid events for H0 audit")
    bundle.add_argument("--directory", type=Path, required=True)
    bundle.add_argument("--output", type=Path, required=True)
    bundle.add_argument("--manifest", type=Path)
    bundle.set_defaults(func=bundle_command)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
