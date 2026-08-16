from __future__ import annotations

import argparse
import json
import math
import tempfile
import time
from pathlib import Path
from typing import Any

from bakeoff.adapters.deeplabcut_common import (
    QUADRUPED_CANONICAL_NAME,
    _columns_by_key,
    _finite,
)


def dataframe_to_candidate_frames(
    df: Any,
    *,
    fps: float,
    frame_offset: int = 0,
    confidence_threshold: float = 0.2,
) -> list[dict[str, Any]]:
    if fps <= 0:
        raise ValueError("fps must be positive")
    indexed = _columns_by_key(df)
    individuals = sorted({key[0] for key in indexed})
    bodyparts = sorted({key[1] for key in indexed})

    frames: list[dict[str, Any]] = []
    for local_index in range(len(df)):
        row = df.iloc[local_index]
        candidates: list[dict[str, Any]] = []
        for individual in individuals:
            keypoints = []
            scores = []
            high_conf_xy: list[tuple[float, float]] = []
            for bodypart in bodyparts:
                x_column = indexed.get((individual, bodypart, "x"))
                y_column = indexed.get((individual, bodypart, "y"))
                score_column = indexed.get((individual, bodypart, "likelihood"))
                if x_column is None or y_column is None:
                    continue
                x = row[x_column]
                y = row[y_column]
                if not _finite(x) or not _finite(y):
                    continue
                score_value = row[score_column] if score_column is not None else 1.0
                score = float(score_value) if _finite(score_value) else 0.0
                canonical = QUADRUPED_CANONICAL_NAME.get(bodypart)
                keypoint = {
                    "native_name": bodypart,
                    "canonical_name": canonical,
                    "x_px": float(x),
                    "y_px": float(y),
                    "score": score,
                }
                keypoints.append(keypoint)
                scores.append(score)
                if score >= confidence_threshold:
                    high_conf_xy.append((float(x), float(y)))

            # DeepLabCut may allocate individual columns even when no meaningful
            # detection exists. Do not manufacture a candidate from all-NaN / all-low
            # rows.
            if not keypoints or not high_conf_xy:
                continue
            xs = [point[0] for point in high_conf_xy]
            ys = [point[1] for point in high_conf_xy]
            candidates.append(
                {
                    "individual": individual,
                    "mean_keypoint_score": sum(scores) / len(scores) if scores else 0.0,
                    "high_confidence_keypoint_count": len(high_conf_xy),
                    "bbox_xyxy": [min(xs), min(ys), max(xs), max(ys)],
                    "centroid_xy": [sum(xs) / len(xs), sum(ys) / len(ys)],
                    "keypoints_2d": keypoints,
                }
            )

        candidates.sort(
            key=lambda candidate: (
                candidate["high_confidence_keypoint_count"],
                candidate["mean_keypoint_score"],
                candidate["individual"],
            ),
            reverse=True,
        )
        frames.append(
            {
                "frame_index": frame_offset + local_index,
                "local_frame_index": local_index,
                "timestamp_s": (frame_offset + local_index) / fps,
                "candidate_count": len(candidates),
                "candidates": candidates,
            }
        )
    return frames


def _first_result(results: dict[Any, Any]) -> Any:
    if not results:
        raise RuntimeError("DeepLabCut returned no video result")
    return next(iter(results.values()))


def _video_metadata(path: Path) -> tuple[int, int, float]:
    import cv2

    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise RuntimeError(f"Could not open video: {path}")
    try:
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = float(capture.get(cv2.CAP_PROP_FPS)) or 30.0
    finally:
        capture.release()
    return width, height, fps


def _render_candidate_overlays(
    video_path: Path,
    frames: list[dict[str, Any]],
    output_dir: Path,
) -> None:
    import cv2
    from PIL import Image, ImageDraw

    output_dir.mkdir(parents=True, exist_ok=True)
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise RuntimeError(f"Could not open video for rendering: {video_path}")
    try:
        for frame in frames:
            local_index = int(frame["local_frame_index"])
            capture.set(cv2.CAP_PROP_POS_FRAMES, local_index)
            ok, bgr = capture.read()
            if not ok:
                raise RuntimeError(f"Could not read video frame {local_index}")
            rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
            image = Image.fromarray(rgb)
            draw = ImageDraw.Draw(image)
            for candidate_index, candidate in enumerate(frame["candidates"]):
                left, top, right, bottom = candidate["bbox_xyxy"]
                # Visual IDs use different line widths/dashes through labels rather than
                # implying any stable identity semantics from display colour.
                draw.rectangle((left, top, right, bottom), outline="red", width=4)
                label = (
                    f"candidate {candidate_index}: {candidate['individual']} "
                    f"n={candidate['high_confidence_keypoint_count']} "
                    f"score={candidate['mean_keypoint_score']:.2f}"
                )
                draw.rectangle((left, max(0, top - 22), min(image.width - 1, left + 360), top), fill="black")
                draw.text((left + 4, max(0, top - 19)), label, fill="white")
                for point in candidate["keypoints_2d"]:
                    if float(point["score"]) < 0.2:
                        continue
                    x, y = float(point["x_px"]), float(point["y_px"])
                    radius = 3 + candidate_index
                    draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill="yellow")
            draw.rectangle((8, 8, 210, 34), fill="black")
            draw.text((14, 13), f"source frame {frame['frame_index']}", fill="white")
            image.save(output_dir / f"{frame['frame_index']:05d}.jpg", quality=92)
    finally:
        capture.release()


