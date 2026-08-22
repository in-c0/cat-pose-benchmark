#!/usr/bin/env python3
"""Export canonical Stage 0 data to Unity JsonUtility-friendly arrays."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np

from stage0.geometry_sim import reflect_point


def vector(values: list[float]) -> list[float]:
    return [float(value) for value in values]


def rounded_vector(values: list[float] | np.ndarray) -> list[float]:
    return [round(float(value), 9) for value in values]


def export_config(layouts: dict[str, Any], report: dict[str, Any]) -> dict[str, Any]:
    report_layouts = report["layouts"]
    camera = layouts["camera"]
    camera_centre = np.asarray(camera["centre_m"], dtype=float)

    exported_layouts: list[dict[str, Any]] = []
    for layout_id, layout in layouts["layouts"].items():
        report_layout = report_layouts[layout_id]
        mirrors: list[dict[str, Any]] = []
        for mirror in layout["mirrors"]:
            mirror_name = str(mirror["name"])
            virtual_centre = reflect_point(
                camera_centre,
                mirror["plane_point_m"],
                mirror["plane_normal"],
            )
            view_report = report_layout["views"][mirror_name]
            roi = view_report["roi_bounds_px"]
            mirrors.append(
                {
                    "name": mirror_name,
                    "sizeM": vector(mirror["size_m"]),
                    "planePointM": vector(mirror["plane_point_m"]),
                    "planeNormal": vector(mirror["plane_normal"]),
                    "verticalAxis": vector(mirror["vertical_axis"]),
                    "expectedVirtualCameraCentreM": rounded_vector(virtual_centre),
                    "reflectionParity": "mirrored",
                    "coverageFraction": float(view_report["coverage_fraction"]),
                    "roiMinPx": vector(roi["min_xy"]),
                    "roiMaxPx": vector(roi["max_xy"]),
                }
            )

        direct_report = report_layout["views"]["direct"]
        direct_roi = direct_report["roi_bounds_px"]
        combined = report_layout["subsets"]["direct+all_reflections"]
        exported_layouts.append(
            {
                "id": layout_id,
                "description": str(layout.get("description", "")),
                "nominalFrameM": vector(layout["nominal_frame_m"]),
                "directView": {
                    "name": "direct",
                    "reflectionParity": "direct",
                    "coverageFraction": float(
                        direct_report["coverage_fraction"]
                    ),
                    "roiMinPx": vector(direct_roi["min_xy"]),
                    "roiMaxPx": vector(direct_roi["max_xy"]),
                },
                "mirrors": mirrors,
                "combinedCoverageFraction": float(
                    combined["coverage_fraction"]
                ),
                "combinedP95RadialStandardDeviationMm": float(
                    combined["radial_standard_deviation_mm"]["p95"]
                ),
                "combinedP95Anisotropy": float(
                    combined["anisotropy_ratio"]["p95"]
                ),
            }
        )

    return {
        "schemaVersion": "0.1.0",
        "sourceLayoutSchemaVersion": str(layouts["schema_version"]),
        "sourceReportSchemaVersion": str(report["schema_version"]),
        "units": str(layouts["units"]),
        "repositoryCoordinateSystem": {
            "x": "portal left to right",
            "y": "camera through portal",
            "z": "up",
        },
        "repositoryToUnityAxisMap": ["+x", "+z", "+y"],
        "camera": {
            "className": str(camera["class"]),
            "resolutionPx": [int(value) for value in camera["resolution_px"]],
            "frameRateFps": int(camera["frame_rate_fps"]),
            "fxPx": float(camera["fx_px"]),
            "fyPx": float(camera["fy_px"]),
            "cxPx": float(camera["cx_px"]),
            "cyPx": float(camera["cy_px"]),
            "centreM": vector(camera["centre_m"]),
            "lookAtM": vector(camera["look_at_m"]),
            "pixelSigmaPx": float(camera["pixel_sigma_px"]),
        },
        "captureVolume": {
            "minM": vector(layouts["capture_volume"]["min_m"]),
            "maxM": vector(layouts["capture_volume"]["max_m"]),
            "samplesXyz": [
                int(value)
                for value in layouts["capture_volume"]["samples_xyz"]
            ],
        },
        "layouts": exported_layouts,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--layouts", type=Path, default=Path("stage0/layouts.json"))
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("stage0/geometry-conditioning-report.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "unity-viewer/Assets/StreamingAssets/CatPose/stage0-layouts.json"
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    layouts = json.loads(args.layouts.read_text(encoding="utf-8"))
    report = json.loads(args.report.read_text(encoding="utf-8"))
    exported = export_config(layouts, report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(exported, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
