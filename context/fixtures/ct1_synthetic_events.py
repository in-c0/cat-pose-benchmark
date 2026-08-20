from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


def build_events(n_events: int = 18) -> list[dict[str, Any]]:
    """Build deterministic #18-shaped synthetic events.

    These records are software fixtures only. They are not animal observations and
    must not be interpreted as evidence about feline behaviour.
    """
    if n_events < 6:
        raise ValueError("CT1 synthetic fixture needs at least 6 events")

    tz = timezone(timedelta(hours=10))
    start = datetime(2026, 8, 1, 8, 0, tzinfo=tz)
    events: list[dict[str, Any]] = []

    for index in range(n_events):
        started = start + timedelta(minutes=20 * index)
        ended = started + timedelta(seconds=15)
        door_closed = index % 4 in (0, 1)
        location = "hallway" if index % 3 != 2 else "living_room"

        events.append(
            {
                "schema_version": "0.1.0",
                "event_id": f"ct1-syn-{index:03d}",
                "subject_id": "synthetic-subject-001",
                "household_id": "synthetic-household-001",
                "session_id": f"synthetic-session-{index // 10:02d}",
                "episode_id": f"synthetic-episode-{index:03d}",
                "time": {
                    "start_time": started.isoformat(),
                    "end_time": ended.isoformat(),
                    "start_offset_ms": 0,
                    "end_offset_ms": 15000,
                    "clock_source": "synthetic-clock",
                    "uncertainty_ms": 0,
                },
                "observations": [
                    {
                        "observation_ref": f"ctx-{index:03d}",
                        "modality": "object_environment",
                        "schema_ref": "context/ct1_feature_spec.json",
                        "record_ids": [f"ctx-record-{index:03d}"],
                        "start_offset_ms": 0,
                        "end_offset_ms": 0,
                        "features": {"synthetic_fixture": True},
                    }
                ],
                "context": {
                    "location": location,
                    "objects": [
                        {
                            "object_id": "door-a",
                            "object_type": "door",
                            "state": {"open": not door_closed},
                            "relation_to_subject": "synthetic",
                        }
                    ],
                    "social": [],
                },
                "hypotheses": [
                    {
                        "hypothesis_id": "h-unknown",
                        "kind": "unknown",
                        "probability": 1.0,
                        "source": "prior",
                        "evidence_refs": [f"ctx-{index:03d}"],
                    }
                ],
                "human_actions": [
                    {
                        "action_id": f"act-{index:03d}",
                        "action_type": "open_door" if door_closed else "acknowledge",
                        "offset_ms": 5000,
                        "actor_id": "synthetic-human",
                        "target_id": "door-a" if door_closed else "synthetic-subject-001",
                        "parameters": {"synthetic_fixture": True},
                    }
                ],
                "interventions": [],
                "outcomes": [
                    {
                        "outcome_id": f"out-{index:03d}",
                        "outcome_type": "signalling_termination",
                        "start_offset_ms": 10000,
                        "end_offset_ms": 15000,
                        "observation_source": "derived",
                        "description": "Synthetic CT1 fixture outcome; not an animal observation.",
                        "signalling_terminated": door_closed,
                    }
                ],
                "missing_modalities": [
                    "visual_pose",
                    "visual_microstate",
                    "audio_vocalisation",
                    "audio_environment",
                    "temporal_routine",
                    "social_proxemic",
                    "physiology",
                ],
                "provenance": {
                    "source_ids": [f"synthetic-source-{index:03d}"],
                    "lineage": ["CT1.1 deterministic non-animal synthetic fixture"],
                    "annotation_source": "synthetic",
                    "software_versions": {"fixture": "ct1.1-v0"},
                },
                "privacy": {
                    "data_class": "synthetic",
                    "consent_status": "not_applicable",
                    "contains_human_audio": False,
                    "contains_human_image": False,
                },
                "notes": "Synthetic software test only; not evidence about feline behaviour.",
            }
        )

    return events


def main() -> None:
    parser = argparse.ArgumentParser(description="Write the deterministic CT1 synthetic fixture")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--n-events", type=int, default=18)
    args = parser.parse_args()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(build_events(args.n_events), indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {args.n_events} synthetic CT1 events to {args.output}")


if __name__ == "__main__":
    main()
