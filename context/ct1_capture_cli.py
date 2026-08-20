from __future__ import annotations

import argparse
import copy
import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from context.ct1_capture import SNAPSHOT_SCHEMA_REF, validate_capture_event

LOCK_VERSION = "CT1.3-capture-lock-v0"
CAPTURE_WINDOW_SECONDS = 60


def _iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        raise ValueError("capture timestamp must be timezone-aware")
    return dt.isoformat()


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _canonical_json(payload: Any) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _fingerprint_projection(event: dict[str, Any]) -> dict[str, Any]:
    """Fields frozen at t0 for CT1.3 capture integrity.

    Outcomes and `missing_modalities` are intentionally excluded because finalize
    appends the former and updates the latter. Everything that can affect current
    CT1 predictors or episode identity is frozen.
    """
    return {
        "schema_version": event["schema_version"],
        "event_id": event["event_id"],
        "subject_id": event["subject_id"],
        "household_id": event["household_id"],
        "session_id": event["session_id"],
        "episode_id": event["episode_id"],
        "time": event["time"],
        "observations": event["observations"],
        "context": event["context"],
        "hypotheses": event["hypotheses"],
        "human_actions": event["human_actions"],
        "interventions": event["interventions"],
        "provenance": event["provenance"],
        "privacy": event["privacy"],
        "notes": event.get("notes"),
    }


def predictor_fingerprint(event: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(_fingerprint_projection(event))).hexdigest()


def default_lock_path(event_path: Path) -> Path:
    return event_path.with_suffix(event_path.suffix + ".ct1-lock.json")


def _normalise_context(context: dict[str, Any]) -> dict[str, Any]:
    allowed = {"location", "objects", "social", "environment"}
    unknown = set(context) - allowed
    if unknown:
        raise ValueError(f"context input contains unsupported fields: {sorted(unknown)}")
    return {
        "location": context.get("location"),
        "objects": copy.deepcopy(context.get("objects", [])),
        "social": copy.deepcopy(context.get("social", [])),
        "environment": copy.deepcopy(context.get("environment", {})),
    }


