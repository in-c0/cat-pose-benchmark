#!/usr/bin/env python3
"""Probe a capture host's storage capacity and sustained sequential write rate.

The probe writes and deletes one temporary file in the selected directory. It does not
claim camera compatibility; it establishes whether the destination storage is plausibly
fast enough for the configured raw stream.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any


def windows_usb_controllers() -> list[dict[str, Any]] | None:
    if platform.system() != "Windows":
        return None
    command = [
        "powershell",
        "-NoProfile",
        "-Command",
        "Get-CimInstance Win32_USBController | "
        "Select-Object Name,Manufacturer,Status | ConvertTo-Json -Compress",
    ]
    try:
        result = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        )
        parsed = json.loads(result.stdout or "[]")
        return parsed if isinstance(parsed, list) else [parsed]
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        return []


def sequential_write_probe(directory: Path, size_mb: int, chunk_mb: int = 8) -> dict[str, Any]:
    directory.mkdir(parents=True, exist_ok=True)
    total_bytes = size_mb * 1024 * 1024
    chunk_bytes = min(chunk_mb * 1024 * 1024, total_bytes)
    payload = os.urandom(chunk_bytes)
    path: Path | None = None

    try:
        with tempfile.NamedTemporaryFile(
            prefix="catpose-write-probe-",
            suffix=".bin",
            dir=directory,
            delete=False,
        ) as stream:
            path = Path(stream.name)
            remaining = total_bytes
            started = time.perf_counter()
            while remaining > 0:
                block = payload if remaining >= len(payload) else payload[:remaining]
                stream.write(block)
                remaining -= len(block)
            stream.flush()
            os.fsync(stream.fileno())
            elapsed = time.perf_counter() - started

        return {
            "size_bytes": total_bytes,
            "elapsed_seconds": elapsed,
            "write_mb_per_s": total_bytes / elapsed / 1_000_000.0,
            "probe_file_deleted": True,
        }
    finally:
        if path is not None and path.exists():
            path.unlink()


def probe(directory: Path, size_mb: int) -> dict[str, Any]:
    usage = shutil.disk_usage(directory.resolve())
    return {
        "schema_version": "0.1.0",
        "captured_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "python": sys.version,
            "logical_cpu_count": os.cpu_count(),
        },
        "probe_directory": str(directory.resolve()),
        "storage": {
            "total_bytes": usage.total,
            "used_bytes": usage.used,
            "free_bytes": usage.free,
        },
        "usb_controllers": windows_usb_controllers(),
        "write_probe": sequential_write_probe(directory, size_mb),
        "reference_rates": {
            "1920x1200_bayer8_60fps_mb_per_s": 138.24,
            "1920x1200_bayer8_160fps_mb_per_s": 368.64,
            "recommended_headroom_multiplier": 1.5,
            "recommended_minimum_for_60fps_mb_per_s": 207.36,
            "recommended_minimum_for_160fps_mb_per_s": 552.96,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--probe-dir",
        type=Path,
        default=Path.cwd(),
        help="Directory on the intended capture drive.",
    )
    parser.add_argument(
        "--size-mb",
        type=int,
        default=512,
        help="Temporary sequential-write test size.",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    if args.size_mb < 16:
        parser.error("--size-mb must be at least 16")
    result = probe(args.probe_dir, args.size_mb)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
