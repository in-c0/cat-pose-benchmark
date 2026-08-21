from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

SPEC_PATH = Path(__file__).with_name("id1_experiment_spec.json")


class ID1ValidationError(ValueError):
    pass


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_spec(path: Path = SPEC_PATH) -> dict[str, Any]:
    raw = _load_json(path)
    if not isinstance(raw, dict) or raw.get("spec_version") != "ID1.0":
        raise ID1ValidationError("expected ID1.0 experiment spec")
    return raw


def validate_run_manifest(manifest: dict[str, Any], spec: dict[str, Any]) -> None:
    required = {
        "run_id",
        "system_id",
        "upstream_commit",
        "sequence_id",
        "sequence_sha256",
        "ground_truth_sha256",
        "subject_ids",
        "stress_strata",
        "quantitative",
    }
    missing = sorted(required - set(manifest))
    if missing:
        raise ID1ValidationError(f"manifest missing fields: {', '.join(missing)}")

    if manifest["system_id"] != "remind_unmodified":
        raise ID1ValidationError("ID1.0 adapter accepts only the frozen unmodified REMIND baseline")

    expected_commit = spec["upstream"]["commit"]
    if manifest["upstream_commit"] != expected_commit:
        raise ID1ValidationError(
            f"upstream commit mismatch: expected {expected_commit}, got {manifest['upstream_commit']}"
        )

    for field in ("sequence_sha256", "ground_truth_sha256"):
        value = str(manifest[field])
        if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value.lower()):
            raise ID1ValidationError(f"{field} must be a SHA-256 hex digest")

    subject_ids = manifest["subject_ids"]
    if not isinstance(subject_ids, list) or not subject_ids or not all(
        isinstance(item, str) and item.strip() for item in subject_ids
    ):
        raise ID1ValidationError("subject_ids must be a non-empty list of pseudonymous IDs")

    strata = manifest["stress_strata"]
    if not isinstance(strata, list) or not strata:
        raise ID1ValidationError("stress_strata must be a non-empty list")
    unknown = sorted(set(strata) - set(spec["required_stress_strata"]))
    if unknown:
        raise ID1ValidationError(f"unknown stress strata: {', '.join(unknown)}")

    if not isinstance(manifest["quantitative"], bool):
        raise ID1ValidationError("quantitative must be boolean")
    if manifest["quantitative"] and not manifest.get("persistent_subject_ground_truth", False):
        raise ID1ValidationError("quantitative ID1 runs require persistent subject ground truth")


def read_summary_global(path: Path) -> dict[str, str]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != 1:
        raise ID1ValidationError(
            f"expected exactly one aggregate row in summary_global.csv, found {len(rows)}"
        )
    return {str(k): str(v) for k, v in rows[0].items() if k is not None}


def _parse_number(row: dict[str, str], key: str) -> float | int | None:
    raw = str(row.get(key, "") or "").strip()
    if raw == "":
        return None
    try:
        value = float(raw)
    except ValueError as exc:
        raise ID1ValidationError(f"metric {key} is not numeric: {raw!r}") from exc
    if value.is_integer() and key in {
        "idsw",
        "frag",
        "objects_recovered_reference",
    }:
        return int(value)
    return value


def build_result_packet(
    *,
    summary_global: Path,
    manifest_path: Path,
    spec_path: Path = SPEC_PATH,
) -> dict[str, Any]:
    spec = load_spec(spec_path)
    manifest = _load_json(manifest_path)
    if not isinstance(manifest, dict):
        raise ID1ValidationError("run manifest must be a JSON object")
    validate_run_manifest(manifest, spec)

    summary = read_summary_global(summary_global)
    required_metrics = list(spec["primary_metrics"])
    resource_metrics = list(spec["resource_metrics"])

    metrics: dict[str, float | int | None] = {}
    for key in required_metrics + resource_metrics:
        metrics[key] = _parse_number(summary, key)

    if manifest["quantitative"]:
        missing_metrics = [key for key in required_metrics if metrics[key] is None]
        if missing_metrics:
            raise ID1ValidationError(
                "quantitative run missing primary REMIND metrics: " + ", ".join(missing_metrics)
            )

    return {
        "schema_version": "ID1-result-v0",
        "spec_version": spec["spec_version"],
        "run_id": manifest["run_id"],
        "system_id": manifest["system_id"],
        "upstream": {
            "repository": spec["upstream"]["repository"],
            "commit": manifest["upstream_commit"],
        },
        "sequence": {
            "sequence_id": manifest["sequence_id"],
            "sequence_sha256": manifest["sequence_sha256"],
            "ground_truth_sha256": manifest["ground_truth_sha256"],
            "subject_ids": manifest["subject_ids"],
            "stress_strata": manifest["stress_strata"],
            "persistent_subject_ground_truth": bool(
                manifest.get("persistent_subject_ground_truth", False)
            ),
        },
        "quantitative": manifest["quantitative"],
        "metrics": metrics,
        "source_summary_global_sha256": _sha256(summary_global),
        "claims": {
            "identity_evaluation_performed": bool(manifest["quantitative"]),
            "intent_inference_performed": False,
            "translation_claim_performed": False,
            "health_or_welfare_inference_performed": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate a frozen ID1 REMIND run and emit a provenance-bound result packet."
    )
    parser.add_argument("--summary-global", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--spec", type=Path, default=SPEC_PATH)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    packet = build_result_packet(
        summary_global=args.summary_global,
        manifest_path=args.manifest,
        spec_path=args.spec,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(packet, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
