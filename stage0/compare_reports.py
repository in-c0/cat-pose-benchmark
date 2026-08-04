#!/usr/bin/env python3
"""Compare generated Stage 0 JSON reports with floating-point tolerance."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


def compare_values(
    expected: Any,
    actual: Any,
    *,
    path: str = "$",
    abs_tol: float = 1e-8,
    rel_tol: float = 1e-10,
) -> list[str]:
    errors: list[str] = []

    if isinstance(expected, bool) or isinstance(actual, bool):
        if expected is not actual:
            errors.append(f"{path}: expected {expected!r}, got {actual!r}")
        return errors

    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        if not math.isclose(
            float(expected),
            float(actual),
            rel_tol=rel_tol,
            abs_tol=abs_tol,
        ):
            errors.append(f"{path}: expected {expected!r}, got {actual!r}")
        return errors

    if type(expected) is not type(actual):
        errors.append(
            f"{path}: expected type {type(expected).__name__}, "
            f"got {type(actual).__name__}"
        )
        return errors

    if isinstance(expected, dict):
        expected_keys = set(expected)
        actual_keys = set(actual)
        for missing in sorted(expected_keys - actual_keys):
            errors.append(f"{path}: missing key {missing!r}")
        for extra in sorted(actual_keys - expected_keys):
            errors.append(f"{path}: unexpected key {extra!r}")
        for key in sorted(expected_keys & actual_keys):
            errors.extend(
                compare_values(
                    expected[key],
                    actual[key],
                    path=f"{path}.{key}",
                    abs_tol=abs_tol,
                    rel_tol=rel_tol,
                )
            )
        return errors

    if isinstance(expected, list):
        if len(expected) != len(actual):
            errors.append(
                f"{path}: expected list length {len(expected)}, got {len(actual)}"
            )
            return errors
        for index, (expected_item, actual_item) in enumerate(
            zip(expected, actual)
        ):
            errors.extend(
                compare_values(
                    expected_item,
                    actual_item,
                    path=f"{path}[{index}]",
                    abs_tol=abs_tol,
                    rel_tol=rel_tol,
                )
            )
        return errors

    if expected != actual:
        errors.append(f"{path}: expected {expected!r}, got {actual!r}")
    return errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("expected", type=Path)
    parser.add_argument("actual", type=Path)
    parser.add_argument("--abs-tol", type=float, default=1e-8)
    parser.add_argument("--rel-tol", type=float, default=1e-10)
    parser.add_argument("--max-errors", type=int, default=20)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    expected = json.loads(args.expected.read_text(encoding="utf-8"))
    actual = json.loads(args.actual.read_text(encoding="utf-8"))
    errors = compare_values(
        expected,
        actual,
        abs_tol=args.abs_tol,
        rel_tol=args.rel_tol,
    )

    if errors:
        print(
            f"Reports differ at {len(errors)} location(s); "
            f"showing up to {args.max_errors}:"
        )
        for error in errors[: args.max_errors]:
            print(f"- {error}")
        return 1

    print(
        "Reports match structurally and numerically "
        f"(abs_tol={args.abs_tol:g}, rel_tol={args.rel_tol:g})."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
