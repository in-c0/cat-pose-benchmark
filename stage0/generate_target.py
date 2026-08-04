#!/usr/bin/env python3
"""Generate printable ChArUco panels and nominal 3D target coordinates.

Generated coordinates are construction coordinates, not measured physical truth. After
assembly, the target must be independently measured before holdout points are used.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image


def load_spec(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def aruco_dictionary(name: str):
    try:
        dictionary_id = getattr(cv2.aruco, name)
    except AttributeError as error:
        raise ValueError(f"Unknown OpenCV ArUco dictionary: {name}") from error
    return cv2.aruco.getPredefinedDictionary(dictionary_id)


def create_board(face: dict[str, Any], dictionary):
    squares = tuple(int(value) for value in face["squares_xy"])
    square_length = float(face["square_length_m"])
    marker_length = float(face["marker_length_m"])
    prototype = cv2.aruco.CharucoBoard(squares, square_length, marker_length, dictionary)
    marker_count = len(np.asarray(prototype.getIds()).reshape(-1))
    marker_ids = np.arange(
        int(face["marker_id_offset"]),
        int(face["marker_id_offset"]) + marker_count,
        dtype=np.int32,
    )
    try:
        board = cv2.aruco.CharucoBoard(
            squares, square_length, marker_length, dictionary, marker_ids
        )
    except cv2.error:
        board = cv2.aruco.CharucoBoard(
            squares, square_length, marker_length, dictionary, marker_ids.reshape(-1, 1)
        )
    return board, marker_ids


def metres_to_pixels(length_m: float, dpi: int) -> int:
    return max(1, round(length_m / 0.0254 * dpi))


def save_board_png(board, face: dict[str, Any], output_path: Path, dpi: int, border_bits: int) -> tuple[int, int]:
    squares_x, squares_y = [int(value) for value in face["squares_xy"]]
    square_length = float(face["square_length_m"])
    size_px = (
        metres_to_pixels(squares_x * square_length, dpi),
        metres_to_pixels(squares_y * square_length, dpi),
    )
    image = board.generateImage(size_px, marginSize=0, borderBits=border_bits)
    Image.fromarray(image).save(output_path, dpi=(dpi, dpi))
    return size_px


def nominal_points(board, face: dict[str, Any], face_index: int) -> list[dict[str, Any]]:
    origin = np.asarray(face["origin_m"], dtype=float)
    axis_u = np.asarray(face["axis_u"], dtype=float)
    axis_v = np.asarray(face["axis_v"], dtype=float)
    points: list[dict[str, Any]] = []
    for local_id, local in enumerate(np.asarray(board.getChessboardCorners(), dtype=float)):
        global_id = face_index * 1000 + local_id
        remainder = global_id % 5
        partition = "calibration" if remainder in (0, 1, 2) else "validation" if remainder == 3 else "holdout"
        world = origin + axis_u * float(local[0]) + axis_v * float(local[1])
        points.append({
            "point_id": f"{face['name']}_corner_{local_id:03d}",
            "face": face["name"],
            "local_corner_id": local_id,
            "global_corner_index": global_id,
            "partition": partition,
            "nominal_position_m": world.tolist(),
            "truth_status": "construction_nominal_only",
        })
    return points


def generate(spec_path: Path, output_dir: Path, dpi_override: int | None) -> dict[str, Any]:
    spec = load_spec(spec_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    dictionary = aruco_dictionary(spec["fiducials"]["dictionary"])
    dpi = int(dpi_override or spec["fiducials"]["render_dpi"])
    border_bits = int(spec["fiducials"]["border_bits"])
    panels: list[dict[str, Any]] = []
    points: list[dict[str, Any]] = []
    all_marker_ids: list[int] = []

    for face_index, face in enumerate(spec["construction"]["faces"]):
        board, marker_ids = create_board(face, dictionary)
        output_name = f"{face['name']}.png"
        size_px = save_board_png(board, face, output_dir / output_name, dpi, border_bits)
        marker_id_list = [int(value) for value in marker_ids]
        all_marker_ids.extend(marker_id_list)
        panels.append({
            "face": face["name"],
            "file": output_name,
            "dpi": dpi,
            "pixel_size": list(size_px),
            "physical_size_m": [
                int(face["squares_xy"][0]) * float(face["square_length_m"]),
                int(face["squares_xy"][1]) * float(face["square_length_m"]),
            ],
            "marker_ids": marker_id_list,
        })
        points.extend(nominal_points(board, face, face_index))

    if len(all_marker_ids) != len(set(all_marker_ids)):
        raise ValueError("Marker IDs overlap between target faces.")

    point_manifest = {
        "schema_version": spec["schema_version"],
        "target_id": spec["target_id"],
        "warning": spec["measurement"]["warning"],
        "points": points,
    }
    (output_dir / "target-nominal-points.json").write_text(
        json.dumps(point_manifest, indent=2) + "\n", encoding="utf-8"
    )
    render_manifest = {
        "schema_version": spec["schema_version"],
        "target_id": spec["target_id"],
        "dictionary": spec["fiducials"]["dictionary"],
        "panels": panels,
        "print_rule": spec["fiducials"]["print_rule"],
        "warning": spec["measurement"]["warning"],
    }
    (output_dir / "render-manifest.json").write_text(
        json.dumps(render_manifest, indent=2) + "\n", encoding="utf-8"
    )
    return render_manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", type=Path, default=Path(__file__).with_name("target_spec.json"))
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--dpi", type=int)
    args = parser.parse_args()
    print(json.dumps(generate(args.spec, args.output_dir, args.dpi), indent=2))


if __name__ == "__main__":
    main()
