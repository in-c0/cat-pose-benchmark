from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def _episode_digest(ids: list[str]) -> str:
    return hashlib.sha256("\n".join(sorted(ids)).encode("utf-8")).hexdigest()


def build_report(*, request_advance: bool = True) -> dict[str, Any]:
    """Build a software-only M1 report fixture.

    Metric values are planted solely to exercise the guard. They are not feline
    evidence and must never be cited as experiment results.
    """
    episode_ids = [f"synthetic-eval-{index:03d}" for index in range(24)]
    episode_sha = _episode_digest(episode_ids)
    split_sha = "a" * 64
    target = {"name": "signalling_terminated", "horizon_seconds": 60}

    inputs = {
        "B0": ["context_routine"],
        "V": ["V1"],
        "A": ["A1"],
        "BV": ["context_routine", "V1"],
        "BA": ["context_routine", "A1"],
        "VA": ["V1", "A1"],
        "BVA": ["context_routine", "V1", "A1"],
        "BVA-V": ["context_routine", "A1"],
        "BVA-A": ["context_routine", "V1"],
    }
    metrics = {
        "B0": (0.690, 0.249, 0.060, 0.50, 0.49),
        "V": (0.670, 0.238, 0.055, 0.55, 0.54),
        "A": (0.675, 0.241, 0.058, 0.54, 0.53),
        "BV": (0.645, 0.225, 0.050, 0.59, 0.58),
        "BA": (0.650, 0.228, 0.052, 0.58, 0.57),
        "VA": (0.640, 0.222, 0.049, 0.60, 0.59),
        "BVA": (0.610, 0.205, 0.047, 0.64, 0.63),
        "BVA-V": (0.660, 0.233, 0.053, 0.57, 0.56),
        "BVA-A": (0.655, 0.230, 0.052, 0.58, 0.57),
    }

    rows: list[dict[str, Any]] = []
    for row_id in inputs:
        log_loss, brier, ece, ba, macro_f1 = metrics[row_id]
        row: dict[str, Any] = {
            "id": row_id,
            "mode": "dropout_stress" if row_id.startswith("BVA-") else "predictive",
            "available_inputs": inputs[row_id],
            "target": target,
            "outer_split_manifest_sha256": split_sha,
            "evaluation_episode_ids": episode_ids,
            "evaluation_episode_sha256": episode_sha,
            "metrics": {
                "log_loss": log_loss,
                "brier": brier,
                "ece": ece,
                "balanced_accuracy": ba,
                "macro_f1": macro_f1,
            },
        }
        if row_id == "BVA-V":
            row.update({"stress_of": "BVA", "dropped_modalities": ["V1"]})
        if row_id == "BVA-A":
            row.update({"stress_of": "BVA", "dropped_modalities": ["A1"]})
        rows.append(row)

    leakage = {
        name: {"status": "reported", "summary": "synthetic guard fixture"}
        for name in (
            "subject_identity",
            "household_owner",
            "time_routine",
            "location",
            "device_source",
            "modality_presence_missingness",
        )
    }
    missingness = {
        name: {"status": "reported", "summary": "synthetic guard fixture"}
        for name in (
            "complete_modality",
            "naturally_missing",
            "visual_dropout",
            "audio_dropout",
            "missingness_target_probe",
        )
    }

    advancement = {
        "requested": request_advance,
        "calibration_degradation_disclosed": False,
    }
    if request_advance:
        advancement["evidence"] = {
            "strongest_comparator_id": "VA",
            "delta_log_loss": 0.610 - 0.640,
            "uncertainty_supports_improvement": True,
        }

    return {
        "contract_version": "M1.1-v0",
        "synthetic_fixture": True,
        "target": target,
        "outer_split": {
            "manifest_sha256": split_sha,
            "claim_scope": "synthetic_cross_subject_guard_test",
        },
        "rows": rows,
        "leakage_probes": leakage,
        "missing_modality_diagnostics": missingness,
        "abstention": {
            "status": "not_applicable",
            "reason": "binary synthetic target fixture has no abstention analysis",
        },
        "uncertainty": {
            "supported": True,
            "resampling_unit": "subject",
            "method": "synthetic fixture only",
        },
        "advancement": advancement,
        "notes": "All values are planted software-test values; no animal observations are represented.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Write a synthetic M1 result-guard fixture")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--no-advance", action="store_true")
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(build_report(request_advance=not args.no_advance), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"wrote synthetic M1 report fixture to {args.output}")


if __name__ == "__main__":
    main()
