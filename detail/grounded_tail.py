"""Text-grounded tail: ask a vision-language detector for "tail", then segment that box.

The propagated (``sam2_tail_video``) and anchored (``anchored_tail``) methods both lack
semantics: one tracks a blob, the other subtracts geometry. This one asks Grounding DINO
for ``"cat. tail."`` on every frame, keeps the tail box that sits inside a cat box, and
hands that box to SAM2 for a mask. No propagation, no geometry, no filtering: whatever
the detector thinks a tail is, that is what gets drawn, so the human review measures the
detector's notion of a tail rather than a hand-tuned filter of it.

A keypoint veto (refuse a mask that contains a limb or head keypoint) is available with
``veto_keypoints=True`` but is off by default. On *Cat Plays* it removed six true tails
(RTMPose had put paw keypoints on the tail of a cat lying on its back) and kept five
false ones (the keypoints were wrong there too), so it traded one model's errors for
another's. Limb/head keypoints inside the mask are always recorded as diagnostics.

Grounding DINO (IDEA-Research, Apache-2.0) via transformers; SAM2 (Apache-2.0).
Everything except the model calls is pure Python so the box selection is unit-testable.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageDraw

from detail.mask_centerline import mask_to_tail_samples

PROMPT = "cat. tail."
DETECTOR_ID = "IDEA-Research/grounding-dino-tiny"
BOX_THRESHOLD = 0.15
TEXT_THRESHOLD = 0.15
MIN_CAT_SCORE = 0.3
MIN_TAIL_SCORE = 0.2
# A "tail" box covering most of a cat box is the detector grounding the whole animal.
MAX_TAIL_TO_CAT_AREA = 0.5
ROOT_NAME = "tail_root"
KEYPOINT_SCORE_THRESHOLD = 0.3
LIMB_NAMES = [
    "left_front_paw", "right_front_paw", "left_back_paw", "right_back_paw",
    "left_knee", "right_knee", "left_elbow", "right_elbow",
]
HEAD_NAMES = ["nose", "left_eye", "right_eye"]

# Geometry features measured on every accepted mask against a SAM2 cat mask (always
# recorded), and the thresholds the optional ``geometry_rules`` pass applies to them.
TRUNK_OPENING_RADIUS_FRACTION = 0.045
BODY_CONTACT_BAND_FRACTION = 0.012
MAX_BODY_CONTACT_FRACTION = 0.45
MIN_ELONGATION = 2.5

Box = list[float]  # x0, y0, x1, y1


def _area(box: Box) -> float:
    return max(0.0, box[2] - box[0]) * max(0.0, box[3] - box[1])


def _iou(a: Box, b: Box) -> float:
    x0, y0 = max(a[0], b[0]), max(a[1], b[1])
    x1, y1 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, x1 - x0) * max(0.0, y1 - y0)
    union = _area(a) + _area(b) - inter
    return inter / union if union else 0.0


def _centre_inside(inner: Box, outer: Box, margin: float = 0.0) -> bool:
    cx, cy = (inner[0] + inner[2]) / 2, (inner[1] + inner[3]) / 2
    return outer[0] - margin <= cx <= outer[2] + margin and outer[1] - margin <= cy <= outer[3] + margin


def pick_cat_box(detections: list[dict[str, Any]], prefer: Box | None) -> dict[str, Any] | None:
    """Highest-scoring 'cat' detection, or the one overlapping ``prefer`` most when a
    reference cat box (e.g. from the body run) is given."""
    # The detector sometimes merges the two phrases and labels the whole animal
    # "cat tail"; that box is still the cat. (Found 2026-09-14; four jumping-clip frames
    # had no cat before this, so note 01's coverage numbers predate the fix.)
    cats = [d for d in detections if "cat" in d["label"].split() and d["score"] >= MIN_CAT_SCORE]
    if not cats:
        return None
    if prefer is not None:
        overlapping = [d for d in cats if _iou(d["box"], prefer) > 0.1]
        if overlapping:
            return max(overlapping, key=lambda d: _iou(d["box"], prefer))
    return max(cats, key=lambda d: d["score"])


def pick_tail_box(detections: list[dict[str, Any]], cat: dict[str, Any]) -> dict[str, Any] | None:
    """Highest-scoring 'tail' detection whose centre lies in the cat box and which is
    not most of the cat box."""
    cat_box = cat["box"]
    margin = 0.05 * math.hypot(cat_box[2] - cat_box[0], cat_box[3] - cat_box[1])
    tails = [
        d
        for d in detections
        if "tail" in d["label"]
        and d["score"] >= MIN_TAIL_SCORE
        and _centre_inside(d["box"], cat_box, margin)
        and _area(d["box"]) <= MAX_TAIL_TO_CAT_AREA * _area(cat_box)
    ]
    if not tails:
        return None
    return max(tails, key=lambda d: d["score"])


def keypoints_inside(mask: np.ndarray, kps: dict[str, tuple[float, float]], names: list[str]) -> list[str]:
    height, width = mask.shape
    hits = []
    for name in names:
        if name not in kps:
            continue
        x, y = kps[name]
        col = min(width - 1, max(0, int(round(x))))
        row = min(height - 1, max(0, int(round(y))))
        if mask[row, col]:
            hits.append(name)
    return hits


def geometry_features(
    tail_mask: np.ndarray,
    cat_mask: np.ndarray,
    cat_box: Box,
    samples: list[dict[str, Any]] | None,
) -> dict[str, float]:
    """How the grounded tail mask sits against the cat: fraction inside the thick body
    (cat mask opened with a trunk-sized disc), fraction within a thin band around that
    body, and centreline elongation. Recorded for analysis; only used to refuse when
    ``geometry_rules`` is on."""
    diag = math.hypot(cat_box[2] - cat_box[0], cat_box[3] - cat_box[1])
    r = max(2, int(TRUNK_OPENING_RADIUS_FRACTION * diag))
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))
    body = cv2.morphologyEx(cat_mask.astype(np.uint8), cv2.MORPH_OPEN, kernel).astype(bool)
    br = max(2, int(BODY_CONTACT_BAND_FRACTION * diag))
    band_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * br + 1, 2 * br + 1))
    band = cv2.dilate(body.astype(np.uint8), band_kernel).astype(bool)
    area = max(int(tail_mask.sum()), 1)
    length = 0.0
    if samples:
        for prev, cur in zip(samples, samples[1:]):
            length += math.hypot(cur["x_px"] - prev["x_px"], cur["y_px"] - prev["y_px"])
    return {
        "inside_body_fraction": float(np.logical_and(tail_mask, body).sum() / area),
        "body_contact_fraction": float(np.logical_and(tail_mask, band).sum() / area),
        "elongation": float(length * length / area),
        "tail_to_cat_area": float(area / max(int(cat_mask.sum()), 1)),
    }


def geometry_rejections(features: dict[str, float]) -> list[str]:
    rejections = []
    if features["body_contact_fraction"] > MAX_BODY_CONTACT_FRACTION:
        rejections.append("attached_along_body")
    if features["elongation"] < MIN_ELONGATION:
        rejections.append("not_elongated")
    return rejections


def base_point(mask: np.ndarray, root: tuple[float, float] | None, cat_box: Box) -> tuple[float, float]:
    """Where the centreline should start: the tail_root keypoint when the body run has
    one, else the cat-box centre (the base is the end nearer the body)."""
    if root is not None:
        return root
    return ((cat_box[0] + cat_box[2]) / 2, (cat_box[1] + cat_box[3]) / 2)


def _load_models(device: str) -> tuple[Any, Any, Any]:
    import torch
    from transformers import AutoModelForZeroShotObjectDetection, AutoProcessor

    try:
        from sam2.sam2_image_predictor import SAM2ImagePredictor
    except ImportError as exception:
        raise RuntimeError("SAM2 is required for grounded tail segmentation") from exception

    processor = AutoProcessor.from_pretrained(DETECTOR_ID)
    detector = AutoModelForZeroShotObjectDetection.from_pretrained(DETECTOR_ID).to(device).eval()
    predictor = SAM2ImagePredictor.from_pretrained("facebook/sam2.1-hiera-tiny", device=device)
    torch.set_grad_enabled(False)
    return processor, detector, predictor


def _detect(processor: Any, detector: Any, image: Image.Image, device: str) -> list[dict[str, Any]]:
    inputs = processor(images=image, text=PROMPT, return_tensors="pt").to(device)
    outputs = detector(**inputs)
    result = processor.post_process_grounded_object_detection(
        outputs,
        inputs.input_ids,
        threshold=BOX_THRESHOLD,
        text_threshold=TEXT_THRESHOLD,
        target_sizes=[image.size[::-1]],
    )[0]
    labels = result.get("text_labels", result.get("labels"))
    return [
        {"label": str(label), "score": float(score), "box": [float(v) for v in box]}
        for score, label, box in zip(result["scores"], labels, result["boxes"])
    ]


def _render_overlay(
    image: Image.Image,
    mask: np.ndarray | None,
    samples: list[dict[str, Any]] | None,
    cat: dict[str, Any] | None,
    tail: dict[str, Any] | None,
    label: str,
    output_path: Path,
) -> None:
    composed = image.convert("RGBA")
    if mask is not None:
        overlay = np.zeros((*mask.shape, 4), dtype=np.uint8)
        overlay[mask] = (255, 0, 0, 120)
        composed = Image.alpha_composite(composed, Image.fromarray(overlay, "RGBA"))
    draw = ImageDraw.Draw(composed)
    if cat:
        draw.rectangle(cat["box"], outline=(255, 255, 255, 255), width=2)
    if tail:
        draw.rectangle(tail["box"], outline=(0, 255, 255, 255), width=3)
        draw.text((tail["box"][0] + 4, tail["box"][1] + 4), f"tail {tail['score']:.2f}", fill=(0, 255, 255, 255))
    if samples:
        curve = [(s["x_px"], s["y_px"]) for s in samples]
        if len(curve) >= 2:
            draw.line(curve, fill=(255, 255, 0, 255), width=4)
        draw.ellipse((curve[0][0] - 6, curve[0][1] - 6, curve[0][0] + 6, curve[0][1] + 6), fill=(0, 255, 0, 255))
    draw.rectangle((8, 8, 8 + 11 * len(label), 34), fill=(0, 0, 0, 170))
    draw.text((14, 14), label, fill=(255, 255, 255, 255))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    composed.convert("RGB").save(output_path, quality=90)


def run(
    *,
    frames_dir: Path,
    frames_manifest: Path,
    output_dir: Path,
    body_json: Path | None,
    device: str,
    sample_count: int,
    clip_id: str | None = None,
    veto_keypoints: bool = False,
    geometry_rules: bool = False,
) -> dict[str, Any]:
    manifest = json.loads(frames_manifest.read_text(encoding="utf-8"))
    clip_id = clip_id or manifest["clip_id"]
    body_frames: dict[int, dict[str, Any]] = {}
    if body_json and body_json.exists():
        body_frames = {int(f["frame_index"]): f for f in json.loads(body_json.read_text(encoding="utf-8"))["frames"]}

    processor, detector, predictor = _load_models(device)
    frames_out: list[dict[str, Any]] = []
    status_counts: dict[str, int] = {}

    for frame in manifest["frames"]:
        index = int(frame["frame_index"])
        image = Image.open(frames_dir / frame["file"]).convert("RGB")
        detections = _detect(processor, detector, image, device)
        record: dict[str, Any] = {"frame_index": index, "file": frame["file"], "detections": detections}

        body = body_frames.get(index, {})
        prefer = body.get("bbox_xyxy")
        kps = {
            kp["name"]: (float(kp["x_px"]), float(kp["y_px"]))
            for kp in body.get("keypoints") or []
            if float(kp["score"]) >= KEYPOINT_SCORE_THRESHOLD
        }
        root = kps.get(ROOT_NAME)

        cat = pick_cat_box(detections, prefer)
        tail = pick_tail_box(detections, cat) if cat else None
        record["cat"] = cat
        record["tail"] = tail
        mask = samples = None
        if cat is None:
            record["status"] = "no_cat"
        elif tail is None:
            record["status"] = "no_tail_box"
        else:
            predictor.set_image(np.asarray(image))
            masks, scores, _ = predictor.predict(box=np.array(tail["box"], dtype=np.float32), multimask_output=True)
            best = int(np.argmax(np.asarray(scores).reshape(-1)))
            mask = np.asarray(masks)[best].astype(bool)
            # keep the mask inside the tail box; SAM2 sometimes bleeds into the body
            x0, y0, x1, y1 = (int(round(v)) for v in tail["box"])
            clipped = np.zeros_like(mask)
            clipped[max(0, y0) : y1 + 1, max(0, x0) : x1 + 1] = mask[max(0, y0) : y1 + 1, max(0, x0) : x1 + 1]
            mask = clipped
            record["sam2_predicted_iou"] = float(np.asarray(scores).reshape(-1)[best])
            record["mask_area_px"] = int(mask.sum())
            limb_hits = keypoints_inside(mask, kps, LIMB_NAMES) if mask.any() else []
            head_hits = keypoints_inside(mask, kps, HEAD_NAMES) if mask.any() else []
            record["limb_keypoints_inside"] = limb_hits
            record["head_keypoints_inside"] = head_hits
            if not mask.any():
                record["status"] = "empty_mask"
                mask = None
            elif veto_keypoints and limb_hits:
                record["status"] = "tail_on_limb"
                mask = None
            elif veto_keypoints and head_hits:
                record["status"] = "tail_on_head"
                mask = None
            else:
                try:
                    samples = mask_to_tail_samples(
                        mask,
                        base_xy=base_point(mask, root, cat["box"]),
                        sample_count=sample_count,
                        provenance="grounding_dino_tail_box_sam2_mask_to_skeleton_v1",
                    )
                    cat_masks, cat_scores, _ = predictor.predict(
                        box=np.array(cat["box"], dtype=np.float32), multimask_output=True
                    )
                    cat_mask = np.asarray(cat_masks)[int(np.argmax(np.asarray(cat_scores).reshape(-1)))].astype(bool)
                    features = geometry_features(mask, cat_mask, cat["box"], samples)
                    record["geometry"] = features
                    rejections = geometry_rejections(features)
                    record["geometry_rejections"] = rejections
                    if geometry_rules and rejections:
                        record["status"] = "geometry_rejected"
                        mask = None
                    else:
                        record["status"] = "ok"
                        record["curve"] = {"samples": samples}
                        record["root_xy"] = [samples[0]["x_px"], samples[0]["y_px"]]
                        record["tip_xy"] = [samples[-1]["x_px"], samples[-1]["y_px"]]
                        record["base_from"] = "tail_root_keypoint" if root else "cat_box_centre"
                except ValueError as exception:
                    record["status"] = "centreline_failed"
                    record["centreline_error"] = str(exception)
        if record["status"] == "ok":
            _render_overlay(
                image,
                mask,
                samples,
                cat,
                tail,
                f"{clip_id} f{index:03d} tail_grounded {tail['score']:.2f}",
                output_dir / "overlays" / frame["file"],
            )
        status_counts[record["status"]] = status_counts.get(record["status"], 0) + 1
        frames_out.append(record)

    payload = {
        "schema_version": "0.1.0",
        "clip_id": clip_id,
        "method": "tail_grounded",
        "models": {
            "detector": DETECTOR_ID,
            "prompt": PROMPT,
            "segmenter": "facebook/sam2.1-hiera-tiny",
            "device": device,
        },
        "selection": {
            "box_threshold": BOX_THRESHOLD,
            "text_threshold": TEXT_THRESHOLD,
            "min_cat_score": MIN_CAT_SCORE,
            "min_tail_score": MIN_TAIL_SCORE,
            "max_tail_to_cat_area": MAX_TAIL_TO_CAT_AREA,
            "cat_box_preference": "body-run bbox when present, else highest score",
            "keypoint_veto": {"enabled": veto_keypoints, "limb": LIMB_NAMES, "head": HEAD_NAMES},
            "geometry_rules": {
                "enabled": geometry_rules,
                "max_body_contact_fraction": MAX_BODY_CONTACT_FRACTION,
                "min_elongation": MIN_ELONGATION,
                "trunk_opening_radius_fraction": TRUNK_OPENING_RADIUS_FRACTION,
                "body_contact_band_fraction": BODY_CONTACT_BAND_FRACTION,
            },
        },
        "evidence_tier": "S2",
        "summary": {
            "frames_total": len(frames_out),
            "frames_with_curve": status_counts.get("ok", 0),
            "status_counts": status_counts,
        },
        "frames": frames_out,
        "scientific_boundary": (
            "Boxes, masks and curves are model-derived. A confident 'tail' box is the detector's "
            "opinion, not a measurement; the human review decides how often it is right."
        ),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "result.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Text-grounded per-frame tail via Grounding DINO + SAM2.")
    parser.add_argument("frames_dir", type=Path)
    parser.add_argument("frames_manifest", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--body-json", type=Path, help="optional review.run_body output for cat preference and tail_root")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--samples", type=int, default=24)
    parser.add_argument("--veto-keypoints", action="store_true", help="refuse masks containing a limb/head keypoint")
    parser.add_argument("--geometry-rules", action="store_true", help="refuse masks that fail the anchored-style body-contact and elongation rules")
    args = parser.parse_args()
    result = run(
        frames_dir=args.frames_dir,
        frames_manifest=args.frames_manifest,
        output_dir=args.output_dir,
        body_json=args.body_json,
        device=args.device,
        sample_count=args.samples,
        veto_keypoints=args.veto_keypoints,
        geometry_rules=args.geometry_rules,
    )
    print(json.dumps(result["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
