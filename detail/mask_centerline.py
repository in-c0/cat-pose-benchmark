from __future__ import annotations

import argparse
import heapq
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
from skimage.morphology import skeletonize


_NEIGHBOURS = (
    (-1, -1),
    (-1, 0),
    (-1, 1),
    (0, -1),
    (0, 1),
    (1, -1),
    (1, 0),
    (1, 1),
)


def _nearest_pixel(
    pixels: np.ndarray, point_xy: tuple[float, float]
) -> tuple[int, int]:
    if len(pixels) == 0:
        raise ValueError("tail mask skeleton is empty")
    # Skeleton pixels are (row=y, col=x).
    x, y = point_xy
    distances = (pixels[:, 1] - x) ** 2 + (pixels[:, 0] - y) ** 2
    row, col = pixels[int(np.argmin(distances))]
    return int(row), int(col)


def _longest_geodesic_path(
    skeleton: np.ndarray, start: tuple[int, int]
) -> list[tuple[int, int]]:
    height, width = skeleton.shape
    distances: dict[tuple[int, int], float] = {start: 0.0}
    previous: dict[tuple[int, int], tuple[int, int]] = {}
    queue: list[tuple[float, tuple[int, int]]] = [(0.0, start)]

    while queue:
        distance, current = heapq.heappop(queue)
        if distance != distances.get(current):
            continue
        row, col = current
        for drow, dcol in _NEIGHBOURS:
            neighbour = (row + drow, col + dcol)
            nrow, ncol = neighbour
            if not (0 <= nrow < height and 0 <= ncol < width):
                continue
            if not skeleton[neighbour]:
                continue
            edge = math.sqrt(2.0) if drow and dcol else 1.0
            candidate = distance + edge
            if candidate < distances.get(neighbour, math.inf):
                distances[neighbour] = candidate
                previous[neighbour] = current
                heapq.heappush(queue, (candidate, neighbour))

    if len(distances) < 2:
        return [start]

    # Prefer an actual skeleton endpoint when one is reachable. This avoids choosing an
    # arbitrary interior pixel when several branches have nearly equal geodesic length.
    endpoints = [
        pixel
        for pixel in distances
        if pixel != start and _skeleton_degree(skeleton, pixel) <= 1
    ]
    candidates = endpoints or [pixel for pixel in distances if pixel != start]
    end = max(candidates, key=lambda pixel: distances[pixel])

    path = [end]
    while path[-1] != start:
        path.append(previous[path[-1]])
    path.reverse()
    return path


def _skeleton_degree(skeleton: np.ndarray, pixel: tuple[int, int]) -> int:
    height, width = skeleton.shape
    row, col = pixel
    degree = 0
    for drow, dcol in _NEIGHBOURS:
        nrow, ncol = row + drow, col + dcol
        if 0 <= nrow < height and 0 <= ncol < width and skeleton[nrow, ncol]:
            degree += 1
    return degree


def _resample_path(
    path: list[tuple[int, int]], count: int
) -> list[tuple[float, float]]:
    if count < 2:
        raise ValueError("sample count must be >= 2")
    if not path:
        raise ValueError("cannot resample an empty path")
    points = [(float(col), float(row)) for row, col in path]
    if len(points) == 1:
        return [points[0] for _ in range(count)]

    segment_lengths = [
        math.hypot(right[0] - left[0], right[1] - left[1])
        for left, right in zip(points, points[1:])
    ]
    cumulative = [0.0]
    for length in segment_lengths:
        cumulative.append(cumulative[-1] + length)
    total = cumulative[-1]
    if total <= 1e-12:
        return [points[0] for _ in range(count)]

    output: list[tuple[float, float]] = []
    segment_index = 0
    for sample_index in range(count):
        target = total * sample_index / (count - 1)
        while (
            segment_index < len(segment_lengths) - 1
            and cumulative[segment_index + 1] < target
        ):
            segment_index += 1
        length = segment_lengths[segment_index]
        alpha = (
            (target - cumulative[segment_index]) / length if length > 1e-12 else 0.0
        )
        left = points[segment_index]
        right = points[segment_index + 1]
        output.append(
            (
                left[0] + alpha * (right[0] - left[0]),
                left[1] + alpha * (right[1] - left[1]),
            )
        )
    return output


def mask_to_tail_samples(
    mask: np.ndarray,
    *,
    base_xy: tuple[float, float],
    sample_count: int = 16,
    provenance: str = "mask_skeleton_longest_path_v0",
) -> list[dict[str, Any]]:
    """Return an ordered base-to-tip curve from a binary tail segmentation mask.

    This is an engineering baseline, not learned anatomy. Branches created by a noisy
    segmentation can make the longest-path heuristic choose the wrong tip; that failure
    is intentional and measurable.
    """

    if mask.ndim != 2:
        raise ValueError("tail mask must be a 2D array")
    binary = mask.astype(bool)
    if not binary.any():
        raise ValueError("tail mask is empty")

    skeleton = skeletonize(binary)
    pixels = np.argwhere(skeleton)
    start = _nearest_pixel(pixels, base_xy)
    path = _longest_geodesic_path(skeleton, start)
    points = _resample_path(path, sample_count)

    return [
        {
            "u": index / (sample_count - 1),
            "x_px": point[0],
            "y_px": point[1],
            "visibility": "visible",
            "confidence": 1.0,
            "provenance": provenance,
        }
        for index, point in enumerate(points)
    ]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract a base-to-tip tail centreline from a binary NumPy mask."
    )
    parser.add_argument("mask_npy", type=Path)
    parser.add_argument("--base-x", type=float, required=True)
    parser.add_argument("--base-y", type=float, required=True)
    parser.add_argument("--samples", type=int, default=16)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    mask = np.load(args.mask_npy)
    samples = mask_to_tail_samples(
        mask,
        base_xy=(args.base_x, args.base_y),
        sample_count=args.samples,
    )
    rendered = json.dumps({"samples": samples}, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
