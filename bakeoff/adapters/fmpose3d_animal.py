from __future__ import annotations

import argparse
import json
import time
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

from bakeoff.adapters.base import AdapterInfo, PoseAdapter
from bakeoff.adapters.deeplabcut_common import (
    dataframe_to_2d_frames,
    dataframe_to_3d_by_frame,
)
from bakeoff.adapters.superanimal_quadruped import _first_result, _video_metadata


FMPOSE_CANONICAL_NAME = {
    "left_eye": "left_eye",
    "right_eye": "right_eye",
    "nose": "nose",
    "neck": "neck",
    "root_of_tail": "tail_base",
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
    "right_knee": "right_hind_knee",
    "right_back_paw": "right_hind_paw",
    "withers": "withers",
    "throat": "throat",
    # Generic ear points are preserved but are not silently promoted to ear tips.
    "left_ear": "left_ear",
    "right_ear": "right_ear",
    "mouth": "mouth",
    "chin": "chin",
    "left_hock": "left_hock",
    "right_hock": "right_hock",
    "tail_tip": "tail_tip",
}

SKELETON_EDGES = [
    ["left_shoulder", "left_elbow"],
    ["left_elbow", "left_front_paw"],
    ["right_shoulder", "right_elbow"],
    ["right_elbow", "right_front_paw"],
    ["left_hip", "left_knee"],
    ["left_knee", "left_hock"],
    ["left_hock", "left_hind_paw"],
    ["right_hip", "right_hind_knee"],
    ["right_hind_knee", "right_hock"],
    ["right_hock", "right_hind_paw"],
]

DIAGNOSTIC_DEPTH_PAIRS = [
    ["left_eye", "right_eye"],
    ["left_front_paw", "right_front_paw"],
    ["left_hind_paw", "right_hind_paw"],
]


def _package_version() -> str:
    try:
        return version("deeplabcut")
    except PackageNotFoundError:
        return "unknown"


class FMPose3DAnimalAdapter(PoseAdapter):
    """Research baseline for current DeepLabCut-integrated FMPose3D animal inference."""

    def __init__(self, *, device: str = "auto", batch_size: int = 8) -> None:
        self.device = device
        self.batch_size = batch_size
        self.info = AdapterInfo(
            model_id="fmpose3d_animal",
            version=_package_version(),
            checkpoint="deeplabcut:fmpose3d_animals/default",
            commercial_status="research_only_or_unknown",
        )

    def predict(self, clip_manifest: dict[str, Any]) -> dict[str, Any]:
        try:
            from deeplabcut.modelzoo.video_inference import video_inference_superanimal
        except ImportError as exception:
            raise RuntimeError(
                "FMPose3D adapter dependencies are not installed. See "
                "bakeoff/environments/deeplabcut.md."
            ) from exception

        local_path = clip_manifest.get("source", {}).get("local_path")
        if not local_path:
            raise ValueError(
                "FMPose3D adapter requires source.local_path. Link-only media must "
                "be materialized by a separate licence-aware step."
            )
        video_path = Path(local_path)
        if not video_path.exists():
            raise FileNotFoundError(video_path)

        width, height, fps = _video_metadata(video_path)

        import tempfile

        with tempfile.TemporaryDirectory(prefix="catpose-fmpose3d-") as directory:
            started = time.perf_counter()
            results = video_inference_superanimal(
                videos=[str(video_path)],
                superanimal_name="quadruped",
                model_name="fmpose3d_animals",
                dest_folder=directory,
                batch_size=self.batch_size,
                max_individuals=1,
                device=self.device,
                create_labeled_video=False,
                fmpose_return_3d=True,
            )
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            payload = _first_result(results)

        if not isinstance(payload, dict) or "df_2d" not in payload or "df_3d" not in payload:
            raise RuntimeError(
                "FMPose3D did not return the expected {'df_2d', 'df_3d'} payload."
            )
        df_2d = payload["df_2d"]
        df_3d = payload["df_3d"]
        if len(df_2d) == 0:
            raise RuntimeError("FMPose3D returned an empty 2D DataFrame")
        if len(df_3d) != len(df_2d):
            raise RuntimeError("FMPose3D 2D and 3D frame counts differ")

        amortized_ms = elapsed_ms / len(df_2d)
        frames = dataframe_to_2d_frames(
            df_2d,
            fps=fps,
            inference_ms_per_frame=amortized_ms,
            canonical_map=FMPOSE_CANONICAL_NAME,
        )
        points_3d = dataframe_to_3d_by_frame(
            df_3d,
            canonical_map=FMPOSE_CANONICAL_NAME,
            # Current integration exposes coordinates but does not make us claim a
            # world/camera convention here. Preserve them as model-native evidence.
            coordinate_frame="model_native",
        )
        for frame, frame_points_3d in zip(frames, points_3d):
            frame["keypoints_3d"] = frame_points_3d

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
            "skeleton_edges_3d": SKELETON_EDGES,
            "diagnostic_depth_pairs": DIAGNOSTIC_DEPTH_PAIRS,
            "frames": frames,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run FMPose3D Animals on one clip.")
    parser.add_argument("--clip", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--batch-size", type=int, default=8)
    args = parser.parse_args()

    manifest = json.loads(args.clip.read_text(encoding="utf-8"))
    prediction = FMPose3DAnimalAdapter(
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
