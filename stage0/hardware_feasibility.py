#!/usr/bin/env python3
"""Compute optical field of view, raw bandwidth, and budget feasibility."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


def field_of_view_degrees(sensor_mm: float, focal_length_mm: float) -> float:
    return math.degrees(2.0 * math.atan(sensor_mm / (2.0 * focal_length_mm)))


def span_at_distance(distance_m: float, fov_degrees: float) -> float:
    return 2.0 * distance_m * math.tan(math.radians(fov_degrees) / 2.0)


def raw_rate_bytes_per_second(width: int, height: int, fps: float, bits_per_pixel: int) -> float:
    return width * height * fps * bits_per_pixel / 8.0


def evaluate(config: dict[str, Any]) -> dict[str, Any]:
    reports: list[dict[str, Any]] = []
    for candidate in config["reference_candidates"]:
        width_px, height_px = [int(value) for value in candidate["resolution_px"]]
        sensor_width_mm, sensor_height_mm = [float(value) for value in candidate["sensor_size_mm"]]
        focal_length_mm = float(candidate["lens_focal_length_mm"])
        horizontal_fov = field_of_view_degrees(sensor_width_mm, focal_length_mm)
        vertical_fov = field_of_view_degrees(sensor_height_mm, focal_length_mm)
        distances = []
        for distance_m in candidate["working_distances_m"]:
            distances.append(
                {
                    "distance_m": float(distance_m),
                    "horizontal_span_m": span_at_distance(float(distance_m), horizontal_fov),
                    "vertical_span_m": span_at_distance(float(distance_m), vertical_fov),
                }
            )

        rates = {}
        for fps_name, fps in (
            ("target", float(candidate["target_frame_rate_hz"])),
            ("maximum", float(candidate["maximum_frame_rate_hz"])),
        ):
            byte_rate = raw_rate_bytes_per_second(width_px, height_px, fps, 8)
            rates[fps_name] = {
                "frame_rate_hz": fps,
                "raw_bayer8_mb_per_s": byte_rate / 1_000_000.0,
                "raw_bayer8_gb_per_min": byte_rate * 60.0 / 1_000_000_000.0,
            }

        reports.append(
            {
                "candidate_id": candidate["candidate_id"],
                "camera_examples": candidate["camera_examples"],
                "lens_focal_length_mm": focal_length_mm,
                "horizontal_fov_degrees": horizontal_fov,
                "vertical_fov_degrees": vertical_fov,
                "spans": distances,
                "data_rates": rates,
                "bytes_for_100_bayer8_frames": width_px * height_px * 100,
            }
        )

    evidence = config["budget_evidence_aud"]
    minimum_total = float(evidence["minimum_example_total_before_mounts_cables_and_full_size_mirrors"])
    budget = float(config["budget_aud"])
    return {
        "schema_version": "0.1.0",
        "budget_aud": budget,
        "minimum_reference_purchase_example_aud": minimum_total,
        "budget_multiple": minimum_total / budget,
        "purchase_feasible": minimum_total <= budget,
        "candidates": reports,
        "decision": config["decision"],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(__file__).with_name("hardware_candidates.json"),
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = evaluate(json.loads(args.config.read_text(encoding="utf-8")))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
