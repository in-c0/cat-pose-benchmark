from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any

from context.ct1_capture import SNAPSHOT_SCHEMA_REF, context_snapshot
from context.ct1_features import extract_ct1_row, extract_ct1_rows, load_events, validate_rows_temporal_integrity


def _strict_event(event: dict[str, Any]) -> dict[str, Any]:
    """Copy an event and replace untimestamped context with the validated t0 snapshot."""
    strict = copy.deepcopy(event)
    strict["context"] = context_snapshot(event)
    return strict


def _mark_strict_audit(row: dict[str, Any]) -> dict[str, Any]:
    row["leakage_audit"]["context_contract"] = "validated timestamped context snapshot at prediction cutoff"
    row["leakage_audit"]["context_source"] = "timestamped_object_environment_snapshot"
    row["leakage_audit"]["context_snapshot_schema"] = SNAPSHOT_SCHEMA_REF
    return row


def extract_strict_ct1_row(
    event: dict[str, Any],
    history: list[dict[str, Any]],
) -> dict[str, Any]:
    strict_event = _strict_event(event)
    strict_history = [_strict_event(item) for item in history]
    return _mark_strict_audit(extract_ct1_row(strict_event, strict_history))


def extract_strict_ct1_rows(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    strict_events = [_strict_event(event) for event in events]
    return [_mark_strict_audit(row) for row in extract_ct1_rows(strict_events)]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Derive CT1 rows using validated timestamped prospective context snapshots"
    )
    parser.add_argument("events", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    rows = extract_strict_ct1_rows(load_events(args.events))
    errors = validate_rows_temporal_integrity(rows)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        raise SystemExit(1)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(rows, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {len(rows)} strict CT1 rows to {args.output}")


if __name__ == "__main__":
    main()
