#!/usr/bin/env python3
"""Validate a Stage 0 capture manifest and optionally verify referenced files."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _error_path(error: Any) -> str:
    return ".".join(str(part) for part in error.absolute_path) or "<root>"


def validate(
    manifest_path: Path,
    schema_path: Path,
    data_root: Path | None = None,
) -> list[str]:
    manifest: dict[str, Any] = json.loads(
        manifest_path.read_text(encoding="utf-8")
    )
    schema: dict[str, Any] = json.loads(schema_path.read_text(encoding="utf-8"))

    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = [
        f"{_error_path(error)}: {error.message}"
        for error in sorted(validator.iter_errors(manifest), key=_error_path)
    ]

    if data_root is None or errors:
        return errors

    for item in manifest["files"]:
        path = data_root / item["path"]
        if not path.is_file():
            errors.append(f"{item['path']}: referenced file does not exist")
            continue
        actual_size = path.stat().st_size
        if actual_size != item["byte_count"]:
            errors.append(
                f"{item['path']}: byte_count is {item['byte_count']}, actual is {actual_size}"
            )
        actual_digest = sha256(path)
        if actual_digest != item["sha256"]:
            errors.append(
                f"{item['path']}: sha256 is {item['sha256']}, actual is {actual_digest}"
            )

    return errors


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument(
        "--schema",
        type=Path,
        default=Path(__file__).parents[1]
        / "schemas"
        / "stage0-capture-manifest.schema.json",
    )
    parser.add_argument(
        "--data-root",
        type=Path,
        help="When set, verify file existence, byte counts, and SHA-256 digests.",
    )
    args = parser.parse_args()

    errors = validate(args.manifest, args.schema, args.data_root)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        raise SystemExit(1)
    print(f"Valid Stage 0 manifest: {args.manifest}")


if __name__ == "__main__":
    main()