def build_started_event(
    *,
    context: dict[str, Any],
    subject_id: str,
    household_id: str,
    session_id: str,
    event_id: str | None = None,
    started_at: datetime | None = None,
    clock_uncertainty_ms: float = 1000.0,
    consent_record_id: str | None = None,
) -> dict[str, Any]:
    started = started_at or datetime.now().astimezone()
    if started.tzinfo is None:
        raise ValueError("started_at must be timezone-aware")
    if clock_uncertainty_ms < 0:
        raise ValueError("clock_uncertainty_ms must be >= 0")

    event_id = event_id or f"ct1-{started.strftime('%Y%m%dT%H%M%S%z')}-{uuid.uuid4().hex[:8]}"
    episode_id = f"{event_id}-episode"
    source_id = f"manual-context:{event_id}"
    observation_ref = f"ctx:{event_id}"
    end = started + timedelta(seconds=CAPTURE_WINDOW_SECONDS)
    context_value = _normalise_context(context)

    snapshot = {
        "snapshot_version": "0.1.0",
        "captured_at": _iso(started),
        "location": context_value["location"],
        "objects": copy.deepcopy(context_value["objects"]),
        "social": copy.deepcopy(context_value["social"]),
        "environment": copy.deepcopy(context_value["environment"]),
        "provenance": {
            "source_ids": [source_id],
            "capture_method": "direct_observation",
            "annotation_source": "human_annotated",
            "notes": "CT1.3 manual structured context captured at episode start.",
        },
        "uncertainty": {
            "clock_uncertainty_ms": clock_uncertainty_ms,
        },
    }

    privacy: dict[str, Any] = {
        "data_class": "private_household",
        "consent_status": "recorded" if consent_record_id else "restricted",
        "contains_human_audio": False,
        "contains_human_image": False,
        "retention_policy": "CT1.3 local-first restricted household pilot",
    }
    if consent_record_id:
        privacy["consent_record_id"] = consent_record_id

    event = {
        "schema_version": "0.1.0",
        "event_id": event_id,
        "subject_id": subject_id,
        "household_id": household_id,
        "session_id": session_id,
        "episode_id": episode_id,
        "time": {
            "start_time": _iso(started),
            "end_time": _iso(end),
            "start_offset_ms": 0,
            "end_offset_ms": CAPTURE_WINDOW_SECONDS * 1000,
            "clock_source": "host-wall-clock",
            "uncertainty_ms": clock_uncertainty_ms,
        },
        "observations": [
            {
                "observation_ref": observation_ref,
                "modality": "object_environment",
                "schema_ref": SNAPSHOT_SCHEMA_REF,
                "record_ids": [source_id],
                "start_offset_ms": 0,
                "end_offset_ms": 0,
                "features": snapshot,
            }
        ],
        "context": context_value,
        "hypotheses": [
            {
                "hypothesis_id": "h-unknown",
                "kind": "unknown",
                "probability": 1.0,
                "source": "prior",
                "evidence_refs": [observation_ref],
            }
        ],
        "human_actions": [],
        "interventions": [],
        "outcomes": [],
        "missing_modalities": [
            "visual_pose",
            "visual_microstate",
            "audio_vocalisation",
            "audio_environment",
            "temporal_routine",
            "social_proxemic",
            "physiology",
            "human_input",
            "intervention",
            "outcome",
        ],
        "provenance": {
            "source_ids": [source_id],
            "lineage": ["CT1.3 local manual start/finalize capture"],
            "annotation_source": "human_annotated",
            "software_versions": {"ct1_capture_cli": LOCK_VERSION},
        },
        "privacy": privacy,
        "notes": "CT1.3 prospective naturalistic capture; no media recorded by this CLI.",
    }

    errors = validate_capture_event(event)
    if errors:
        raise ValueError("started event does not satisfy CT1.2 capture contract: " + "; ".join(errors))
    return event


def build_lock(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "lock_version": LOCK_VERSION,
        "event_id": event["event_id"],
        "created_at": event["time"]["start_time"],
        "capture_window_seconds": CAPTURE_WINDOW_SECONDS,
        "predictor_fingerprint_sha256": predictor_fingerprint(event),
        "frozen_fields": sorted(_fingerprint_projection(event)),
        "finalized": False,
    }


def verify_lock(event: dict[str, Any], lock: dict[str, Any]) -> None:
    if lock.get("lock_version") != LOCK_VERSION:
        raise ValueError("unsupported CT1 capture lock version")
    if lock.get("event_id") != event.get("event_id"):
        raise ValueError("lock event_id does not match event")
    expected = lock.get("predictor_fingerprint_sha256")
    actual = predictor_fingerprint(event)
    if expected != actual:
        raise ValueError("frozen t0 predictor fingerprint changed; refusing finalization")
    if lock.get("finalized") is True:
        raise ValueError("capture has already been finalized")


