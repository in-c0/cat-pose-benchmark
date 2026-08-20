from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from context.ct1_capture import SNAPSHOT_SCHEMA_REF


def build_capture_event(*, include_outcome: bool = False) -> dict[str, Any]:
    """Build a synthetic CT1.2 capture-ready event template.

    The payload demonstrates the timestamp/provenance contract only. It is not an
    animal observation and is not evidence about feline behaviour.
    """
    tz = timezone(timedelta(hours=10))
    started = datetime(2026, 8, 21, 7, 30, tzinfo=tz)
    ended = started + timedelta(seconds=60)

    context = {
        "location": "hallway",
        "objects": [
            {
                "object_id": "door-balcony",
                "object_type": "door",
                "state": {"open": False},
                "relation_to_subject": "subject-facing",
            }
        ],
        "social": [
            {
                "entity_id": "human-01",
                "entity_type": "human",
                "relationship": "household_member",
                "distance_m": 1.5,
            }
        ],
        "environment": {
            "capture_note": "synthetic example only",
        },
    }

    snapshot = {
        "snapshot_version": "0.1.0",
        "captured_at": started.isoformat(),
        "location": context["location"],
        "objects": context["objects"],
        "social": context["social"],
        "environment": context["environment"],
        "provenance": {
            "source_ids": ["synthetic-context-snapshot-001"],
            "capture_method": "synthetic",
            "annotation_source": "synthetic",
            "notes": "Replace with capture-time sensor/annotation provenance in naturalistic use.",
        },
        "uncertainty": {
            "location": "synthetic exact fixture",
        },
    }

    outcomes: list[dict[str, Any]] = []
    if include_outcome:
        outcomes.append(
            {
                "outcome_id": "out-template-termination",
                "outcome_type": "signalling_termination",
                "start_offset_ms": 30000,
                "end_offset_ms": 60000,
                "observation_source": "derived",
                "description": "Synthetic completed-example outcome.",
                "signalling_terminated": True,
            }
        )

    return {
        "schema_version": "0.1.0",
        "event_id": "ct1-capture-template-001",
        "subject_id": "synthetic-subject-template",
        "household_id": "synthetic-household-template",
        "session_id": "synthetic-session-template",
        "episode_id": "synthetic-episode-template",
        "time": {
            "start_time": started.isoformat(),
            "end_time": ended.isoformat(),
            "start_offset_ms": 0,
            "end_offset_ms": 60000,
            "clock_source": "synthetic-clock",
            "uncertainty_ms": 0,
        },
        "observations": [
            {
                "observation_ref": "ctx-snapshot-template",
                "modality": "object_environment",
                "schema_ref": SNAPSHOT_SCHEMA_REF,
                "record_ids": ["synthetic-context-snapshot-001"],
                "start_offset_ms": 0,
                "end_offset_ms": 0,
                "features": snapshot,
            }
        ],
        "context": context,
        "hypotheses": [
            {
                "hypothesis_id": "h-unknown",
                "kind": "unknown",
                "probability": 1.0,
                "source": "prior",
                "evidence_refs": ["ctx-snapshot-template"],
            }
        ],
        "human_actions": [],
        "interventions": [],
        "outcomes": outcomes,
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
        ] if not include_outcome else [
            "visual_pose",
            "visual_microstate",
            "audio_vocalisation",
            "audio_environment",
            "temporal_routine",
            "social_proxemic",
            "physiology",
            "human_input",
            "intervention",
        ],
        "provenance": {
            "source_ids": ["synthetic-context-snapshot-001"],
            "lineage": ["CT1.2 timestamped context capture template"],
            "annotation_source": "synthetic",
            "software_versions": {"template": "ct1.2-v0"},
        },
        "privacy": {
            "data_class": "synthetic",
            "consent_status": "not_applicable",
            "contains_human_audio": False,
            "contains_human_image": False,
        },
        "notes": "Synthetic capture template only; replace IDs/context with prospective observations.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Write the CT1.2 synthetic capture template")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--include-outcome", action="store_true")
    args = parser.parse_args()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(build_capture_event(include_outcome=args.include_outcome), indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"wrote CT1.2 capture template to {args.output}")


if __name__ == "__main__":
    main()
