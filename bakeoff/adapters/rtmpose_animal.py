from __future__ import annotations

import argparse
import json
import time
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

from bakeoff.adapters.base import AdapterInfo, PoseAdapter


AP10K_NAMES = [
    "left_eye",
    "right_eye",
    "nose",
    "neck",
    "tail_root",
    "left_shoulder",
    "left_elbow",
    "left_front_paw",
    "right_shoulder",
    "right_elbow",
    "right_front_paw",
    "left_hip",
    "left_knee",
    "left_back_paw",
    "right_hip",
    "right_knee",
    "right_back_paw",
]

CANONICAL_NAME = {
    "left_eye": "left_eye",
    "right_eye": "right_eye",
    "nose": "nose",
    "neck": "neck",
    "tail_root": "tail_base",
    "left_shoulder": "left_shoulder",
    "left_elbow": "left_elbow",
    "left_front_paw": "left_front_paw",
    "right_shoulder": "right_shoulder",
    "right_elbow": "right_elbow",
    "right_front_paw": "right_front_paw",
    "left_hip": "left_hip",
    "left_knee": "left_knee",
    "left_back_paw": "left_hind_paw",
    "right_hip": "right_hip",
    "right_knee": "right_knee",
    "right_back_paw": "right_hind_paw",
}


def _mmpose_version() -> str:
    try:
        return version("mmpose")
    except PackageNotFoundError:
        return "unknown"


def _length(value: Any) -> int:
    if value is None:
        return 0
    try:
        return len(value)
    except TypeError:
        return 0


def _unwrap_instances(result: dict[str, Any]) -> list[dict[str, Any]]:
    predictions = result.get("predictions")
    if predictions is None or _length(predictions) == 0:
        return []
    if _length(predictions) == 1 and isinstance(predictions[0], list):
        return predictions[0]
    if all(isinstance(item, dict) for item in predictions):
        return list(predictions)
    return []


def _instance_score(instance: dict[str, Any]) -> float:
    scores = instance.get("keypoint_scores")
    if scores is not None and _length(scores) > 0:
        return sum(float(score) for score in scores) / _length(scores)

    bbox_score = instance.get("bbox_score")
    if bbox_score is None:
        return 0.0
    try:
        return float(bbox_score)
    except (TypeError, ValueError):
        if _length(bbox_score) > 0:
            return float(bbox_score[0])
    return 0.0


def canonical_keypoints(instance: dict[str, Any]) -> list[dict[str, Any]]:
    coordinates = instance.get("keypoints")
    scores = instance.get("keypoint_scores")
    if coordinates is None:
        coordinates = []
    if scores is None:
        scores = []

    if _length(coordinates) != len(AP10K_NAMES):
        raise ValueError(
            f"RTMPose animal returned {_length(coordinates)} keypoints; expected "
            f"{len(AP10K_NAMES)} for AP-10K."
        )
    if _length(scores) not in (0, _length(coordinates)):
        raise ValueError("RTMPose keypoint_scores length does not match keypoints")

    converted = []
    for index, (native_name, coordinate) in enumerate(zip(AP10K_NAMES, coordinates)):
        score = float(scores[index]) if _length(scores) else 1.0
        converted.append(
            {
                "native_name": native_name,
                "canonical_name": CANONICAL_NAME.get(native_name),
                "x_px": float(coordinate[0]),
                "y_px": float(coordinate[1]),
                "score": score,
            }
        )
    return converted


class RTMPoseAnimalAdapter(PoseAdapter):
    def __init__(
        self,
        *,
        device: str | None = None,
        stride: int = 1,
        max_frames: int | None = None,
    ) -> None:
        if stride < 1:
            raise ValueError("stride must be >= 1")
        self.device = device
        self.stride = stride
        self.max_frames = max_frames
        self.info = AdapterInfo(
            model_id="rtmpose_animal",
            version=_mmpose_version(),
            checkpoint="mmpose-alias:animal/rtmpose-m_ap10k",
            commercial_status="unknown",
        )

    def predict(self, clip_manifest: dict[str, Any]) -> dict[str, Any]:
        try:
            import cv2
            from mmpose.apis import MMPoseInferencer
        except ImportError as exception:
            raise RuntimeError(
                "RTMPose adapter dependencies are not installed. See "
                "bakeoff/environments/rtmpose.md."
            ) from exception

        local_path = clip_manifest.get("source", {}).get("local_path")
        if not local_path:
            raise ValueError(
                "RTMPose adapter requires source.local_path. Link-only clips must be "
                "materialized by a separate licence-aware fetch step."
            )

        video_path = Path(local_path)
        if not video_path.exists():
            raise FileNotFoundError(video_path)

        capture = cv2.VideoCapture(str(video_path))
        if not capture.isOpened():
            raise RuntimeError(f"Could not open video: {video_path}")

        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = float(capture.get(cv2.CAP_PROP_FPS)) or 30.0

        kwargs: dict[str, Any] = {"pose2d": "animal"}
        if self.device:
            kwargs["device"] = self.device
        inferencer = MMPoseInferencer(**kwargs)

        frames = []
        source_frame_index = 0
        emitted_index = 0
        try:
            while True:
                ok, frame = capture.read()
                if not ok:
                    break
                if source_frame_index % self.stride != 0:
                    source_frame_index += 1
                    continue
                if self.max_frames is not None and emitted_index >= self.max_frames:
                    break

                started = time.perf_counter()
                result = next(inferencer(frame, show=False))
                inference_ms = (time.perf_counter() - started) * 1000.0
                instances = _unwrap_instances(result)
                selected = max(instances, key=_instance_score) if instances else None
                keypoints_2d = canonical_keypoints(selected) if selected else []

                frames.append(
                    {
                        "frame_index": emitted_index,
                        "timestamp_s": source_frame_index / fps,
                        "inference_ms": inference_ms,
                        "keypoints_2d": keypoints_2d,
                    }
                )
                emitted_index += 1
                source_frame_index += 1
        finally:
            capture.release()

        if not frames:
            raise RuntimeError("No frames were emitted from the input video")

        return {
            "schema_version": "0.1.0",
            "clip_id": clip_manifest["clip_id"],
            "model": {
                "id": self.info.model_id,
                "version": self.info.version,
                "checkpoint": self.info.checkpoint,
                "commercial_status": self.info.commercial_status,
            },
            "source": {"width_px": width, "height_px": height, "fps": fps},
            "timing": {
                "scope": "per_frame_model_call_after_initialization",
                "notes": "Per emitted frame around the inferencer call; model construction/checkpoint initialization is excluded.",
            },
            "frames": frames,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run MMPose RTMPose Animal on one clip.")
    parser.add_argument("--clip", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--device")
    parser.add_argument("--stride", type=int, default=1)
    parser.add_argument("--max-frames", type=int)
    args = parser.parse_args()

    manifest = json.loads(args.clip.read_text(encoding="utf-8"))
    adapter = RTMPoseAnimalAdapter(
        device=args.device,
        stride=args.stride,
        max_frames=args.max_frames,
    )
    prediction = adapter.predict(manifest)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(prediction, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
