from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from bakeoff.adapters.base import AdapterInfo, PoseAdapter


class MockAdapter(PoseAdapter):
    info = AdapterInfo(
        model_id="mock_model",
        version="0.1.0",
        checkpoint="deterministic-code-fixture",
        commercial_status="allowed",
    )

    _points = {
        "nose": (350.0, 190.0, 0.30),
        "left_ear_tip": (335.0, 165.0, 0.28),
        "right_ear_tip": (365.0, 165.0, 0.32),
        "left_front_paw": (330.0, 300.0, 0.20),
        "right_front_paw": (370.0, 300.0, 0.40),
        "left_hind_paw": (300.0, 305.0, 0.22),
        "right_hind_paw": (400.0, 305.0, 0.42),
        "tail_base": (290.0, 235.0, 0.35),
    }

    def predict(self, clip_manifest: dict[str, Any]) -> dict[str, Any]:
        frames = []
        for frame_index in range(8):
            keypoints_2d = []
            keypoints_3d = []
            shift = 2.0 * frame_index
            for point_index, (name, (x, y, z)) in enumerate(self._points.items()):
                score = 0.05 if name == "left_front_paw" and frame_index == 3 else 0.95
                keypoints_2d.append(
                    {
                        "native_name": name,
                        "canonical_name": name,
                        "x_px": x + shift,
                        "y_px": y,
                        "score": score,
                    }
                )
                keypoints_3d.append(
                    {
                        "native_name": name,
                        "canonical_name": name,
                        "x": (x - 320.0) / 200.0 + 0.01 * frame_index,
                        "y": (240.0 - y) / 200.0,
                        "z": z,
                        "coordinate_frame": "camera",
                        "score": score,
                    }
                )

            frames.append(
                {
                    "frame_index": frame_index,
                    "timestamp_s": frame_index / 30.0,
                    "inference_ms": 10.0 + (frame_index % 2),
                    "keypoints_2d": keypoints_2d,
                    "keypoints_3d": keypoints_3d,
                }
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
            "source": {"width_px": 640, "height_px": 480, "fps": 30.0},
            "skeleton_edges_3d": [
                ["left_ear_tip", "nose"],
                ["right_ear_tip", "nose"],
                ["left_front_paw", "left_hind_paw"],
                ["right_front_paw", "right_hind_paw"],
            ],
            "diagnostic_depth_pairs": [
                ["left_front_paw", "right_front_paw"],
                ["left_hind_paw", "right_hind_paw"],
            ],
            "frames": frames,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate deterministic mock bake-off output.")
    parser.add_argument("--clip", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    adapter = MockAdapter()
    prediction = adapter.predict_file(args.clip)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(prediction, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
