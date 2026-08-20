from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

TIME_SINCE_SENTINEL = -1.0

ACTION_KEYWORDS = {
    "food": ("feed", "food", "meal"),
    "play": ("play", "toy"),
    "access": ("door", "access", "gate", "window"),
    "social": ("contact", "pet", "stroke", "call", "acknowledge", "social"),
}

OBJECT_KEYWORDS = {
    "door": ("door", "gate", "window", "access"),
    "toy": ("toy", "play"),
    "food_area": ("food", "feeder", "bowl", "meal", "kitchen"),
}


def _parse_iso(value: str) -> datetime:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError(f"timestamp must be offset-aware: {value}")
    return dt


def _event_start(event: dict[str, Any]) -> datetime:
    return _parse_iso(event["time"]["start_time"])


def _absolute_offset(event: dict[str, Any], offset_ms: int) -> datetime:
    return _event_start(event) + timedelta(milliseconds=offset_ms)


def _normalise_token(value: Any) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")


def _matches(value: Any, keywords: Iterable[str]) -> bool:
    token = _normalise_token(value)
    return any(keyword in token for keyword in keywords)


def _categorise_action(action_type: Any) -> str | None:
    for category, keywords in ACTION_KEYWORDS.items():
        if _matches(action_type, keywords):
            return category
    return None


def _categorise_object(item: dict[str, Any]) -> set[str]:
    haystack = f"{item.get('object_type', '')} {item.get('object_id', '')}"
    return {
        category
        for category, keywords in OBJECT_KEYWORDS.items()
        if _matches(haystack, keywords)
    }


def _termination_observation_before(
    event: dict[str, Any],
    cutoff: datetime | None = None,
) -> tuple[bool | None, datetime | None]:
    values: list[tuple[bool, datetime]] = []
    for outcome in event.get("outcomes", []):
        if outcome.get("outcome_type") != "signalling_termination":
            continue
        value = outcome.get("signalling_terminated")
        if not isinstance(value, bool):
            continue
        when = _absolute_offset(event, int(outcome["start_offset_ms"]))
        if cutoff is not None and when > cutoff:
            continue
        values.append((value, when))
    if not values:
        return None, None
    if any(value != values[0][0] for value, _ in values[1:]):
        raise ValueError(f"{event.get('event_id')}: contradictory signalling termination outcomes")
    return values[0][0], max(when for _, when in values)


def _termination_before(event: dict[str, Any], cutoff: datetime | None = None) -> bool | None:
    value, _ = _termination_observation_before(event, cutoff=cutoff)
    return value


def _context_features(event: dict[str, Any]) -> dict[str, Any]:
    context = event.get("context", {})
    objects = context.get("objects", [])
    social = context.get("social", [])

    feature: dict[str, Any] = {
        "location": context.get("location") or "__missing__",
        "n_objects": float(len(objects)),
        "n_humans_present": float(sum(item.get("entity_type") == "human" for item in social)),
        "n_other_cats_present": float(sum(item.get("entity_type") == "cat" for item in social)),
        "door_present": 0.0,
        "door_open": 0.0,
        "door_closed": 0.0,
        "toy_present": 0.0,
        "food_area_present": 0.0,
    }

    human_distances = [
        float(item["distance_m"])
        for item in social
        if item.get("entity_type") == "human" and isinstance(item.get("distance_m"), (int, float))
    ]
    feature["nearest_human_distance_m_missing"] = float(not human_distances)
    feature["nearest_human_distance_m"] = min(human_distances) if human_distances else TIME_SINCE_SENTINEL

    for item in objects:
        categories = _categorise_object(item)
        if "door" in categories:
            feature["door_present"] = 1.0
            state = item.get("state", {})
            if state.get("open") is True:
                feature["door_open"] = 1.0
            elif state.get("open") is False:
                feature["door_closed"] = 1.0
        if "toy" in categories:
            feature["toy_present"] = 1.0
        if "food_area" in categories:
            feature["food_area_present"] = 1.0

    return feature


