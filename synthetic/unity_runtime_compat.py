from __future__ import annotations

import argparse
import copy
import json
import re
from pathlib import Path
from typing import Any

from synthetic.unity_roundtrip import (
    DEFAULT_TOLERANCE,
    PINNED_UNITY_EDITOR_VERSION,
    RUNTIME_SOURCE_UNITY,
    build_report,
    compare_unity_export,
)

POLICY_VERSION = "S0B-unity-6.3-lts-compat-v0"
UNITY_6_3_FINAL_RE = re.compile(r"^6000\.3\.\d+f\d+$")


def is_compatible_unity_6_3_lts(value: Any) -> bool:
    return isinstance(value, str) and UNITY_6_3_FINAL_RE.fullmatch(value) is not None


def build_compatibility_report(
    payload: Any,
    *,
    tolerance: float = DEFAULT_TOLERANCE,
) -> dict[str, Any]:
    """Evaluate real Unity 6.3 LTS runtime compatibility without rewriting provenance.

    The underlying S0B comparator intentionally remains exact-pin strict for
    canonical reproduction. This policy layer answers a separate engineering
    question: did a real final-release Unity 6000.3.x Editor satisfy every
    non-version contract check?
    """
    canonical = build_report(
        payload,
        tolerance=tolerance,
        require_unity_runtime=True,
    )

    actual_version = payload.get("unity_editor_version") if isinstance(payload, dict) else None
    runtime_source = payload.get("runtime_source") if isinstance(payload, dict) else None
    same_lts_line = is_compatible_unity_6_3_lts(actual_version)
    canonical_version = actual_version == PINNED_UNITY_EDITOR_VERSION

    compatibility_mismatches: list[str]
    if not isinstance(payload, dict):
        compatibility_mismatches = ["<root>: Unity export must be a JSON object"]
    elif not same_lts_line:
        compatibility_mismatches = [
            "unity_editor_version: compatibility gate requires a final-release Unity 6000.3.x editor; "
            f"got {actual_version!r}"
        ]
    else:
        # Preserve the observed editor version in the report. The copy exists
        # only to reuse the exact-pin comparator for all non-version checks.
        normalised = copy.deepcopy(payload)
        normalised["unity_editor_version"] = PINNED_UNITY_EDITOR_VERSION
        compatibility_mismatches = compare_unity_export(
            normalised,
            tolerance=tolerance,
            require_unity_runtime=True,
        )

    compatible_runtime_verified = (
        same_lts_line
        and runtime_source == RUNTIME_SOURCE_UNITY
        and not compatibility_mismatches
    )
    canonical_pin_verified = (
        canonical_version
        and canonical.get("unity_runtime_verified") is True
    )

    if canonical_pin_verified:
        editor_status = "canonical_pin"
    elif compatible_runtime_verified:
        editor_status = "compatible_6000.3_lts_patch"
    else:
        editor_status = "not_verified"

    return {
        "policy_version": POLICY_VERSION,
        "roundtrip_version": canonical.get("roundtrip_version"),
        "actual_unity_editor_version": actual_version,
        "canonical_unity_editor_version": PINNED_UNITY_EDITOR_VERSION,
        "editor_status": editor_status,
        "canonical_pin_verified": canonical_pin_verified,
        "compatible_runtime_verified": compatible_runtime_verified,
        # Backwards-compatible aggregate: a real compatible Unity 6.3 LTS
        # runtime has executed and satisfied all non-version S0B checks.
        "unity_runtime_verified": compatible_runtime_verified,
        "canonical_contract_valid": canonical.get("contract_valid") is True,
        "compatibility_contract_valid": not compatibility_mismatches,
        "canonical_mismatch_count": canonical.get("mismatch_count"),
        "canonical_mismatches": canonical.get("mismatches", []),
        "compatibility_mismatch_count": len(compatibility_mismatches),
        "compatibility_mismatches": compatibility_mismatches,
        "performance_analysis_performed": False,
        "tolerance": tolerance,
        "claims_boundary": (
            "runtime compatibility verifies exporter/convention agreement only; "
            "it is not real-cat pose accuracy or behavioural evidence"
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate an S0B export under the documented Unity 6.3 LTS patch-compatibility policy"
        )
    )
    parser.add_argument("export", type=Path)
    parser.add_argument("--summary", type=Path)
    parser.add_argument("--tolerance", type=float, default=DEFAULT_TOLERANCE)
    parser.add_argument(
        "--require-canonical-pin",
        action="store_true",
        help="exit successfully only when the exact canonical Editor pin was executed",
    )
    args = parser.parse_args()

    payload = json.loads(args.export.read_text(encoding="utf-8"))
    report = build_compatibility_report(payload, tolerance=args.tolerance)
    rendered = json.dumps(report, indent=2, sort_keys=True)
    print(rendered)
    if args.summary:
        args.summary.parent.mkdir(parents=True, exist_ok=True)
        args.summary.write_text(rendered + "\n", encoding="utf-8")

    accepted = (
        report["canonical_pin_verified"]
        if args.require_canonical_pin
        else report["compatible_runtime_verified"]
    )
    if not accepted:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
