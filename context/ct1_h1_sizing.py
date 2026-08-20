from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from statistics import NormalDist
from typing import Any

MIN_LOG_LOSS_IMPROVEMENT = 0.05
ALPHA_TWO_SIDED = 0.05
TARGET_POWER = 0.80
FINAL_TEST_FRACTION = 0.30
PAIRED_LOGLOSS_SD_GRID = (0.075, 0.10, 0.15)
CONSERVATIVE_SD = 0.15
PROVISIONAL_H1_RANGE = (40, 100)


def _required_iid_pairs(sd: float) -> int:
    normal = NormalDist()
    z_alpha = normal.inv_cdf(1.0 - ALPHA_TWO_SIDED / 2.0)
    z_power = normal.inv_cdf(TARGET_POWER)
    return int(math.ceil(((z_alpha + z_power) * sd / MIN_LOG_LOSS_IMPROVEMENT) ** 2))


def size_h1(h0_report: dict[str, Any]) -> dict[str, Any]:
    instrumentation = h0_report.get("outcome_instrumentation", {})
    label_rate = instrumentation.get("usable_label_rate")
    design_effect = instrumentation.get("planning_design_effect")

    if not isinstance(label_rate, (int, float)) or not (0 < float(label_rate) <= 1):
        raise ValueError("H0 usable_label_rate must be in (0, 1]")
    label_rate = float(label_rate)

    dependence_note: str | None = None
    if design_effect is None:
        design_effect = 1.0
        dependence_note = (
            "lag-1 dependence was not estimable; table shows no dependence inflation and cannot be described as dependence-adjusted"
        )
    elif isinstance(design_effect, (int, float)):
        design_effect = float(design_effect)
        if not math.isfinite(design_effect):
            raise ValueError("H0 planning_design_effect is not finite; extend/redesign instrumentation before H1 sizing")
        if design_effect < 1.0:
            raise ValueError("planning_design_effect must be >= 1")
    else:
        raise ValueError("H0 planning_design_effect must be numeric or null")

    table: list[dict[str, Any]] = []
    for sd in PAIRED_LOGLOSS_SD_GRID:
        iid_test = _required_iid_pairs(sd)
        dependence_adjusted_labelled_test = int(math.ceil(iid_test * design_effect))
        total_h1 = int(
            math.ceil(
                dependence_adjusted_labelled_test
                / (FINAL_TEST_FRACTION * label_rate)
            )
        )
        table.append(
            {
                "paired_logloss_difference_sd": sd,
                "required_iid_labelled_test_episodes": iid_test,
                "planning_design_effect": design_effect,
                "required_dependence_adjusted_labelled_test_episodes": dependence_adjusted_labelled_test,
                "usable_label_rate": label_rate,
                "final_test_fraction": FINAL_TEST_FRACTION,
                "required_total_h1_strict_valid_episodes": total_h1,
            }
        )

    conservative = next(
        row for row in table if row["paired_logloss_difference_sd"] == CONSERVATIVE_SD
    )
    required = int(conservative["required_total_h1_strict_valid_episodes"])
    low, high = PROVISIONAL_H1_RANGE
    if required < low:
        range_status = "below_provisional_range"
    elif required <= high:
        range_status = "within_provisional_range"
    else:
        range_status = "exceeds_provisional_range_do_not_cap"

    return {
        "protocol": "CT1.3-H1-sizing-v0",
        "performance_analysis_performed": False,
        "frozen_before_h0": {
            "minimum_practically_interesting_log_loss_improvement_nats": MIN_LOG_LOSS_IMPROVEMENT,
            "alpha_two_sided": ALPHA_TWO_SIDED,
            "target_power": TARGET_POWER,
            "final_test_fraction": FINAL_TEST_FRACTION,
            "paired_logloss_difference_sd_grid": list(PAIRED_LOGLOSS_SD_GRID),
            "conservative_planning_sd": CONSERVATIVE_SD,
            "provisional_h1_range": list(PROVISIONAL_H1_RANGE),
        },
        "h0_allowed_inputs_only": {
            "usable_label_rate": label_rate,
            "lag1_outcome_autocorrelation": instrumentation.get("lag1_outcome_autocorrelation"),
            "planning_design_effect": design_effect,
        },
        "sensitivity_table": table,
        "conservative_plan": {
            "required_total_h1_strict_valid_episodes": required,
            "range_status": range_status,
            "rule": (
                "Do not cap the calculated requirement at 100 and call it powered. "
                "If impractical, either declare a bounded cohort exploratory or prospectively redesign/extend collection before performance analysis."
            ),
        },
        "limitations": [
            note
            for note in (
                dependence_note,
                "Normal-approximation sensitivity calculation; final inference must still report chronological/block dependence and calibration limitations.",
                "The paired SD grid is fixed rather than estimated from H0 predictor performance.",
            )
            if note is not None
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compute CT1.3 H1 sample-size sensitivity from performance-blind H0 inputs"
    )
    parser.add_argument("h0_report", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    h0 = json.loads(args.h0_report.read_text(encoding="utf-8"))
    report = size_h1(h0)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote CT1.3 H1 sizing report to {args.output}")


if __name__ == "__main__":
    main()
