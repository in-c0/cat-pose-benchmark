"""Grounded tail v1: zoom, a second opinion on the crop, and temporal consistency.

Three additions to ``grounded_tail`` (v0), each aimed at the "whether" failure: v0 finds
an extended tail well and draws a paw when the tail is tucked, because the detector must
return something once it has a cat.

1. **Zoom.** Detect the cat on the full frame, then run the ``"cat. tail."`` prompt on a
   padded crop of the cat box. The detector resizes its input to ~800 px on the short
   side, so a 30 px tail in a 1280 px frame becomes a 30 px tail in a 400 px crop: the
   part gets pixels.
2. **Crop check.** Each candidate tail box, padded, is scored by SigLIP against
   "a cat's tail" / "paw" / "leg" / "face" / "belly" / "floor". A candidate whose paw
   score beats its tail score is refused. This is a different model with a different
   failure mode from the detector and from the pose model, which is why it can help
   where the keypoint veto could not.
3. **Temporal consistency.** Candidates surviving 1–2 on every frame, plus an explicit
   "no tail" state, go through a Viterbi pass: emission is the detection score, moving
   between boxes costs their centre displacement in cat-box diagonals, entering or
   leaving "no tail" costs a fixed penalty. A real tail moves smoothly; a paw picked by
   default jumps. The path gives a per-frame answer including "none".

SAM2 then segments the chosen box exactly as in v0. All pure-Python parts (box mapping,
the paw rule, Viterbi) are unit-tested without models.

On the review set, zoom made things slightly worse (the crop-pass detector scores drop
and the candidates change) so it is off by default; the crop check alone did nothing
because the detector's second candidate is as wrong as its first; the two together with
the temporal pass are what moved precision. Thresholds were chosen by a grid on the same
57 frames and are not validated on held-out video.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw

from detail.grounded_tail import (
    DETECTOR_ID,
    MAX_TAIL_TO_CAT_AREA,
    MIN_CAT_SCORE,
    MIN_TAIL_SCORE,
    Box,
    _area,
    _centre_inside,
    _detect,
    _iou,
    base_point,
    geometry_features,
    keypoints_inside,
    pick_cat_box,
)
from detail.grounded_tail import HEAD_NAMES, KEYPOINT_SCORE_THRESHOLD, LIMB_NAMES, ROOT_NAME
from detail.mask_centerline import mask_to_tail_samples

CROP_PAD = 0.25  # of cat box size, each side
CANDIDATES_PER_FRAME = 2

CLASSIFIER_ID = "google/siglip-base-patch16-224"
CROP_TEXTS = [
    "a photo of a cat's tail",
    "a photo of a cat's paw",
    "a photo of a cat's leg",
    "a photo of a cat's face",
    "a photo of a cat's belly",
    "a photo of a carpet or floor",
]
CROP_CHECK_PAD = 0.3
MIN_PAW_TO_REFUSE = 0.10  # paw sigmoid must be at least this and above tail

NONE_EMISSION = 0.20  # what "no tail" scores per frame, on the detector-score scale
MOVE_WEIGHT = 0.5  # cost per cat-box diagonal of centre displacement
NONE_SWITCH_COST = 0.20  # entering or leaving the "no tail" state
# The three constants above were fitted at 4 fps (frame interval 0.25 s). Emissions
# accumulate per frame, so at a denser sampling a stretch of frames carries more emission
# mass against the same per-switch cost and the path changes shape at sequence edges.
# With ``time_scale`` on, per-frame emissions are multiplied by (frame interval / 0.25 s)
# so the same clip carries the same emission mass at any sampling rate.
REFERENCE_INTERVAL_S = 0.25


def pad_box(box: Box, pad: float, width: int, height: int) -> Box:
    w, h = box[2] - box[0], box[3] - box[1]
    return [
        max(0.0, box[0] - pad * w),
        max(0.0, box[1] - pad * h),
        min(float(width), box[2] + pad * w),
        min(float(height), box[3] + pad * h),
    ]


def map_box_from_crop(box: Box, crop: Box) -> Box:
    """A box in crop pixel coordinates -> full-frame coordinates."""
    return [box[0] + crop[0], box[1] + crop[1], box[2] + crop[0], box[3] + crop[1]]


def tail_candidates(detections: list[dict[str, Any]], cat_box: Box, limit: int) -> list[dict[str, Any]]:
    margin = 0.05 * math.hypot(cat_box[2] - cat_box[0], cat_box[3] - cat_box[1])
    tails = [
        d
        for d in detections
        if "tail" in d["label"]
        and d["score"] >= MIN_TAIL_SCORE
        and _centre_inside(d["box"], cat_box, margin)
        and _area(d["box"]) <= MAX_TAIL_TO_CAT_AREA * _area(cat_box)
    ]
    tails.sort(key=lambda d: -d["score"])
    # drop near-duplicates of a stronger box
    kept: list[dict[str, Any]] = []
    for d in tails:
        if all(_iou(d["box"], k["box"]) < 0.7 for k in kept):
            kept.append(d)
        if len(kept) == limit:
            break
    return kept


def looks_like_paw(probs: dict[str, float]) -> bool:
    """The crop-check refusal rule. ``probs`` are independent sigmoid scores keyed by
    the short class name."""
    return probs["paw"] >= MIN_PAW_TO_REFUSE and probs["paw"] > probs["tail"]


def viterbi(
    frames: list[list[dict[str, Any]]],
    diagonals: list[float],
    emission_scale: float = 1.0,
) -> list[int | None]:
    """Choose one candidate (index) or None per frame.

    ``frames[t]`` is the list of surviving candidates on frame t, each with ``score`` and
    ``box``; ``diagonals[t]`` is that frame's cat-box diagonal (or a frame-size fallback
    when there is no cat). Returns the chosen candidate index per frame, None for the
    "no tail" state.
    """
    n = len(frames)
    if n == 0:
        return []

    def centre(b: Box) -> tuple[float, float]:
        return ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)

    # state 0 = none, states 1..k = candidates
    best: list[list[float]] = []
    back: list[list[int]] = []
    for t in range(n):
        states = 1 + len(frames[t])
        emis = [NONE_EMISSION * emission_scale] + [c["score"] * emission_scale for c in frames[t]]
        cur = [-math.inf] * states
        prev_idx = [0] * states
        if t == 0:
            cur = emis[:]
        else:
            prev_states = 1 + len(frames[t - 1])
            for s in range(states):
                for p in range(prev_states):
                    if s == 0 and p == 0:
                        trans = 0.0
                    elif s == 0 or p == 0:
                        trans = -NONE_SWITCH_COST
                    else:
                        a = centre(frames[t - 1][p - 1]["box"])
                        b = centre(frames[t][s - 1]["box"])
                        d = math.hypot(a[0] - b[0], a[1] - b[1]) / max(diagonals[t], 1.0)
                        trans = -MOVE_WEIGHT * d
                    value = best[t - 1][p] + trans + emis[s]
                    if value > cur[s]:
                        cur[s] = value
                        prev_idx[s] = p
        best.append(cur)
        back.append(prev_idx)

    path = [0] * n
    path[-1] = int(np.argmax(best[-1]))
    for t in range(n - 1, 0, -1):
        path[t - 1] = back[t][path[t]]
    return [None if s == 0 else s - 1 for s in path]


def _load_models(device: str, detector_id: str = DETECTOR_ID, classifier_id: str = CLASSIFIER_ID) -> dict[str, Any]:
    import torch
    from transformers import AutoModel, AutoModelForZeroShotObjectDetection, AutoProcessor

    try:
        from sam2.sam2_image_predictor import SAM2ImagePredictor
    except ImportError as exception:
        raise RuntimeError("SAM2 is required for grounded tail segmentation") from exception

    torch.set_grad_enabled(False)
    return {
        "det_processor": AutoProcessor.from_pretrained(detector_id),
        "detector": AutoModelForZeroShotObjectDetection.from_pretrained(detector_id).to(device).eval(),
        "clf_processor": AutoProcessor.from_pretrained(classifier_id),
        "classifier": AutoModel.from_pretrained(classifier_id).to(device).eval(),
        "predictor": SAM2ImagePredictor.from_pretrained("facebook/sam2.1-hiera-tiny", device=device),
        "detector_id": detector_id,
        "classifier_id": classifier_id,
    }


def _crop_probs(models: dict[str, Any], image: Image.Image, box: Box, device: str) -> dict[str, float]:
    import torch

    crop = image.crop(tuple(pad_box(box, CROP_CHECK_PAD, image.width, image.height)))
    inputs = models["clf_processor"](text=CROP_TEXTS, images=crop, padding="max_length", return_tensors="pt").to(device)
    logits = models["classifier"](**inputs).logits_per_image[0]
    probs = torch.sigmoid(logits).detach().cpu().numpy().tolist()
    keys = ["tail", "paw", "leg", "face", "belly", "floor"]
    return {k: float(v) for k, v in zip(keys, probs)}


def _render_overlay(image: Image.Image, mask: np.ndarray | None, samples, cat, tail, probs, label: str, output_path: Path) -> None:
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
        text = f"tail {tail['score']:.2f}"
        if probs:
            text += f"  siglip tail {probs['tail']:.2f} paw {probs['paw']:.2f}"
        draw.text((tail["box"][0] + 4, tail["box"][1] + 4), text, fill=(0, 255, 255, 255))
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
    zoom: bool = False,
    crop_check: bool = True,
    temporal: bool = True,
    detector_id: str = DETECTOR_ID,
    classifier_id: str = CLASSIFIER_ID,
    time_scale: bool = False,
) -> dict[str, Any]:
    manifest = json.loads(frames_manifest.read_text(encoding="utf-8"))
    frame_interval_s = 1.0 / float(manifest.get("sampling", {}).get("fps") or (1.0 / REFERENCE_INTERVAL_S))
    emission_scale = (frame_interval_s / REFERENCE_INTERVAL_S) if time_scale else 1.0
    clip_id = clip_id or manifest["clip_id"]
    body_frames: dict[int, dict[str, Any]] = {}
    if body_json and body_json.exists():
        body_frames = {int(f["frame_index"]): f for f in json.loads(body_json.read_text(encoding="utf-8"))["frames"]}
    models = _load_models(device, detector_id, classifier_id)
    predictor = models["predictor"]

    # Pass 1: detection (and crop check) on every frame, collecting candidates.
    per_frame: list[dict[str, Any]] = []
    for frame in manifest["frames"]:
        index = int(frame["frame_index"])
        image = Image.open(frames_dir / frame["file"]).convert("RGB")
        body = body_frames.get(index, {})
        kps = {
            kp["name"]: (float(kp["x_px"]), float(kp["y_px"]))
            for kp in body.get("keypoints") or []
            if float(kp["score"]) >= KEYPOINT_SCORE_THRESHOLD
        }
        full = _detect(models["det_processor"], models["detector"], image, device)
        cat = pick_cat_box(full, body.get("bbox_xyxy"))
        record: dict[str, Any] = {"frame_index": index, "file": frame["file"], "cat": cat, "full_frame_detections": full}
        candidates: list[dict[str, Any]] = []
        if cat is not None:
            if zoom:
                crop_box = pad_box(cat["box"], CROP_PAD, image.width, image.height)
                crop_dets = _detect(models["det_processor"], models["detector"], image.crop(tuple(int(round(v)) for v in crop_box)), device)
                for d in crop_dets:
                    d["box"] = map_box_from_crop(d["box"], [int(round(v)) for v in crop_box])
                    d["from"] = "crop"
                record["crop_box"] = crop_box
                pool = crop_dets
            else:
                for d in full:
                    d["from"] = "full"
                pool = full
            candidates = tail_candidates(pool, cat["box"], CANDIDATES_PER_FRAME)
            if crop_check:
                for c in candidates:
                    c["crop_probs"] = _crop_probs(models, image, c["box"], device)
                    c["looks_like_paw"] = looks_like_paw(c["crop_probs"])
        record["candidates"] = candidates
        record["kps"] = kps
        record["image_size"] = [image.width, image.height]
        per_frame.append(record)

    # Pass 2: choose per frame.
    surviving = [[c for c in r["candidates"] if not c.get("looks_like_paw")] for r in per_frame]
    diagonals = [
        math.hypot(r["cat"]["box"][2] - r["cat"]["box"][0], r["cat"]["box"][3] - r["cat"]["box"][1])
        if r["cat"]
        else math.hypot(*r["image_size"])
        for r in per_frame
    ]
    if temporal:
        choice = viterbi(surviving, diagonals, emission_scale)
    else:
        choice = [0 if s else None for s in surviving]

    # Pass 3: segment the chosen boxes.
    frames_out: list[dict[str, Any]] = []
    status_counts: dict[str, int] = {}
    for r, cands, pick in zip(per_frame, surviving, choice):
        record = {k: v for k, v in r.items() if k not in ("kps", "full_frame_detections")}
        record["n_candidates"] = len(r["candidates"])
        record["n_after_crop_check"] = len(cands)
        tail = cands[pick] if pick is not None else None
        record["tail"] = tail
        mask = samples = None
        if r["cat"] is None:
            record["status"] = "no_cat"
        elif not r["candidates"]:
            record["status"] = "no_tail_box"
        elif not cands:
            record["status"] = "all_look_like_paw"
        elif tail is None:
            record["status"] = "temporal_none"
        else:
            image = Image.open(frames_dir / r["file"]).convert("RGB")
            predictor.set_image(np.asarray(image))
            masks, scores, _ = predictor.predict(box=np.array(tail["box"], dtype=np.float32), multimask_output=True)
            best = int(np.argmax(np.asarray(scores).reshape(-1)))
            mask = np.asarray(masks)[best].astype(bool)
            x0, y0, x1, y1 = (int(round(v)) for v in tail["box"])
            clipped = np.zeros_like(mask)
            clipped[max(0, y0) : y1 + 1, max(0, x0) : x1 + 1] = mask[max(0, y0) : y1 + 1, max(0, x0) : x1 + 1]
            mask = clipped
            record["mask_area_px"] = int(mask.sum())
            record["limb_keypoints_inside"] = keypoints_inside(mask, r["kps"], LIMB_NAMES) if mask.any() else []
            record["head_keypoints_inside"] = keypoints_inside(mask, r["kps"], HEAD_NAMES) if mask.any() else []
            if not mask.any():
                record["status"] = "empty_mask"
                mask = None
            else:
                try:
                    root = r["kps"].get(ROOT_NAME)
                    samples = mask_to_tail_samples(
                        mask,
                        base_xy=base_point(mask, root, r["cat"]["box"]),
                        sample_count=sample_count,
                        provenance="grounding_dino_zoom_siglip_viterbi_sam2_mask_to_skeleton_v1",
                    )
                    cat_masks, cat_scores, _ = predictor.predict(box=np.array(r["cat"]["box"], dtype=np.float32), multimask_output=True)
                    cat_mask = np.asarray(cat_masks)[int(np.argmax(np.asarray(cat_scores).reshape(-1)))].astype(bool)
                    record["geometry"] = geometry_features(mask, cat_mask, r["cat"]["box"], samples)
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
                    image, mask, samples, r["cat"], tail, tail.get("crop_probs"),
                    f"{clip_id} f{r['frame_index']:03d} tail_grounded_v1 {tail['score']:.2f}",
                    output_dir / "overlays" / r["file"],
                )
        status_counts[record["status"]] = status_counts.get(record["status"], 0) + 1
        frames_out.append(record)

    payload = {
        "schema_version": "0.1.0",
        "clip_id": clip_id,
        "method": "tail_grounded_v1",
        "models": {
            "detector": detector_id,
            "prompt": "cat. tail.",
            "crop_classifier": classifier_id,
            "crop_texts": CROP_TEXTS,
            "segmenter": "facebook/sam2.1-hiera-tiny",
            "device": device,
        },
        "options": {
            "zoom": zoom,
            "crop_pad": CROP_PAD,
            "crop_check": crop_check,
            "min_paw_to_refuse": MIN_PAW_TO_REFUSE,
            "temporal": temporal,
            "none_emission": NONE_EMISSION,
            "move_weight": MOVE_WEIGHT,
            "none_switch_cost": NONE_SWITCH_COST,
            "time_scale": time_scale,
            "frame_interval_s": frame_interval_s,
            "emission_scale": emission_scale,
            "candidates_per_frame": CANDIDATES_PER_FRAME,
            "min_cat_score": MIN_CAT_SCORE,
            "min_tail_score": MIN_TAIL_SCORE,
        },
        "evidence_tier": "S2",
        "summary": {
            "frames_total": len(frames_out),
            "frames_with_curve": status_counts.get("ok", 0),
            "status_counts": status_counts,
        },
        "frames": frames_out,
        "scientific_boundary": (
            "Boxes, masks and curves are model-derived. The crop check and the temporal pass make "
            "a paw less likely to be reported as a tail; they do not make an accepted curve correct."
        ),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "result.json").write_text(json.dumps(payload, indent=2, sort_keys=True, default=float) + "\n", encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Grounded tail v1: zoom + crop check + temporal.")
    parser.add_argument("frames_dir", type=Path)
    parser.add_argument("frames_manifest", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--body-json", type=Path)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--samples", type=int, default=24)
    parser.add_argument("--zoom", action="store_true", help="detect on a padded cat crop (hurt on the review set; off by default)")
    parser.add_argument("--no-crop-check", action="store_true")
    parser.add_argument("--no-temporal", action="store_true")
    parser.add_argument("--detector", default=DETECTOR_ID)
    parser.add_argument("--classifier", default=CLASSIFIER_ID)
    parser.add_argument("--time-scale", action="store_true", help="scale per-frame emissions by frame interval / 0.25 s")
    args = parser.parse_args()
    result = run(
        frames_dir=args.frames_dir, frames_manifest=args.frames_manifest, output_dir=args.output_dir,
        body_json=args.body_json, device=args.device, sample_count=args.samples,
        zoom=args.zoom, crop_check=not args.no_crop_check, temporal=not args.no_temporal,
        detector_id=args.detector, classifier_id=args.classifier, time_scale=args.time_scale,
    )
    print(json.dumps(result["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