def _make_contact_sheet(overlays_dir: Path, output_path: Path, columns: int = 4) -> None:
    from PIL import Image

    paths = sorted(overlays_dir.glob("*.jpg"))
    images = [Image.open(path).convert("RGB") for path in paths]
    if not images:
        return
    thumb_width = 480
    thumb_height = int(round(thumb_width * images[0].height / images[0].width))
    rows = math.ceil(len(images) / columns)
    sheet = Image.new("RGB", (thumb_width * columns, thumb_height * rows), "black")
    for index, image in enumerate(images):
        sheet.paste(
            image.resize((thumb_width, thumb_height)),
            ((index % columns) * thumb_width, (index // columns) * thumb_height),
        )
    sheet.save(output_path, quality=92)


def run(
    *,
    video_path: Path,
    output_dir: Path,
    device: str,
    max_individuals: int,
    frame_offset: int,
    confidence_threshold: float,
) -> dict[str, Any]:
    try:
        from deeplabcut.modelzoo.video_inference import video_inference_superanimal
    except ImportError as exception:
        raise RuntimeError("DeepLabCut 3 is required for the multi-candidate probe") from exception

    if max_individuals < 2:
        raise ValueError("multi-candidate probe requires max_individuals >= 2")
    if not video_path.exists():
        raise FileNotFoundError(video_path)

    width, height, fps = _video_metadata(video_path)
    with tempfile.TemporaryDirectory(prefix="catpose-multi-superanimal-") as directory:
        started = time.perf_counter()
        results = video_inference_superanimal(
            videos=[str(video_path)],
            superanimal_name="superanimal_quadruped",
            model_name="hrnet_w32",
            detector_name="fasterrcnn_resnet50_fpn_v2",
            dest_folder=directory,
            video_adapt=False,
            plot_trajectories=False,
            batch_size=1,
            detector_batch_size=1,
            max_individuals=max_individuals,
            device=device,
            plot_bboxes=False,
            create_labeled_video=False,
        )
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        dataframe = _first_result(results)

    frames = dataframe_to_candidate_frames(
        dataframe,
        fps=fps,
        frame_offset=frame_offset,
        confidence_threshold=confidence_threshold,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    overlays_dir = output_dir / "overlays"
    _render_candidate_overlays(video_path, frames, overlays_dir)
    _make_contact_sheet(overlays_dir, output_dir / "candidate-contact-sheet.jpg")

    counts = [frame["candidate_count"] for frame in frames]
    result = {
        "schema_version": "0.1.0",
        "model": {
            "id": "superanimal_quadruped_multi_candidate",
            "version": "deeplabcut-3.0.1",
            "checkpoint": "deeplabcut-modelzoo:superanimal_quadruped/hrnet_w32",
            "commercial_status": "research_only",
        },
        "source": {
            "width_px": width,
            "height_px": height,
            "fps": fps,
            "frame_offset": frame_offset,
        },
        "max_individuals": max_individuals,
        "confidence_threshold": confidence_threshold,
        "elapsed_ms_including_setup": elapsed_ms,
        "frames": frames,
        "summary": {
            "frames_total": len(frames),
            "frames_with_two_or_more_candidates": sum(count >= 2 for count in counts),
            "frames_with_one_candidate": sum(count == 1 for count in counts),
            "frames_with_zero_candidates": sum(count == 0 for count in counts),
            "candidate_counts": counts,
            "assignment_feasibility": (
                "candidate_layer_available"
                if any(count >= 2 for count in counts)
                else "no_multi_candidate_layer"
            ),
            "interpretation_boundary": (
                "Candidate count/pose confidence does not establish stable identity. This probe "
                "only tests whether an explicit assignment layer has multiple animal hypotheses to choose from."
            ),
        },
        "scientific_boundary": (
            "All candidate skeletons are research-only R3 model outputs. They are not identity labels, "
            "ground truth, or product-training supervision."
        ),
    }
    (output_dir / "multi-candidates.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Probe whether SuperAnimal exposes multiple cat candidates in an identity-switch window."
    )
    parser.add_argument("video", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--max-individuals", type=int, default=2)
    parser.add_argument("--frame-offset", type=int, default=0)
    parser.add_argument("--confidence", type=float, default=0.2)
    args = parser.parse_args()

    result = run(
        video_path=args.video,
        output_dir=args.output_dir,
        device=args.device,
        max_individuals=args.max_individuals,
        frame_offset=args.frame_offset,
        confidence_threshold=args.confidence,
    )
    print(json.dumps(result["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
