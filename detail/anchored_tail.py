"""Per-frame tail extraction anchored on body keypoints: segment the cat, subtract the body.

The propagated-mask approach (``sam2_tail_video``) tracks whatever blob it was first shown;
on the review sheets that blob became a hind leg within a second. Point-prompting SAM2 for
"the tail" directly does not work either: with more than a few negative points its IoU
head collapses to zero and the masks stay whole-cat.

So this module asks SAM2 only for what it is good at, the whole cat, and does the anatomy
itself. The body region is everything thick: a morphological opening of the cat mask with
a trunk-sized disc keeps the trunk and head and drops every thin protrusion (tail, legs,
ears). Keypoints then account for the thin parts that are not the tail: leg tubes along
the limb bones and a head polygon. What is left of the cat after subtracting both is thin
and has no keypoint on it, which for a cat is the tail. The connected piece touching
``tail_root`` is the candidate; rules reject it if it is speckle, too large, contains a
limb keypoint, or is not long and thin.

Propagation survives only as a tie-breaker: the previous tip seeds one of the cat-mask
prompts and previous-mask IoU is part of the selection score.

Everything except the SAM2 call is numpy/OpenCV so the rules are unit-testable.
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
from skimage.measure import label as label_components

from detail.mask_centerline import mask_to_tail_samples

KEYPOINT_SCORE_THRESHOLD = 0.3
ROOT_NAME = "tail_root"
TRUNK_NAMES = ["neck", "left_shoulder", "right_shoulder", "left_hip", "right_hip"]
HEAD_NAMES = ["nose", "left_eye", "right_eye"]
LEG_BONES = [
    ("left_shoulder", "left_elbow"),
    ("left_elbow", "left_front_paw"),
    ("right_shoulder", "right_elbow"),
    ("right_elbow", "right_front_paw"),
    ("left_hip", "left_knee"),
    ("left_knee", "left_back_paw"),
    ("right_hip", "right_knee"),
    ("right_knee", "right_back_paw"),
]
LEG_NAMES = sorted({name for bone in LEG_BONES for name in bone} - set(TRUNK_NAMES))

# Body-region geometry, as fractions of the detection bbox diagonal.
TRUNK_OPENING_RADIUS_FRACTION = 0.045  # opening removes anything thinner than twice this: tails, not a curled back
LEG_TUBE_WIDTH_FRACTION = 0.09
BODY_DILATION_FRACTION = 0.02
ROOT_TOLERANCE_FRACTION = 0.10  # candidate must come within this of tail_root; the root keypoint sits on the rump, not the tail base

# Candidate rules.
MAX_AREA_FRACTION_OF_BBOX = 0.30
MIN_AREA_PX = 40
MIN_ELONGATION = 3.0  # curve_length^2 / area; a tail is long and thin
MIN_SOLID_FRACTION = 0.5  # area surviving a small morphological opening; speckle does not
OPENING_RADIUS_PX = 3
MAX_ROOT_DISTANCE_FRACTION = 0.12  # curve start to tail_root
# A tail touches the body only at its base. A sliver of back or shadow that the opening
# peeled off the trunk touches the body along its whole length. This is the fraction of
# the candidate lying within a thin band around the body region.
BODY_CONTACT_BAND_FRACTION = 0.012  # of bbox diagonal
MAX_BODY_CONTACT_FRACTION = 0.35

TEMPORAL_IOU_WEIGHT = 0.5
ELONGATION_WEIGHT = 0.05


def _inside(mask: np.ndarray, x: float, y: float) -> bool:
    height, width = mask.shape
    col = min(width - 1, max(0, int(round(x))))
    row = min(height - 1, max(0, int(round(y))))
    return bool(mask[row, col])


def _mask_iou(a: np.ndarray | None, b: np.ndarray) -> float:
    if a is None:
        return 0.0
    inter = np.logical_and(a, b).sum()
    union = np.logical_or(a, b).sum()
    return float(inter / union) if union else 0.0


def _curve_length(samples: list[dict[str, Any]]) -> float:
    total = 0.0
    for prev, cur in zip(samples, samples[1:]):
        total += math.hypot(cur["x_px"] - prev["x_px"], cur["y_px"] - prev["y_px"])
    return total


def keypoint_map(keypoints: list[dict[str, Any]]) -> dict[str, tuple[float, float]]:
    """Keypoints above threshold as name -> (x, y)."""
    return {
        k["name"]: (float(k["x_px"]), float(k["y_px"]))
        for k in keypoints
        if float(k["score"]) >= KEYPOINT_SCORE_THRESHOLD
    }


def body_region(
    kps: dict[str, tuple[float, float]],
    cat_mask: np.ndarray,
    bbox_xyxy: list[float],
) -> np.ndarray:
    """Binary mask of the cat minus its thin protrusions, plus keypoint-drawn legs and
    head. The tail is what is left of the cat once this is removed."""
    height, width = cat_mask.shape
    diag = math.hypot(bbox_xyxy[2] - bbox_xyxy[0], bbox_xyxy[3] - bbox_xyxy[1])
    tube = max(3, int(LEG_TUBE_WIDTH_FRACTION * diag))
    trunk_radius = max(2, int(TRUNK_OPENING_RADIUS_FRACTION * diag))
    trunk_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * trunk_radius + 1, 2 * trunk_radius + 1))
    region = cv2.morphologyEx(cat_mask.astype(np.uint8), cv2.MORPH_OPEN, trunk_kernel)

    def poly(names: list[str]) -> None:
        points = [kps[n] for n in names if n in kps]
        if len(points) >= 3:
            hull = cv2.convexHull(np.array(points, dtype=np.float32)).astype(np.int32)
            cv2.fillConvexPoly(region, hull, 1)
        elif len(points) == 2:
            a, b = points
            cv2.line(region, (int(a[0]), int(a[1])), (int(b[0]), int(b[1])), 1, thickness=tube)

    poly(TRUNK_NAMES)
    poly(HEAD_NAMES + ["neck"])
    for a_name, b_name in LEG_BONES:
        if a_name in kps and b_name in kps:
            a, b = kps[a_name], kps[b_name]
            cv2.line(region, (int(a[0]), int(a[1])), (int(b[0]), int(b[1])), 1, thickness=tube)
            cv2.circle(region, (int(b[0]), int(b[1])), tube // 2, 1, -1)

    radius = max(1, int(BODY_DILATION_FRACTION * diag))
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * radius + 1, 2 * radius + 1))
    return cv2.dilate(region, kernel).astype(bool)


def root_component(mask: np.ndarray, root: tuple[float, float], tolerance: float) -> np.ndarray | None:
    """The connected component of ``mask`` that comes within ``tolerance`` px of the root,
    or None."""
    labels = label_components(mask, connectivity=2)
    if labels.max() == 0:
        return None
    ys, xs = np.nonzero(mask)
    d2 = (xs - root[0]) ** 2 + (ys - root[1]) ** 2
    nearest = int(np.argmin(d2))
    if d2[nearest] > tolerance * tolerance:
        return None
    return labels == labels[ys[nearest], xs[nearest]]


def evaluate_candidate(
    cat_mask: np.ndarray,
    *,
    sam_iou: float,
    kps: dict[str, tuple[float, float]],
    bbox_xyxy: list[float],
    previous_mask: np.ndarray | None,
    sample_count: int,
) -> dict[str, Any]:
    """Subtract the body region from a whole-cat mask and apply the tail rules to what is
    left at the root. Returns a record with ``rejections`` (empty when accepted) and, when
    accepted, the mask and curve."""
    cat_mask = cat_mask.astype(bool)
    root = kps[ROOT_NAME]
    bw, bh = bbox_xyxy[2] - bbox_xyxy[0], bbox_xyxy[3] - bbox_xyxy[1]
    bbox_area = max(bw * bh, 1.0)
    bbox_diag = math.hypot(bw, bh)

    rejections: list[str] = []
    record: dict[str, Any] = {
        "sam2_predicted_iou": float(sam_iou),
        "cat_mask_area_px": int(cat_mask.sum()),
    }

    body = body_region(kps, cat_mask, bbox_xyxy)
    remainder = np.logical_and(cat_mask, np.logical_not(body))
    mask = root_component(remainder, root, ROOT_TOLERANCE_FRACTION * bbox_diag)
    if mask is None:
        rejections.append("nothing_at_root")
        record["rejections"] = rejections
        return record

    area = int(mask.sum())
    record["mask_area_px"] = area
    record["mask_area_fraction_of_bbox"] = area / bbox_area
    record["temporal_iou"] = _mask_iou(previous_mask, mask)
    if area < MIN_AREA_PX:
        rejections.append("too_small")
        record["rejections"] = rejections
        return record
    if area / bbox_area > MAX_AREA_FRACTION_OF_BBOX:
        rejections.append("too_large")

    band_radius = max(2, int(BODY_CONTACT_BAND_FRACTION * bbox_diag))
    band_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * band_radius + 1, 2 * band_radius + 1))
    body_band = cv2.dilate(body.astype(np.uint8), band_kernel).astype(bool)
    record["body_contact_fraction"] = float(np.logical_and(mask, body_band).sum() / area)
    if record["body_contact_fraction"] > MAX_BODY_CONTACT_FRACTION:
        rejections.append("attached_along_body")

    open_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * OPENING_RADIUS_PX + 1, 2 * OPENING_RADIUS_PX + 1))
    solid = cv2.morphologyEx(mask.astype(np.uint8), cv2.MORPH_OPEN, open_kernel).astype(bool)
    record["solid_fraction"] = float(solid.sum() / area)
    if record["solid_fraction"] < MIN_SOLID_FRACTION:
        rejections.append("speckled")

    leg_hits = [n for n in LEG_NAMES if n in kps and _inside(mask, *kps[n])]
    if leg_hits:
        rejections.append("contains_leg_keypoint")
        record["leg_keypoints_inside"] = leg_hits
    head_hits = [n for n in HEAD_NAMES if n in kps and _inside(mask, *kps[n])]
    if head_hits:
        rejections.append("contains_head_keypoint")
        record["head_keypoints_inside"] = head_hits

    try:
        samples = mask_to_tail_samples(
            mask,
            base_xy=root,
            sample_count=sample_count,
            provenance="sam2_cat_mask_minus_keypoint_body_to_skeleton_v1",
        )
    except ValueError as exception:
        rejections.append("centreline_failed")
        record["centreline_error"] = str(exception)
        record["rejections"] = rejections
        return record

    length = _curve_length(samples)
    elongation = (length * length) / max(area, 1)
    start_distance = math.hypot(samples[0]["x_px"] - root[0], samples[0]["y_px"] - root[1])
    record.update(
        {"curve_length_px": length, "elongation": elongation, "curve_start_to_root_px": start_distance}
    )
    if elongation < MIN_ELONGATION:
        rejections.append("not_elongated")
    if start_distance > MAX_ROOT_DISTANCE_FRACTION * bbox_diag:
        rejections.append("curve_start_far_from_root")

    record["rejections"] = rejections
    if not rejections:
        record["mask"] = mask
        record["body"] = body
        record["curve"] = {"samples": samples}
        record["root_xy"] = [samples[0]["x_px"], samples[0]["y_px"]]
        record["tip_xy"] = [samples[-1]["x_px"], samples[-1]["y_px"]]
        record["selection_score"] = (
            float(sam_iou)
            + TEMPORAL_IOU_WEIGHT * record["temporal_iou"]
            + ELONGATION_WEIGHT * min(elongation, 20.0)
        )
    return record


def select_candidate(records: list[dict[str, Any]]) -> int | None:
    accepted = [i for i, r in enumerate(records) if not r["rejections"]]
    if not accepted:
        return None
    return max(accepted, key=lambda i: records[i]["selection_score"])


def cat_prompts(
    kps: dict[str, tuple[float, float]],
    bbox_xyxy: list[float],
    previous_tip: tuple[float, float] | None,
) -> list[dict[str, Any]]:
    """Whole-cat prompts for SAM2: the detection box, the box plus the root, and (when
    known) the box plus the previous tip so a tail SAM2 tends to drop is kept in."""
    root = kps[ROOT_NAME]
    prompts = [
        {"name": "box", "box": bbox_xyxy, "points": []},
        {"name": "box_plus_root", "box": bbox_xyxy, "points": [root]},
    ]
    if previous_tip is not None:
        prompts.append({"name": "box_plus_root_plus_previous_tip", "box": bbox_xyxy, "points": [root, previous_tip]})
    return prompts


def _render_overlay(
    image_path: Path,
    mask: np.ndarray,
    body: np.ndarray,
    samples: list[dict[str, Any]],
    kps: dict[str, tuple[float, float]],
    label: str,
    output_path: Path,
) -> None:
    image = Image.open(image_path).convert("RGBA")
    overlay = np.zeros((*mask.shape, 4), dtype=np.uint8)
    overlay[body] = (0, 110, 255, 45)
    overlay[mask] = (255, 0, 0, 120)
    composed = Image.alpha_composite(image, Image.fromarray(overlay, "RGBA"))
    draw = ImageDraw.Draw(composed)
    curve = [(s["x_px"], s["y_px"]) for s in samples]
    if len(curve) >= 2:
        draw.line(curve, fill=(255, 255, 0, 255), width=4)
    rx, ry = kps[ROOT_NAME]
    draw.ellipse((rx - 6, ry - 6, rx + 6, ry + 6), fill=(0, 255, 0, 255))
    draw.rectangle((8, 8, 8 + 11 * len(label), 34), fill=(0, 0, 0, 170))
    draw.text((14, 14), label, fill=(255, 255, 255, 255))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    composed.convert("RGB").save(output_path, quality=90)


def run(
    *,
    frames_dir: Path,
    body_json: Path,
    output_dir: Path,
    checkpoint: str,
    device: str,
    sample_count: int,
    clip_id: str | None = None,
) -> dict[str, Any]:
    try:
        from sam2.sam2_image_predictor import SAM2ImagePredictor
    except ImportError as exception:
        raise RuntimeError("SAM2 is required for anchored tail extraction") from exception

    body_run = json.loads(body_json.read_text(encoding="utf-8"))
    clip_id = clip_id or body_run["clip_id"]
    predictor = SAM2ImagePredictor.from_pretrained(checkpoint, device=device)

    previous_mask: np.ndarray | None = None
    previous_tip: tuple[float, float] | None = None
    frames_out: list[dict[str, Any]] = []
    status_counts: dict[str, int] = {}

    for frame in body_run["frames"]:
        index = int(frame["frame_index"])
        record: dict[str, Any] = {"frame_index": index, "file": frame["file"]}
        kps = keypoint_map(frame["keypoints"] or []) if frame.get("bbox_xyxy") else {}

        if not frame.get("bbox_xyxy"):
            record["status"] = "no_detection"
        elif ROOT_NAME not in kps:
            record["status"] = "no_tail_root"
        else:
            image = np.asarray(Image.open(frames_dir / frame["file"]).convert("RGB"))
            predictor.set_image(image)
            candidates: list[dict[str, Any]] = []
            for prompt in cat_prompts(kps, frame["bbox_xyxy"], previous_tip):
                kwargs: dict[str, Any] = {"box": np.array(prompt["box"], dtype=np.float32), "multimask_output": True}
                if prompt["points"]:
                    kwargs["point_coords"] = np.array(prompt["points"], dtype=np.float32)
                    kwargs["point_labels"] = np.ones(len(prompt["points"]), dtype=np.int32)
                masks, scores, _ = predictor.predict(**kwargs)
                for cand_index, (mask, score) in enumerate(zip(np.asarray(masks), np.asarray(scores).reshape(-1))):
                    evaluated = evaluate_candidate(
                        mask.astype(bool),
                        sam_iou=float(score),
                        kps=kps,
                        bbox_xyxy=frame["bbox_xyxy"],
                        previous_mask=previous_mask,
                        sample_count=sample_count,
                    )
                    evaluated["prompt"] = prompt["name"]
                    evaluated["candidate_index"] = cand_index
                    candidates.append(evaluated)

            chosen = select_candidate(candidates)
            record["candidates"] = [{k: v for k, v in c.items() if k not in ("curve", "mask", "body")} for c in candidates]
            if chosen is None:
                record["status"] = "all_candidates_rejected"
                reasons: dict[str, int] = {}
                for c in candidates:
                    for r in c["rejections"]:
                        reasons[r] = reasons.get(r, 0) + 1
                record["rejection_reasons"] = reasons
                previous_mask, previous_tip = None, None
            else:
                pick = candidates[chosen]
                record["status"] = "ok"
                record["chosen"] = {"prompt": pick["prompt"], "candidate_index": pick["candidate_index"]}
                record["curve"] = pick["curve"]
                record["curve_length_px"] = pick["curve_length_px"]
                record["root_xy"] = pick["root_xy"]
                record["tip_xy"] = pick["tip_xy"]
                record["mask_area_px"] = pick["mask_area_px"]
                previous_mask = pick["mask"]
                previous_tip = (pick["tip_xy"][0], pick["tip_xy"][1])
                _render_overlay(
                    frames_dir / frame["file"],
                    previous_mask,
                    pick["body"],
                    pick["curve"]["samples"],
                    kps,
                    f"{clip_id} f{index:03d} tail_anchored {pick['prompt']}",
                    output_dir / "overlays" / frame["file"],
                )

        status_counts[record["status"]] = status_counts.get(record["status"], 0) + 1
        frames_out.append(record)

    payload = {
        "schema_version": "0.2.0",
        "clip_id": clip_id,
        "method": "tail_anchored",
        "checkpoint": checkpoint,
        "device": device,
        "anchor_source": {"file": str(body_json), "model": body_run.get("model")},
        "rules": {
            "keypoint_score_threshold": KEYPOINT_SCORE_THRESHOLD,
            "body_region": {
                "trunk_opening_radius_fraction": TRUNK_OPENING_RADIUS_FRACTION,
                "trunk_polygon": TRUNK_NAMES,
                "head_polygon": HEAD_NAMES + ["neck"],
                "leg_bones": LEG_BONES,
                "leg_tube_width_fraction": LEG_TUBE_WIDTH_FRACTION,
                "dilation_fraction": BODY_DILATION_FRACTION,
            },
            "root_tolerance_fraction": ROOT_TOLERANCE_FRACTION,
            "max_area_fraction_of_bbox": MAX_AREA_FRACTION_OF_BBOX,
            "min_area_px": MIN_AREA_PX,
            "min_elongation": MIN_ELONGATION,
            "min_solid_fraction": MIN_SOLID_FRACTION,
            "opening_radius_px": OPENING_RADIUS_PX,
            "max_root_distance_fraction": MAX_ROOT_DISTANCE_FRACTION,
            "body_contact_band_fraction": BODY_CONTACT_BAND_FRACTION,
            "max_body_contact_fraction": MAX_BODY_CONTACT_FRACTION,
            "leg_reject_names": LEG_NAMES,
            "head_reject_names": HEAD_NAMES,
        },
        "evidence_tier": "S2",
        "summary": {
            "frames_total": len(frames_out),
            "frames_with_curve": status_counts.get("ok", 0),
            "status_counts": status_counts,
        },
        "frames": frames_out,
        "scientific_boundary": (
            "Masks and curves are model-derived. Subtracting a keypoint-built body region makes a "
            "leg less likely to be reported as a tail; it does not make an accepted curve correct. "
            "Accuracy needs human verdicts or independent labels."
        ),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "result.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Per-frame keypoint-anchored tail extraction from a SAM2 cat mask.")
    parser.add_argument("frames_dir", type=Path)
    parser.add_argument("body_json", type=Path, help="review.run_body output with per-frame keypoints")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--checkpoint", default="facebook/sam2.1-hiera-tiny")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--samples", type=int, default=24)
    args = parser.parse_args()
    result = run(
        frames_dir=args.frames_dir,
        body_json=args.body_json,
        output_dir=args.output_dir,
        checkpoint=args.checkpoint,
        device=args.device,
        sample_count=args.samples,
    )
    print(json.dumps(result["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
