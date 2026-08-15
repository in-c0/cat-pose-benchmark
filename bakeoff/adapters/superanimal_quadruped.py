from __future__ import annotations

import argparse
import json
import time
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

from bakeoff.adapters.base import AdapterInfo, PoseAdapter
from bakeoff.adapters.deeplabcut_common import (
    QUADRUPED_CANONICAL_NAME,
    dataframe_to_2d_frames,
)


def _package_version() -> str:
    try:
        return version("deeplabcut")
    except PackageNotFoundError:
        return "unknown"


def _video_metadata(path: Path) -> tuple[int, int, float]:
    try:
        import cv2
    except ImportError as exception:
        raise RuntimeError("OpenCV is required to inspect input video metadata") from exception

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


def _first_result(results: dict[Any, Any]) -> Any:
    if not results:
        raise RuntimeError("DeepLabCut returned no video result")
    return next(iter(results.values()))


class SuperAnimalQuadrupedAdapter(PoseAdapter):
    """Research-only zero-shot SuperAnimal-Quadruped baseline."""

    def __init__(self, *, device: str = "auto", batch_size: int = 1) -> None:
        self.device = device
        self.batch_size = batch_size
        self.info = AdapterInfo(
            model_id="superanimal_quadruped",
            version=_package_version(),
            checkpoint="deeplabcut-modelzoo:superanimal_quadruped/hrnet_w32",
            commercial_status="research_only",
        )

    def predict(self, clip_manifest: dict[str, Any]) -> dict[str, Any]:
        try:
            from deeplabcut.modelzoo.video_inference import video_inference_superanimal
        except ImportError as exception:
            raise RuntimeError(
                "DeepLabCut adapter dependencies are not installed. See "
                "bakeoff/environments/deeplabcut.md."
            ) from exception

        local_path = clip_manifest.get("source", {}).get("local_path")
        if not local_path:
            raise ValueError(
                "SuperAnimal adapter requires source.local_path. Link-only media must "
                "be materialized by a separate licence-aware step."
            )
        video_path = Path(local_path)
        if not video_path.exists():
            raise FileNotFoundError(video_path)

        width, height, fps = _video_metadata(video_path)

        import tempfile

        with tempfile.TemporaryDirectory(prefix="catpose-superanimal-") as directory:
            started = time.perf_counter()
            results = video_inference_superanimal(
                videos=[str(video_path)],
                superanimal_name="superanimal_quadruped",
                model_name="hrnet_w32",
                detector_name="fasterrcnn_resnet50_fpn_v2",
                dest_folder=directory,
                video_adapt=False,
                plot_trajectories=False,
                batch_size=self.batch_size,
                detector_batch_size=self.batch_size,
                max_individuals=1,
                device=self.device,
                plot_bboxes=False,
                create_labeled_video=False,
            )
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            dataframe = _first_result(results)

        if len(dataframe) == 0:
            raise RuntimeError("SuperAnimal returned an empty DataFrame")
        amortized_ms = elapsed_ms / len(dataframe)
        frames = dataframe_to_2d_frames(
            dataframe,
            fps=fps,
            inference_ms_per_frame=amortized_ms,
            canonical_map=QUADRUPED_CANONICAL_NAME,
        )

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
                "scope": "whole_video_amortized_including_setup",
                "notes": "Whole video_inference_superanimal call divided by output frames; includes model/setup overhead and is not directly comparable to RTMPose per-frame timing.",
            },
            "frames": frames,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run SuperAnimal-Quadruped on one clip.")
    parser.add_argument("--clip", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--batch-size", type=int, default=1)
    args = parser.parse_args()

    manifest = json.loads(args.clip.read_text(encoding="utf-8"))
    prediction = SuperAnimalQuadrupedAdapter(
        device=args.device,
        batch_size=args.batch_size,
    ).predict(manifest)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(prediction, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