def finalize_event(
    event: dict[str, Any],
    lock: dict[str, Any],
    *,
    terminated: bool | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    verify_lock(event, lock)
    if event.get("outcomes"):
        raise ValueError("event already contains an outcome; refusing second finalization")

    completed = copy.deepcopy(event)
    if terminated is None:
        outcome = {
            "outcome_id": f"out:{event['event_id']}:termination-window",
            "outcome_type": "unknown",
            "start_offset_ms": CAPTURE_WINDOW_SECONDS * 1000,
            "end_offset_ms": CAPTURE_WINDOW_SECONDS * 1000,
            "observation_source": "human_annotation",
            "description": "Termination state was not reliably observable at the end of the frozen 60 s window.",
        }
    else:
        outcome = {
            "outcome_id": f"out:{event['event_id']}:termination-window",
            "outcome_type": "signalling_termination",
            "start_offset_ms": CAPTURE_WINDOW_SECONDS * 1000,
            "end_offset_ms": CAPTURE_WINDOW_SECONDS * 1000,
            "observation_source": "human_annotation",
            "description": (
                "Signalling had terminated by the end of the frozen 60 s window."
                if terminated
                else "Signalling had not terminated by the end of the frozen 60 s window."
            ),
            "signalling_terminated": terminated,
        }
    completed["outcomes"] = [outcome]
    completed["missing_modalities"] = [
        item for item in completed["missing_modalities"] if item != "outcome"
    ]

    # The current-event predictor projection must remain byte-for-byte equivalent.
    if predictor_fingerprint(completed) != lock["predictor_fingerprint_sha256"]:
        raise AssertionError("finalization altered frozen CT1 predictor fields")

    errors = validate_capture_event(completed)
    if errors:
        raise ValueError("completed event is invalid: " + "; ".join(errors))

    completed_lock = copy.deepcopy(lock)
    completed_lock["finalized"] = True
    completed_lock["outcome_state"] = (
        "unknown" if terminated is None else ("terminated" if terminated else "continued")
    )
    completed_lock["completed_event_sha256"] = hashlib.sha256(_canonical_json(completed)).hexdigest()
    return completed, completed_lock


def _load_context(path: Path) -> dict[str, Any]:
    payload = _load_json(path)
    if not isinstance(payload, dict):
        raise ValueError("context file must contain one JSON object")
    return payload


def _parse_outcome(value: str) -> bool | None:
    mapping: dict[str, bool | None] = {
        "terminated": True,
        "continued": False,
        "unknown": None,
    }
    return mapping[value]


def start_command(args: argparse.Namespace) -> None:
    event_path: Path = args.output
    lock_path = args.lock or default_lock_path(event_path)
    if event_path.exists() or lock_path.exists():
        raise FileExistsError("refusing to overwrite an existing event or lock file")

    event = build_started_event(
        context=_load_context(args.context),
        subject_id=args.subject_id,
        household_id=args.household_id,
        session_id=args.session_id,
        event_id=args.event_id,
        clock_uncertainty_ms=args.clock_uncertainty_ms,
        consent_record_id=args.consent_record_id,
    )
    lock = build_lock(event)
    _write_json(event_path, event)
    _write_json(lock_path, lock)
    print(f"started CT1.3 capture {event['event_id']}")
    print(f"event: {event_path}")
    print(f"lock:  {lock_path}")
    print("At the end of the frozen 60 s window, finalize as terminated, continued, or unknown.")


def finalize_command(args: argparse.Namespace) -> None:
    event_path: Path = args.event
    lock_path = args.lock or default_lock_path(event_path)
    event = _load_json(event_path)
    lock = _load_json(lock_path)
    if not isinstance(event, dict) or not isinstance(lock, dict):
        raise ValueError("event and lock files must contain JSON objects")

    completed, completed_lock = finalize_event(
        event,
        lock,
        terminated=_parse_outcome(args.outcome),
    )
    _write_json(event_path, completed)
    _write_json(lock_path, completed_lock)
    print(f"finalized CT1.3 capture {event['event_id']} as {args.outcome}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Start/finalize a local CT1.3 context-only naturalistic capture"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    start = sub.add_parser("start", help="freeze t0 context and open a 60 s episode")
    start.add_argument("--output", type=Path, required=True)
    start.add_argument("--lock", type=Path)
    start.add_argument("--context", type=Path, required=True)
    start.add_argument("--subject-id", required=True)
    start.add_argument("--household-id", required=True)
    start.add_argument("--session-id", required=True)
    start.add_argument("--event-id")
    start.add_argument("--clock-uncertainty-ms", type=float, default=1000.0)
    start.add_argument("--consent-record-id")
    start.set_defaults(func=start_command)

    finalize = sub.add_parser("finalize", help="append only the frozen-window outcome")
    finalize.add_argument("--event", type=Path, required=True)
    finalize.add_argument("--lock", type=Path)
    finalize.add_argument(
        "--outcome",
        choices=("terminated", "continued", "unknown"),
        required=True,
    )
    finalize.set_defaults(func=finalize_command)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
