"""Run RTMPose-m (AP-10K, ONNX SDK export) on every review frame and draw overlays.

This is the same RTMPose-m AP-10K checkpoint the bake-off adapter runs through MMPose,
but taken from OpenMMLab's ONNX SDK export and executed with rtmlib/onnxruntime so it
runs on a plain Windows machine without the MMPose stack. Outputs are S2 model
pseudo-labels; the human verdicts collected against them are what this directory is for.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw

from review.common import (
    BODY_SCORE_THRESHOLD,
    clip_workdir,
    frames_dir,
    load_clips,
    load_frames_manifest,
    write_json,
)

DETECTOR_ONNX = "https://github.com/Megvii-BaseDetection/YOLOX/releases/download/0.1.1rc0/yolox_m.onnx"
POSE_ONNX = (
    "https://download.openmmlab.com/mmpose/v1/projects/rtmposev1/onnx_sdk/"
    "rtmpose-m_simcc-ap10k_pt-aic-coco_210e-256x256-7a041aa1_20230206.zip"
)
# COCO indices the YOLOX multiclass head may assign to a cat. Dog is accepted because
# the detector sometimes labels a cat as a dog; the class is recorded, not hidden.
ANIMAL_CLASSES = {15: "cat", 16: "dog"}

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
SKELETON = [
    (0, 1), (0, 2), (1, 2), (2, 3), (3, 4),
    (3, 5), (5, 6), (6, 7),
    (3, 8), (8, 9), (9, 10),
    (4, 11), (11, 12), (12, 13),
    (4, 14), (14, 15), (15, 16),
]
GROUP_COLOUR = {
    "head": (255, 80, 80),
    "spine": (255, 220, 0),
    "front": (80, 200, 255),
    "hind": (120, 255, 120),
}


def _group(index: int) -> str:
    if index <= 2:
        return "head"
    if index in (3, 4):
        return "spine"
    if index <= 10:
        return "front"
    return "hind"


def _load_models(device: str) -> tuple[Any, Any]:
    from rtmlib import RTMPose, YOLOX

    detector = YOLOX(
        DETECTOR_ONNX,
        det_mode="multiclass",
        model_input_size=(640, 640),
        backend="onnxruntime",
        device=device,
    )
    pose = RTMPose(
        POSE_ONNX,
        model_input_size=(256, 256),
        backend="onnxruntime",
        device=device,
    )
    return detector, pose


class GroundingCatDetector:
    """Grounding DINO prompted with "cat." as a drop-in for YOLOX. Returns boxes and a
    class id of 15 (COCO cat) so the rest of the run is unchanged. Slower, but on the
    review clips it finds cats YOLOX-m misses (motion blur, small)."""

    def __init__(self, device: str, model_id: str = "IDEA-Research/grounding-dino-tiny", threshold: float = 0.3):
        import torch
        from transformers import AutoModelForZeroShotObjectDetection, AutoProcessor

        torch.set_grad_enabled(False)
        self.processor = AutoProcessor.from_pretrained(model_id)
        self.model = AutoModelForZeroShotObjectDetection.from_pretrained(model_id).to(device).eval()
        self.device = device
        self.model_id = model_id
        self.threshold = threshold

    def __call__(self, image_bgr: np.ndarray) -> tuple[list[list[float]], list[int]]:
        image = Image.fromarray(image_bgr[:, :, ::-1])
        inputs = self.processor(images=image, text="cat.", return_tensors="pt").to(self.device)
        outputs = self.model(**inputs)
        result = self.processor.post_process_grounded_object_detection(
            outputs, inputs.input_ids, threshold=self.threshold, text_threshold=self.threshold, target_sizes=[image.size[::-1]]
        )[0]
        boxes = [[float(v) for v in box] for box in result["boxes"]]
        return boxes, [15] * len(boxes)


def _pick_box(bboxes: Any, classes: Any) -> tuple[list[float] | None, int | None]:
    candidates = [
        (bbox, int(cls))
        for bbox, cls in zip(bboxes, classes)
        if int(cls) in ANIMAL_CLASSES
    ]
    if not candidates:
        return None, None
    # Largest animal box; the review clips are single-cat.
    bbox, cls = max(candidates, key=lambda item: (item[0][2] - item[0][0]) * (item[0][3] - item[0][1]))
    return [float(v) for v in bbox], cls


def _draw_overlay(
    image_path: Path,
    keypoints: np.ndarray | None,
    scores: np.ndarray | None,
    bbox: list[float] | None,
    label: str,
    output_path: Path,
) -> None:
    image = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(image)
    radius = max(4, int(min(image.size) * 0.006))
    if bbox:
        draw.rectangle(bbox, outline=(255, 255, 255), width=2)
    if keypoints is not None and scores is not None:
        for a, b in SKELETON:
            if scores[a] >= BODY_SCORE_THRESHOLD and scores[b] >= BODY_SCORE_THRESHOLD:
                colour = GROUP_COLOUR[_group(b)]
                draw.line(
                    [tuple(keypoints[a]), tuple(keypoints[b])],
                    fill=colour,
                    width=max(2, radius // 2),
                )
        for index, ((x, y), score) in enumerate(zip(keypoints, scores)):
            colour = GROUP_COLOUR[_group(index)]
            box = (x - radius, y - radius, x + radius, y + radius)
            if score >= BODY_SCORE_THRESHOLD:
                draw.ellipse(box, fill=colour, outline=(0, 0, 0))
            else:
                draw.ellipse(box, outline=colour, width=2)
    draw.rectangle((8, 8, 8 + 12 * len(label), 34), fill=(0, 0, 0, 170))
    draw.text((14, 14), label, fill=(255, 255, 255))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path, quality=90)


def run_clip(clip_id: str, *, device: str, detector_kind: str = "yolox") -> dict[str, Any]:
    import cv2

    detector, pose = _load_models(device)
    if detector_kind == "grounding":
        # ONNX runtime stays on CPU for pose; the grounding detector wants the GPU when there is one.
        import torch

        detector = GroundingCatDetector("cuda" if torch.cuda.is_available() else "cpu")
    manifest = load_frames_manifest(clip_id)
    src_dir = frames_dir(clip_id)
    out_dir = clip_workdir(clip_id) / "overlays" / "body"

    frames_out = []
    started = time.time()
    for frame in manifest["frames"]:
        path = src_dir / frame["file"]
        image = cv2.imread(str(path))
        bboxes, classes = detector(image)
        bbox, cls = _pick_box(bboxes, classes)
        record: dict[str, Any] = {
            "frame_index": frame["frame_index"],
            "file": frame["file"],
            "detector_class": ANIMAL_CLASSES.get(cls) if cls is not None else None,
            "bbox_xyxy": bbox,
            "keypoints": None,
        }
        keypoints = scores = None
        if bbox is not None:
            kps, scs = pose(image, bboxes=[bbox])
            keypoints, scores = kps[0], scs[0]
            record["keypoints"] = [
                {
                    "name": AP10K_NAMES[i],
                    "x_px": float(keypoints[i][0]),
                    "y_px": float(keypoints[i][1]),
                    "score": float(scores[i]),
                }
                for i in range(len(AP10K_NAMES))
            ]
            record["n_above_threshold"] = int((scores >= BODY_SCORE_THRESHOLD).sum())
        # No overlay when nothing was detected: the sheet builder then shows the raw
        # frame with a NO OUTPUT banner so the reviewer judges the miss explicitly.
        if bbox is not None:
            label = f"{clip_id} f{frame['frame_index']:03d} t={frame['timestamp_s']:.2f}s body"
            _draw_overlay(path, keypoints, scores, bbox, label, out_dir / frame["file"])
        frames_out.append(record)

    detected = sum(1 for f in frames_out if f["bbox_xyxy"] is not None)
    payload = {
        "schema_version": "0.1.0",
        "clip_id": clip_id,
        "method": "body",
        "model": {
            "detector": getattr(detector, "model_id", DETECTOR_ONNX),
            "detector_kind": detector_kind,
            "pose": POSE_ONNX,
            "runtime": "rtmlib/onnxruntime",
            "device": device,
            "score_threshold": BODY_SCORE_THRESHOLD,
        },
        "evidence_tier": "S2",
        "summary": {
            "frames": len(frames_out),
            "frames_with_detection": detected,
            "wall_seconds": round(time.time() - started, 2),
        },
        "frames": frames_out,
    }
    write_json(clip_workdir(clip_id) / "body.json", payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Run RTMPose AP-10K over the review frames.")
    parser.add_argument("--clip", action="append")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--detector", choices=["yolox", "grounding"], default="grounding", help="grounding (default since 2026-09-14) finds cats YOLOX-m misses on the review clips")
    args = parser.parse_args()
    for clip in load_clips():
        if args.clip and clip["clip_id"] not in args.clip:
            continue
        payload = run_clip(clip["clip_id"], device=args.device, detector_kind=args.detector)
        print(json.dumps({"clip_id": clip["clip_id"], **payload["summary"]}))


if __name__ == "__main__":
    main()
