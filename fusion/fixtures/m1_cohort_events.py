from __future__ import annotations

import argparse
import copy
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from context.fixtures.ct1_capture_template import build_capture_event


def _shift_event(event: dict[str, Any], index: int, suffix: str) -> dict[str, Any]:
    event = copy.deepcopy(event)
    start = datetime.fromisoformat(event["time"]["start_time"]) + timedelta(minutes=5 * index)
    end = start + timedelta(seconds=60)
    event["event_id"] = f"m1-{suffix}-{index:02d}"
    event["episode_id"] = f"m1-episode-{suffix}-{index:02d}"
    event["session_id"] = f"m1-session-{index // 3:02d}"
    event["time"]["start_time"] = start.isoformat()
    event["time"]["end_time"] = end.isoformat()
    event["observations"][0]["features"]["captured_at"] = start.isoformat()
    event["observations"][0]["observation_ref"] = f"ctx-{suffix}-{index:02d}"
    event["observations"][0]["record_ids"] = [f"ctx-record-{suffix}-{index:02d}"]
    event["observations"][0]["features"]["provenance"]["source_ids"] = [
        f"ctx-source-{suffix}-{index:02d}"
    ]
    event["hypotheses"][0]["evidence_refs"] = [event["observations"][0]["observation_ref"]]
    event["provenance"]["source_ids"] = [f"event-source-{suffix}-{index:02d}"]
    return event


def _add_sensor(event: dict[str, Any], modality: str, *, end_offset_ms: int = 3000) -> None:
    token = "v1" if modality == "visual_pose" else "a1"
    ref = f"{token}:{event['event_id']}"
    event["observations"].append(
        {
            "observation_ref": ref,
            "modality": modality,
            "schema_ref": f"synthetic/{token}-fixture-v0",
            "record_ids": [f"synthetic-{token}-record:{event['event_id']}"],
            "start_offset_ms": 0,
            "end_offset_ms": end_offset_ms,
            "features": {"synthetic_fixture": True},
        }
    )
    event["missing_modalities"] = [
        item for item in event["missing_modalities"] if item != modality
    ]


def _complete(index: int, suffix: str, *, terminated: bool = True) -> dict[str, Any]:
    event = _shift_event(build_capture_event(include_outcome=True), index, suffix)
    outcome = event["outcomes"][0]
    outcome["outcome_id"] = f"outcome-{suffix}-{index:02d}"
    outcome["signalling_terminated"] = terminated
    if terminated:
        outcome["start_offset_ms"] = 30_000
        outcome["end_offset_ms"] = 30_000
    else:
        outcome["start_offset_ms"] = 60_000
        outcome["end_offset_ms"] = 60_000
    _add_sensor(event, "visual_pose")
    _add_sensor(event, "audio_vocalisation")
    return event


def build_events() -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []

    events.append(_complete(0, "complete-true", terminated=True))
    events.append(_complete(1, "complete-false", terminated=False))

    audio_missing = _complete(2, "audio-missing")
    audio_missing["observations"] = [
        obs for obs in audio_missing["observations"] if obs["modality"] != "audio_vocalisation"
    ]
    audio_missing["missing_modalities"] = sorted(
        set(audio_missing["missing_modalities"]) | {"audio_vocalisation"}
    )
    events.append(audio_missing)

    visual_missing = _complete(3, "visual-missing")
    visual_missing["observations"] = [
        obs for obs in visual_missing["observations"] if obs["modality"] != "visual_pose"
    ]
    visual_missing["missing_modalities"] = sorted(
        set(visual_missing["missing_modalities"]) | {"visual_pose"}
    )
    events.append(visual_missing)

    unknown_target = _complete(4, "unknown-target")
    unknown_target["outcomes"] = [
        {
            "outcome_id": "outcome-unknown-target-04",
            "outcome_type": "unknown",
            "start_offset_ms": 60_000,
            "end_offset_ms": 60_000,
            "observation_source": "human_annotation",
            "description": "Synthetic unknown target fixture.",
        }
    ]
    events.append(unknown_target)

    late_audio = _complete(5, "late-audio")
    for obs in late_audio["observations"]:
        if obs["modality"] == "audio_vocalisation":
            obs["start_offset_ms"] = 5_500
            obs["end_offset_ms"] = 6_000
    events.append(late_audio)

    conflict = _complete(6, "audio-conflict")
    conflict["missing_modalities"] = sorted(
        set(conflict["missing_modalities"]) | {"audio_vocalisation"}
    )
    events.append(conflict)

    return events


def main() -> None:
    parser = argparse.ArgumentParser(description="Write software-only M1.2 cohort fixture events")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(build_events(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {len(build_events())} synthetic M1.2 events to {args.output}")


if __name__ == "__main__":
    main()
