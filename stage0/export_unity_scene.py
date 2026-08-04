#!/usr/bin/env python3
"""Export nominal Stage 0 geometry to a Unity JsonUtility-friendly scene file."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np

from stage0.geometry_sim import reflect_point, reflection_point


def vector(values: Any) -> list[float]:
    return [float(value) for value in values]


def export_scene(config: dict[str, Any], layout_name: str) -> dict[str, Any]:
    if layout_name not in config["layouts"]:
        raise ValueError(f"Unknown layout: {layout_name}")

    camera = config["camera"]
    layout = config["layouts"][layout_name]
    camera_centre = np.asarray(camera["centre_m"], dtype=float)
    representative_point = (
        np.asarray(config["capture_volume"]["min_m"], dtype=float)
        + np.asarray(config["capture_volume"]["max_m"], dtype=float)
    ) / 2.0

    mirrors: list[dict[str, Any]] = []
    cameras = [
        {
            "name": "physical",
            "kind": "physical",
            "position_m": vector(camera_centre),
            "look_at_m": vector(camera["look_at_m"]),
        }
    ]
    rays = [
        {
            "name": "direct-centre-ray",
            "kind": "direct",
            "points_m": [vector(camera_centre), vector(representative_point)],
        }
    ]

    for mirror in layout["mirrors"]:
        virtual_centre = reflect_point(
            camera_centre,
            mirror["plane_point_m"],
            mirror["plane_normal"],
        )
        reflected_point, amount = reflection_point(
            representative_point,
            camera_centre,
            mirror,
        )
        if not 0.0 < amount < 1.0:
            raise ValueError(
                f"Representative ray for {mirror['name']} does not cross the mirror."
            )

        mirrors.append(
            {
                "name": mirror["name"],
                "plane_point_m": vector(mirror["plane_point_m"]),
                "plane_normal": vector(mirror["plane_normal"]),
                "vertical_axis": vector(mirror["vertical_axis"]),
                "size_m": vector(mirror["size_m"]),
            }
        )
        cameras.append(
            {
                "name": f"virtual-{mirror['name']}",
                "kind": "virtual",
                "position_m": vector(virtual_centre),
                "look_at_m": vector(representative_point),
            }
        )
        rays.append(
            {
                "name": f"reflected-centre-ray-{mirror['name']}",
                "kind": "reflected",
                "points_m": [
                    vector(camera_centre),
                    vector(reflected_point),
                    vector(representative_point),
                ],
            }
        )

    return {
        "schema_version": "0.1.0",
        "source_layout_schema_version": config["schema_version"],
        "layout_name": layout_name,
        "units": "metres",
        "source_coordinate_convention": {
            "x": "portal left to right",
            "y": "camera through portal",
            "z": "up"
        },
        "unity_conversion": "unity_xyz = [source_x, source_z, source_y]",
        "capture_volume": {
            "min_m": vector(config["capture_volume"]["min_m"]),
            "max_m": vector(config["capture_volume"]["max_m"]),
        },
        "representative_point_m": vector(representative_point),
        "mirrors": mirrors,
        "cameras": cameras,
        "rays": rays,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(__file__).with_name("layouts.json"),
    )
    parser.add_argument("--layout", default="A_symmetric_lateral")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    config = json.loads(args.config.read_text(encoding="utf-8"))
    scene = export_scene(config, args.layout)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(scene, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(scene, indent=2))


if __name__ == "__main__":
    main()