def _history_features(event: dict[str, Any], history: list[dict[str, Any]]) -> tuple[dict[str, Any], list[str], datetime | None]:
    cutoff = _event_start(event)
    prior = [item for item in history if _event_start(item) < cutoff]
    prior.sort(key=_event_start)

    feature: dict[str, Any] = {}
    source_ids: set[str] = set()
    source_times: list[datetime] = []

    if prior:
        previous = prior[-1]
        previous_start = _event_start(previous)
        delta = (cutoff - previous_start).total_seconds()
        feature["time_since_previous_episode_s"] = delta
        feature["time_since_previous_episode_s_missing"] = 0.0
        feature["previous_location"] = previous.get("context", {}).get("location") or "__missing__"
        prev_termination, prev_termination_time = _termination_observation_before(previous, cutoff=cutoff)
        feature["previous_signalling_terminated_missing"] = float(prev_termination is None)
        feature["previous_signalling_terminated"] = (
            TIME_SINCE_SENTINEL if prev_termination is None else float(prev_termination)
        )
        source_ids.add(previous["event_id"])
        source_times.append(previous_start)
        if prev_termination_time is not None:
            source_times.append(prev_termination_time)
    else:
        feature["time_since_previous_episode_s"] = TIME_SINCE_SENTINEL
        feature["time_since_previous_episode_s_missing"] = 1.0
        feature["previous_location"] = "__missing__"
        feature["previous_signalling_terminated_missing"] = 1.0
        feature["previous_signalling_terminated"] = TIME_SINCE_SENTINEL

    feature["episodes_last_1h"] = float(sum((cutoff - _event_start(item)).total_seconds() <= 3600 for item in prior))
    feature["episodes_last_24h"] = float(sum((cutoff - _event_start(item)).total_seconds() <= 86400 for item in prior))

    for category in ACTION_KEYWORDS:
        candidates: list[tuple[datetime, str]] = []
        for item in prior:
            for action in item.get("human_actions", []):
                if _categorise_action(action.get("action_type")) != category:
                    continue
                when = _absolute_offset(item, int(action["offset_ms"]))
                if when <= cutoff:
                    candidates.append((when, item["event_id"]))
        key = f"time_since_{category}_action_s"
        if candidates:
            when, source_id = max(candidates, key=lambda pair: pair[0])
            feature[key] = (cutoff - when).total_seconds()
            feature[f"{key}_missing"] = 0.0
            source_ids.add(source_id)
            source_times.append(when)
        else:
            feature[key] = TIME_SINCE_SENTINEL
            feature[f"{key}_missing"] = 1.0

    max_source_time = max(source_times) if source_times else None
    return feature, sorted(source_ids), max_source_time


def extract_ct1_row(event: dict[str, Any], history: list[dict[str, Any]]) -> dict[str, Any]:
    prediction_time = _event_start(event)
    hour = prediction_time.hour + prediction_time.minute / 60.0 + prediction_time.second / 3600.0
    angle = 2.0 * math.pi * hour / 24.0

    features: dict[str, Any] = {
        "local_hour_sin": math.sin(angle),
        "local_hour_cos": math.cos(angle),
    }
    features.update(_context_features(event))
    history_features, source_ids, max_history_time = _history_features(event, history)
    features.update(history_features)

    if max_history_time is not None and max_history_time > prediction_time:
        raise AssertionError("CT1 history feature provenance exceeds prediction time")

    return {
        "event_id": event["event_id"],
        "subject_id": event["subject_id"],
        "household_id": event["household_id"],
        "session_id": event["session_id"],
        "episode_id": event["episode_id"],
        "prediction_time": prediction_time.isoformat(),
        "features": features,
        "target_signalling_terminated": _termination_before(event),
        "leakage_audit": {
            "history_source_event_ids": source_ids,
            "max_history_source_time": max_history_time.isoformat() if max_history_time else None,
            "excluded_current_episode_fields": [
                "observations",
                "human_actions",
                "interventions",
                "outcomes",
                "hypotheses",
                "context.routine",
            ],
            "context_contract": "top-level context is treated as a prediction-time snapshot",
        },
    }


def extract_ct1_rows(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ids = [event.get("event_id") for event in events]
    if len(ids) != len(set(ids)):
        raise ValueError("event_id values must be unique")

    ordered = sorted(events, key=_event_start)
    rows: list[dict[str, Any]] = []
    history: list[dict[str, Any]] = []
    for event in ordered:
        rows.append(extract_ct1_row(event, history))
        history.append(event)
    return rows


def validate_rows_temporal_integrity(rows: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    for row in rows:
        cutoff = _parse_iso(row["prediction_time"])
        source_time = row.get("leakage_audit", {}).get("max_history_source_time")
        if source_time is not None and _parse_iso(source_time) > cutoff:
            errors.append(f"{row['event_id']}: history source exceeds prediction time")
        excluded = set(row.get("leakage_audit", {}).get("excluded_current_episode_fields", []))
        required = {"human_actions", "interventions", "outcomes", "hypotheses", "context.routine"}
        if not required.issubset(excluded):
            errors.append(f"{row['event_id']}: leakage audit is missing excluded current-episode fields")
    return errors


def load_events(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("CT1 input must be a JSON array of intent-event objects")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Derive leakage-auditable CT1 context/routine rows")
    parser.add_argument("events", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    rows = extract_ct1_rows(load_events(args.events))
    errors = validate_rows_temporal_integrity(rows)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        raise SystemExit(1)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(rows, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {len(rows)} CT1 rows to {args.output}")


if __name__ == "__main__":
    main()
