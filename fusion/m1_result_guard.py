from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

SPEC_PATH = Path(__file__).with_name("m1_ablation_spec.json")


def load_spec(path: Path = SPEC_PATH) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("M1 spec must be a JSON object")
    return payload


def _finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _episode_digest(ids: list[str]) -> str:
    payload = "\n".join(sorted(ids)).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _require_mapping(value: Any, name: str, errors: list[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        errors.append(f"{name} must be an object")
        return {}
    return value


def _row_map(report: dict[str, Any], errors: list[str]) -> dict[str, dict[str, Any]]:
    rows = report.get("rows")
    if not isinstance(rows, list):
        errors.append("rows must be an array")
        return {}
    result: dict[str, dict[str, Any]] = {}
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            errors.append(f"rows[{index}] must be an object")
            continue
        row_id = row.get("id")
        if not isinstance(row_id, str) or not row_id:
            errors.append(f"rows[{index}].id must be a non-empty string")
            continue
        if row_id in result:
            errors.append(f"duplicate ablation row id: {row_id}")
            continue
        result[row_id] = row
    return result


def validate_report(report: dict[str, Any], spec: dict[str, Any] | None = None) -> list[str]:
    spec = spec or load_spec()
    errors: list[str] = []

    if report.get("contract_version") != spec.get("spec_version"):
        errors.append(
            f"contract_version must equal {spec.get('spec_version')!r}"
        )

    target = _require_mapping(report.get("target"), "target", errors)
    frozen_target = spec["first_compatible_target"]
    if target.get("name") != frozen_target["name"]:
        errors.append(f"target.name must equal {frozen_target['name']!r}")
    if target.get("horizon_seconds") != frozen_target["horizon_seconds"]:
        errors.append(
            f"target.horizon_seconds must equal {frozen_target['horizon_seconds']}"
        )
    if target.get("name") == spec["claims_boundary"]["forbidden_primary_target"]:
        errors.append("human true_intent labels are forbidden as the primary M1 target")

    split = _require_mapping(report.get("outer_split"), "outer_split", errors)
    split_sha = split.get("manifest_sha256")
    if not isinstance(split_sha, str) or len(split_sha) < 16:
        errors.append("outer_split.manifest_sha256 must be a stable non-empty digest")
    if not isinstance(split.get("claim_scope"), str) or not split.get("claim_scope"):
        errors.append("outer_split.claim_scope must name the generalisation scope")

    rows = _row_map(report, errors)
    required_rows: dict[str, Any] = spec["required_rows"]
    missing_rows = sorted(set(required_rows) - set(rows))
    if missing_rows:
        errors.append(f"missing required ablation rows: {missing_rows}")

    required_metrics = spec["required_metrics"]
    report_target = (target.get("name"), target.get("horizon_seconds"))
    primary_episode_sets: dict[str, list[str]] = {}

    for row_id, expected in required_rows.items():
        row = rows.get(row_id)
        if row is None:
            continue

        if row.get("mode") != expected["mode"]:
            errors.append(f"{row_id}: mode must equal {expected['mode']!r}")
        actual_inputs = row.get("available_inputs")
        if not isinstance(actual_inputs, list) or sorted(actual_inputs) != sorted(expected["available_inputs"]):
            errors.append(
                f"{row_id}: available_inputs must equal {expected['available_inputs']}"
            )

        if expected["mode"] == "dropout_stress":
            if row.get("stress_of") != expected.get("stress_of"):
                errors.append(f"{row_id}: stress_of must equal {expected.get('stress_of')!r}")
            if sorted(row.get("dropped_modalities", [])) != sorted(expected.get("dropped_modalities", [])):
                errors.append(
                    f"{row_id}: dropped_modalities must equal {expected.get('dropped_modalities', [])}"
                )

        row_target = row.get("target", {})
        if not isinstance(row_target, dict):
            errors.append(f"{row_id}: target must be an object")
        elif (row_target.get("name"), row_target.get("horizon_seconds")) != report_target:
            errors.append(f"{row_id}: target/horizon differs from report-level frozen target")

        if row.get("outer_split_manifest_sha256") != split_sha:
            errors.append(f"{row_id}: outer split manifest differs from report-level split")

        episode_ids = row.get("evaluation_episode_ids")
        if not isinstance(episode_ids, list) or not episode_ids:
            errors.append(f"{row_id}: evaluation_episode_ids must be a non-empty array")
        elif not all(isinstance(item, str) and item for item in episode_ids):
            errors.append(f"{row_id}: evaluation_episode_ids must contain non-empty strings")
        elif len(episode_ids) != len(set(episode_ids)):
            errors.append(f"{row_id}: evaluation_episode_ids contain duplicates")
        else:
            declared_digest = row.get("evaluation_episode_sha256")
            actual_digest = _episode_digest(episode_ids)
            if declared_digest != actual_digest:
                errors.append(f"{row_id}: evaluation_episode_sha256 does not match episode IDs")
            if row_id in spec["primary_same_episode_rows"]:
                primary_episode_sets[row_id] = sorted(episode_ids)

        metrics = row.get("metrics")
        if not isinstance(metrics, dict):
            errors.append(f"{row_id}: metrics must be an object")
        else:
            for metric in required_metrics:
                if metric not in metrics:
                    errors.append(f"{row_id}: missing metric {metric}")
                elif not _finite_number(metrics[metric]):
                    errors.append(f"{row_id}: metric {metric} must be finite numeric")

    if primary_episode_sets:
        anchor_id = spec["primary_same_episode_rows"][0]
        anchor = primary_episode_sets.get(anchor_id)
        if anchor is not None:
            for row_id in spec["primary_same_episode_rows"][1:]:
                cohort = primary_episode_sets.get(row_id)
                if cohort is not None and cohort != anchor:
                    errors.append(
                        f"{row_id}: primary comparison cohort differs from {anchor_id}; exact same held-out episodes are required"
                    )

    bva = rows.get("BVA")
    if bva is not None and isinstance(bva.get("evaluation_episode_ids"), list):
        full_ids = sorted(bva["evaluation_episode_ids"])
        for stress_id in ("BVA-V", "BVA-A"):
            stress = rows.get(stress_id)
            if stress is not None and isinstance(stress.get("evaluation_episode_ids"), list):
                if sorted(stress["evaluation_episode_ids"]) != full_ids:
                    errors.append(f"{stress_id}: dropout stress must use the BVA evaluation cohort")

    leakage = _require_mapping(report.get("leakage_probes"), "leakage_probes", errors)
    for probe in spec["required_leakage_probes"]:
        item = leakage.get(probe)
        if not isinstance(item, dict):
            errors.append(f"missing leakage probe: {probe}")
            continue
        if item.get("status") not in {"reported", "unsupported"}:
            errors.append(f"leakage probe {probe}: status must be reported or unsupported")
        if item.get("status") == "unsupported" and not item.get("reason"):
            errors.append(f"leakage probe {probe}: unsupported status requires a reason")

    missingness = _require_mapping(
        report.get("missing_modality_diagnostics"),
        "missing_modality_diagnostics",
        errors,
    )
    for diagnostic in spec["required_missing_modality_diagnostics"]:
        item = missingness.get(diagnostic)
        if not isinstance(item, dict):
            errors.append(f"missing modality diagnostic: {diagnostic}")
            continue
        if item.get("status") not in {"reported", "not_present", "unsupported"}:
            errors.append(
                f"missing modality diagnostic {diagnostic}: invalid status"
            )
        if item.get("status") in {"not_present", "unsupported"} and not item.get("reason"):
            errors.append(
                f"missing modality diagnostic {diagnostic}: non-reported status requires a reason"
            )

    abstention = _require_mapping(report.get("abstention"), "abstention", errors)
    if abstention.get("status") not in {"reported", "not_applicable", "unsupported"}:
        errors.append("abstention.status must be reported, not_applicable, or unsupported")
    if abstention.get("status") == "reported" and abstention.get("threshold_frozen_before_test") is not True:
        errors.append("reported abstention analysis must freeze its threshold before test scoring")
    if abstention.get("status") in {"not_applicable", "unsupported"} and not abstention.get("reason"):
        errors.append("non-reported abstention status requires a reason")

    uncertainty = _require_mapping(report.get("uncertainty"), "uncertainty", errors)
    if uncertainty.get("supported") is True:
        if uncertainty.get("resampling_unit") not in spec["allowed_group_aware_resampling_units"]:
            errors.append(
                "supported uncertainty must name an allowed group-aware resampling_unit"
            )
    elif uncertainty.get("supported") is False:
        if not uncertainty.get("reason"):
            errors.append("unsupported uncertainty must state a reason")
    else:
        errors.append("uncertainty.supported must be boolean")

    advancement = _require_mapping(report.get("advancement"), "advancement", errors)
    if not isinstance(advancement.get("requested"), bool):
        errors.append("advancement.requested must be boolean")

    if advancement.get("requested") is True and not errors:
        errors.extend(_validate_advancement(report, rows, spec))

    return errors


def _validate_advancement(
    report: dict[str, Any],
    rows: dict[str, dict[str, Any]],
    spec: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    constituent_ids = ["B0", "V", "A", "BV", "BA", "VA"]
    if any(row_id not in rows for row_id in constituent_ids + ["BVA"]):
        return ["advancement cannot be evaluated until all primary ablations exist"]

    strongest_id = min(
        constituent_ids,
        key=lambda row_id: float(rows[row_id]["metrics"]["log_loss"]),
    )
    strongest_loss = float(rows[strongest_id]["metrics"]["log_loss"])
    bva_loss = float(rows["BVA"]["metrics"]["log_loss"])
    if not bva_loss < strongest_loss:
        errors.append(
            f"advancement denied: BVA log_loss {bva_loss:.6g} does not beat strongest constituent {strongest_id} ({strongest_loss:.6g})"
        )

    uncertainty = report["uncertainty"]
    if uncertainty.get("supported") is not True:
        errors.append("advancement denied: supported group-aware uncertainty is required")

    evidence = report["advancement"].get("evidence")
    if not isinstance(evidence, dict):
        errors.append("advancement.evidence must be an object when advancement is requested")
    else:
        if evidence.get("strongest_comparator_id") != strongest_id:
            errors.append(
                f"advancement evidence must name computed strongest comparator {strongest_id}"
            )
        declared_delta = evidence.get("delta_log_loss")
        expected_delta = bva_loss - strongest_loss
        if not _finite_number(declared_delta) or not math.isclose(
            float(declared_delta), expected_delta, rel_tol=1e-9, abs_tol=1e-12
        ):
            errors.append(
                "advancement.evidence.delta_log_loss must equal BVA minus strongest-comparator log loss"
            )
        if evidence.get("uncertainty_supports_improvement") is not True:
            errors.append(
                "advancement denied: evidence must state that preregistered group-aware uncertainty supports the improvement"
            )

    strongest_ece = float(rows[strongest_id]["metrics"]["ece"])
    bva_ece = float(rows["BVA"]["metrics"]["ece"])
    ece_degradation = bva_ece - strongest_ece
    threshold = float(spec["advancement"]["max_undisclosed_ece_degradation"])
    if ece_degradation > threshold and report["advancement"].get("calibration_degradation_disclosed") is not True:
        errors.append(
            "advancement denied: material ECE degradation exceeds the frozen disclosure threshold"
        )

    return errors


def validation_summary(report: dict[str, Any], spec: dict[str, Any] | None = None) -> dict[str, Any]:
    spec = spec or load_spec()
    errors = validate_report(report, spec)
    return {
        "contract_version": spec["spec_version"],
        "contract_valid": not errors,
        "advancement_requested": bool(report.get("advancement", {}).get("requested")) if isinstance(report.get("advancement"), dict) else False,
        "advancement_eligible": not errors and bool(report.get("advancement", {}).get("requested")),
        "errors": errors,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate a future M1 fusion result against the frozen ablation contract")
    parser.add_argument("report", type=Path)
    parser.add_argument("--summary", type=Path)
    args = parser.parse_args()

    report = json.loads(args.report.read_text(encoding="utf-8"))
    if not isinstance(report, dict):
        raise SystemExit("M1 report must be a JSON object")
    summary = validation_summary(report)
    rendered = json.dumps(summary, indent=2, sort_keys=True) + "\n"
    if args.summary:
        args.summary.parent.mkdir(parents=True, exist_ok=True)
        args.summary.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    if not summary["contract_valid"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
