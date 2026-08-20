from __future__ import annotations

import argparse
import json
import math
import statistics
from datetime import datetime
from pathlib import Path
from typing import Any

from context.ct1_capture import validate_capture_event
from context.ct1_features import load_events
from context.ct1_strict_features import extract_strict_ct1_rows


FORBIDDEN_PERFORMANCE_OUTPUTS = [
    "model coefficients",
    "feature importance",
    "feature/target association",
    "classifier predictions",
    "held-out model scores",
    "audio incremental performance",
]


def _parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _lag1_binary(values: list[int]) -> float | None:
    if len(values) < 4:
        return None
    x = values[:-1]
    y = values[1:]
    if len(set(x)) < 2 or len(set(y)) < 2:
        return None
    mean_x = statistics.fmean(x)
    mean_y = statistics.fmean(y)
    numerator = sum((a - mean_x) * (b - mean_y) for a, b in zip(x, y))
    denom_x = sum((a - mean_x) ** 2 for a in x)
    denom_y = sum((b - mean_y) ** 2 for b in y)
    denominator = math.sqrt(denom_x * denom_y)
    if denominator <= 0:
        return None
    return float(numerator / denominator)


def _design_effect(rho: float | None) -> float | None:
    """AR(1)-style sensitivity adjustment using only positive observed dependence.

    Negative lag-1 correlation is not used to claim a sample-size discount. Very
    high positive dependence is returned as unsupported/infinite rather than capped.
    """
    if rho is None:
        return None
    planning_rho = max(0.0, rho)
    if planning_rho >= 0.95:
        return math.inf
    return float((1.0 + planning_rho) / (1.0 - planning_rho))


def _feature_missingness(rows: list[dict[str, Any]]) -> dict[str, float | None]:
    if not rows:
        return {}
    names = sorted(
        {
            key
            for row in rows
            for key in row.get("features", {})
            if key.endswith("_missing")
        }
    )
    result: dict[str, float | None] = {}
    for name in names:
        values = [row["features"].get(name) for row in rows]
        numeric = [float(value) for value in values if isinstance(value, (int, float))]
        result[name] = float(statistics.fmean(numeric)) if numeric else None

    locations = [row.get("features", {}).get("location") for row in rows]
    result["location_missing"] = float(
        sum(value in (None, "__missing__", "") for value in locations) / len(locations)
    )
    return result


def audit_h0(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Audit CT1.3 H0 instrumentation without fitting or scoring a predictor."""
    ordered = sorted(events, key=lambda event: _parse_time(event["time"]["start_time"]))
    invalid: list[dict[str, Any]] = []
    valid: list[dict[str, Any]] = []

    for event in ordered:
        errors = validate_capture_event(event)
        if errors:
            invalid.append(
                {
                    "event_id": event.get("event_id", "<unknown>"),
                    "reasons": errors,
                }
            )
        else:
            valid.append(event)

    rows = extract_strict_ct1_rows(valid) if valid else []
    labelled_rows = [
        row
        for row in rows
        if isinstance(row.get("target_signalling_terminated"), bool)
    ]
    outcomes = [int(row["target_signalling_terminated"]) for row in labelled_rows]

    starts = [_parse_time(event["time"]["start_time"]) for event in valid]
    intervals = [
        (current - previous).total_seconds()
        for previous, current in zip(starts, starts[1:])
    ]

    rho = _lag1_binary(outcomes)
    design_effect = _design_effect(rho)
    prevalence = float(statistics.fmean(outcomes)) if outcomes else None

    return {
        "protocol": "CT1.3-H0-v0",
        "audit_scope": "instrumentation_only_no_predictor_performance",
        "performance_analysis_performed": False,
        "forbidden_performance_outputs": FORBIDDEN_PERFORMANCE_OUTPUTS,
        "counts": {
            "events_received": len(events),
            "strict_valid_events": len(valid),
            "strict_invalid_events": len(invalid),
            "labelled_termination_events": len(labelled_rows),
            "unknown_or_missing_termination_events": len(rows) - len(labelled_rows),
        },
        "strict_invalid_events": invalid,
        "outcome_instrumentation": {
            "usable_label_rate": (
                len(labelled_rows) / len(rows) if rows else None
            ),
            "termination_prevalence": prevalence,
            "lag1_outcome_autocorrelation": rho,
            "planning_design_effect": design_effect,
            "design_effect_rule": "(1 + max(rho,0)) / (1 - max(rho,0)); unavailable if rho cannot be estimated; infinite if rho>=0.95",
        },
        "episode_timing": {
            "n_intervals": len(intervals),
            "median_inter_event_seconds": statistics.median(intervals) if intervals else None,
            "min_inter_event_seconds": min(intervals) if intervals else None,
            "max_inter_event_seconds": max(intervals) if intervals else None,
        },
        "feature_missingness": _feature_missingness(rows),
        "readiness": {
            "h0_target_strict_valid_events": 10,
            "h0_target_reached": len(valid) >= 10,
            "sizing_inputs_available": bool(rows and labelled_rows),
            "limitations": [
                message
                for condition, message in (
                    (len(valid) < 10, "fewer than 10 strict-valid H0 events"),
                    (not labelled_rows, "no observed termination labels"),
                    (rho is None, "lag-1 outcome dependence is not estimable from available labels"),
                    (design_effect is not None and math.isinf(design_effect), "outcome dependence is too high for finite AR(1)-style sizing"),
                )
                if condition
            ],
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit CT1.3 H0 instrumentation without predictor-performance analysis"
    )
    parser.add_argument("events", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    report = audit_h0(load_events(args.events))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote CT1.3 H0 audit to {args.output}")


if __name__ == "__main__":
    main()
