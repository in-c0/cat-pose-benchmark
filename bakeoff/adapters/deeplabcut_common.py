from __future__ import annotations

import math
from typing import Any


QUADRUPED_CANONICAL_NAME = {
    "nose": "nose",
    "left_eye": "left_eye",
    "right_eye": "right_eye",
    "left_earbase": "left_ear_base",
    "right_earbase": "right_ear_base",
    "left_earend": "left_ear_tip",
    "right_earend": "right_ear_tip",
    "neck_base": "neck_base",
    "neck_end": "neck_end",
    "back_base": "back_base",
    "back_middle": "back_middle",
    "back_end": "back_end",
    "tail_base": "tail_base",
    "tail_end": "tail_tip",
    "front_left_knee": "left_front_knee",
    "front_right_knee": "right_front_knee",
    "front_left_paw": "left_front_paw",
    "front_right_paw": "right_front_paw",
    "back_left_knee": "left_hind_knee",
    "back_right_knee": "right_hind_knee",
    "back_left_paw": "left_hind_paw",
    "back_right_paw": "right_hind_paw",
}


def _finite(value: Any) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _columns_by_key(df: Any) -> dict[tuple[str, str, str], Any]:
    """Index a DLC DataFrame by (individual, bodypart, coord).

    DeepLabCut DataFrames use MultiIndex columns whose named levels include
    ``bodyparts`` and ``coords`` and may include ``individuals``. Scorer/model levels
    are intentionally ignored because one inference result should contain one scorer.
    """

    names = list(df.columns.names)
    if "bodyparts" not in names or "coords" not in names:
        raise ValueError(
            "DeepLabCut DataFrame must have named 'bodyparts' and 'coords' column levels"
        )

    indexed: dict[tuple[str, str, str], Any] = {}
    for column in df.columns:
        parts = column if isinstance(column, tuple) else (column,)
        if len(parts) != len(names):
            raise ValueError("DeepLabCut column tuple does not match named levels")
        metadata = dict(zip(names, parts))
        individual = str(metadata.get("individuals", "single"))
        bodypart = str(metadata["bodyparts"])
        coord = str(metadata["coords"])
        indexed[(individual, bodypart, coord)] = column
    return indexed


def _selected_individual(
    row: Any,
    indexed: dict[tuple[str, str, str], Any],
) -> str | None:
    individuals = sorted({key[0] for key in indexed})
    if not individuals:
        return None
    if individuals == ["single"]:
        return "single"

    best: tuple[float, str] | None = None
    for individual in individuals:
        likelihoods: list[float] = []
        for (candidate, _bodypart, coord), column in indexed.items():
            if candidate != individual or coord != "likelihood":
                continue
            value = row[column]
            if _finite(value):
                likelihoods.append(float(value))
        score = sum(likelihoods) / len(likelihoods) if likelihoods else float("-inf")
        candidate_score = (score, individual)
        if best is None or candidate_score > best:
            best = candidate_score
    return best[1] if best is not None else individuals[0]


def dataframe_to_2d_frames(
    df: Any,
    *,
    fps: float,
    inference_ms_per_frame: float,
    canonical_map: dict[str, str | None] | None = None,
) -> list[dict[str, Any]]:
    if fps <= 0:
        raise ValueError("fps must be positive")
    indexed = _columns_by_key(df)
    canonical_map = canonical_map or {}
    bodyparts = sorted({key[1] for key in indexed})

    frames: list[dict[str, Any]] = []
    for frame_index in range(len(df)):
        row = df.iloc[frame_index]
        individual = _selected_individual(row, indexed)
        keypoints = []
        if individual is not None:
            for bodypart in bodyparts:
                x_column = indexed.get((individual, bodypart, "x"))
                y_column = indexed.get((individual, bodypart, "y"))
                likelihood_column = indexed.get((individual, bodypart, "likelihood"))
                if x_column is None or y_column is None:
                    continue
                x = row[x_column]
                y = row[y_column]
                if not _finite(x) or not _finite(y):
                    continue
                score = row[likelihood_column] if likelihood_column is not None else 1.0
                score = float(score) if _finite(score) else 0.0
                keypoints.append(
                    {
                        "native_name": bodypart,
                        "canonical_name": canonical_map.get(bodypart),
                        "x_px": float(x),
                        "y_px": float(y),
                        "score": score,
                    }
                )
        frames.append(
            {
                "frame_index": frame_index,
                "timestamp_s": frame_index / fps,
                "inference_ms": inference_ms_per_frame,
                "keypoints_2d": keypoints,
            }
        )
    return frames


def dataframe_to_3d_by_frame(
    df: Any,
    *,
    canonical_map: dict[str, str | None] | None = None,
    coordinate_frame: str = "model_native",
) -> list[list[dict[str, Any]]]:
    indexed = _columns_by_key(df)
    canonical_map = canonical_map or {}
    individuals = sorted({key[0] for key in indexed})
    if len(individuals) > 1:
        raise ValueError(
            "3D DeepLabCut conversion currently expects one individual; "
            f"found {individuals}"
        )
    individual = individuals[0] if individuals else "single"
    bodyparts = sorted({key[1] for key in indexed})

    output: list[list[dict[str, Any]]] = []
    for frame_index in range(len(df)):
        row = df.iloc[frame_index]
        points = []
        for bodypart in bodyparts:
            columns = [
                indexed.get((individual, bodypart, coord)) for coord in ("x", "y", "z")
            ]
            if any(column is None for column in columns):
                continue
            values = [row[column] for column in columns]
            if not all(_finite(value) for value in values):
                continue
            points.append(
                {
                    "native_name": bodypart,
                    "canonical_name": canonical_map.get(bodypart),
                    "x": float(values[0]),
                    "y": float(values[1]),
                    "z": float(values[2]),
                    "coordinate_frame": coordinate_frame,
                }
            )
        output.append(points)
    return output
