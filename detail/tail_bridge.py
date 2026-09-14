"""Bridge short gaps in a per-frame tail result with SAM2 video propagation.

Given a per-frame result whose accepted frames carry a tail box (grounded v1), propagate
each accepted frame's mask through SAM2's video predictor into neighbouring frames that
were refused for lack of evidence (``no_cat``, ``no_tail_box``, ``temporal_none``), up to
``max_reach`` frames each way. Frames refused because every candidate looked like a paw
are never filled: the whole point of v1 was to say "no" there.

A propagated mask is accepted only if its area stays within ``area_ratio`` of the seed
mask, which catches the failure propagation is known for (the mask swallowing the body
or another cat), and only if the same SigLIP crop check v1 uses does not call its
bounding box a paw. When two seeds reach the same frame, the nearer one wins.

Statuses added: ``propagated`` (with ``propagated_from`` and ``propagated_distance``).
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw

from detail.grounded_tail import base_point
from detail.grounded_tail_v1 import CLASSIFIER_ID, _crop_probs, looks_like_paw
from detail.mask_centerline import mask_to_tail_samples

FILLABLE = {"no_cat", "no_tail_box", "temporal_none", "empty_mask", "centreline_failed"}
MAX_REACH = 1  # reach 2 recovered two more true tails and added two wrong ones (a paw, a hip) on the review set
AREA_RATIO = (0.4, 2.5)


def plan_fills(statuses: list[str], max_reach: int = MAX_REACH) -> dict[int, tuple[int, int]]:
    """For each fillable frame index, the (seed index, distance) it should be filled
    from, choosing the nearest accepted frame within reach. Pure, for tests."""
    accepted = [i for i, s in enumerate(statuses) if s == "ok"]
    plan: dict[int, tuple[int, int]] = {}
    for i, s in enumerate(statuses):
        if s not in FILLABLE:
            continue
        best = None
        for a in accepted:
            d = abs(a - i)
            if 0 < d <= max_reach and (best is None or d < best[1]):
                best = (a, d)
        if best:
            plan[i] = best
    return plan


def _mask_from_logits(logits: Any) -> np.ndarray:
    arr = logits
    if hasattr(arr, "detach"):
        arr = arr.detach().cpu().numpy()
    arr = np.asarray(arr)
    while arr.ndim > 2:
        arr = arr[0]
    return arr > 0.0


def run(*, frames_dir: Path, result_json: Path, output_dir: Path, device: str, sample_count: int, max_reach: int = MAX_REACH) -> dict[str, Any]:
    try:
        from sam2.sam2_video_predictor import SAM2VideoPredictor
    except ImportError as exception:
        raise RuntimeError("SAM2 is required for bridging") from exception

    source = json.loads(result_json.read_text(encoding="utf-8"))
    frames = source["frames"]
    statuses = [f["status"] for f in frames]
    plan = plan_fills(statuses, max_reach)
    output_dir.mkdir(parents=True, exist_ok=True)
    if plan:
        predictor = SAM2VideoPredictor.from_pretrained("facebook/sam2.1-hiera-tiny", device=device)
        image_predictor_masks: dict[int, np.ndarray] = {}
        # Rebuild each seed's mask from its box with the image predictor path of the video model.
        from sam2.sam2_image_predictor import SAM2ImagePredictor

        img_pred = SAM2ImagePredictor.from_pretrained("facebook/sam2.1-hiera-tiny", device=device)
        seeds = sorted({a for a, _ in plan.values()})
        for a in seeds:
            f = frames[a]
            image = np.asarray(Image.open(frames_dir / f["file"]).convert("RGB"))
            img_pred.set_image(image)
            masks, scores, _ = img_pred.predict(box=np.array(f["tail"]["box"], dtype=np.float32), multimask_output=True)
            m = np.asarray(masks)[int(np.argmax(np.asarray(scores).reshape(-1)))].astype(bool)
            x0, y0, x1, y1 = (int(round(v)) for v in f["tail"]["box"])
            clipped = np.zeros_like(m)
            clipped[max(0, y0) : y1 + 1, max(0, x0) : x1 + 1] = m[max(0, y0) : y1 + 1, max(0, x0) : x1 + 1]
            image_predictor_masks[a] = clipped

        from transformers import AutoModel, AutoProcessor

        clf = {"clf_processor": AutoProcessor.from_pretrained(CLASSIFIER_ID), "classifier": AutoModel.from_pretrained(CLASSIFIER_ID).to(device).eval()}
        state = predictor.init_state(video_path=str(frames_dir))
        filled: dict[int, dict[str, Any]] = {}
        by_seed: dict[int, list[int]] = {}
        for i, (a, _) in plan.items():
            by_seed.setdefault(a, []).append(i)
        for a, targets in by_seed.items():
            seed_mask = image_predictor_masks[a]
            seed_area = int(seed_mask.sum())
            for direction_targets, reverse in ((sorted(t for t in targets if t > a), False), (sorted((t for t in targets if t < a), reverse=True), True)):
                if not direction_targets:
                    continue
                predictor.reset_state(state)
                predictor.add_new_mask(inference_state=state, frame_idx=a, obj_id=1, mask=seed_mask)
                for frame_idx, _obj_ids, mask_logits in predictor.propagate_in_video(
                    state, start_frame_idx=a, max_frame_num_to_track=max_reach, reverse=reverse
                ):
                    if int(frame_idx) not in direction_targets:
                        continue
                    mask = _mask_from_logits(mask_logits)
                    area = int(mask.sum())
                    ratio = area / max(seed_area, 1)
                    probs = None
                    paw = False
                    if area > 0:
                        ys, xs = np.nonzero(mask)
                        box = [float(xs.min()), float(ys.min()), float(xs.max()), float(ys.max())]
                        probs = _crop_probs(clf, Image.open(frames_dir / frames[int(frame_idx)]["file"]).convert("RGB"), box, device)
                        paw = looks_like_paw(probs)
                    filled[int(frame_idx)] = {
                        "mask": mask,
                        "seed": a,
                        "distance": abs(int(frame_idx) - a),
                        "area_ratio": ratio,
                        "crop_probs": probs,
                        "looks_like_paw": paw,
                        "accepted": AREA_RATIO[0] <= ratio <= AREA_RATIO[1] and area > 0 and not paw,
                    }

    frames_out = []
    counts: dict[str, int] = {}
    for i, f in enumerate(frames):
        record = {k: v for k, v in f.items() if k not in ("candidates",)}
        fill = filled.get(i) if plan else None
        if fill is not None:
            record["propagated_from"] = fill["seed"]
            record["propagated_distance"] = fill["distance"]
            record["propagated_area_ratio"] = fill["area_ratio"]
            record["propagated_crop_probs"] = fill["crop_probs"]
            if fill["accepted"]:
                mask = fill["mask"]
                try:
                    seed = frames[fill["seed"]]
                    root = seed.get("root_xy")
                    samples = mask_to_tail_samples(
                        mask,
                        base_xy=(root[0], root[1]) if root else base_point(mask, None, seed["cat"]["box"]),
                        sample_count=sample_count,
                        provenance="grounded_v1_seed_sam2_video_propagated_v1",
                    )
                    record["status"] = "propagated"
                    record["curve"] = {"samples": samples}
                    record["root_xy"] = [samples[0]["x_px"], samples[0]["y_px"]]
                    record["tip_xy"] = [samples[-1]["x_px"], samples[-1]["y_px"]]
                    record["mask_area_px"] = int(mask.sum())
                    image = Image.open(frames_dir / f["file"]).convert("RGBA")
                    overlay = np.zeros((*mask.shape, 4), dtype=np.uint8)
                    overlay[mask] = (255, 120, 0, 120)
                    composed = Image.alpha_composite(image, Image.fromarray(overlay, "RGBA"))
                    draw = ImageDraw.Draw(composed)
                    curve = [(s["x_px"], s["y_px"]) for s in samples]
                    if len(curve) >= 2:
                        draw.line(curve, fill=(255, 255, 0, 255), width=4)
                    label = f"{source['clip_id']} f{i:03d} propagated from f{fill['seed']:03d}"
                    draw.rectangle((8, 8, 8 + 11 * len(label), 34), fill=(0, 0, 0, 170))
                    draw.text((14, 14), label, fill=(255, 255, 255, 255))
                    (output_dir / "overlays").mkdir(parents=True, exist_ok=True)
                    composed.convert("RGB").save(output_dir / "overlays" / f["file"], quality=90)
                except ValueError as exception:
                    record["status"] = "propagation_centreline_failed"
                    record["centreline_error"] = str(exception)
            else:
                record["status"] = "propagation_looks_like_paw" if fill["looks_like_paw"] else "propagation_rejected"
        counts[record["status"]] = counts.get(record["status"], 0) + 1
        frames_out.append(record)

    # copy the source overlays for accepted frames so the method is complete on disk
    src_overlays = result_json.parent / "overlays"
    if src_overlays.exists():
        (output_dir / "overlays").mkdir(parents=True, exist_ok=True)
        for p in src_overlays.glob("*.jpg"):
            shutil.copy2(p, output_dir / "overlays" / p.name)

    payload = {
        "schema_version": "0.1.0",
        "clip_id": source["clip_id"],
        "method": "tail_grounded_v2",
        "source_method": source["method"],
        "bridge": {"fillable_statuses": sorted(FILLABLE), "max_reach": max_reach, "area_ratio": list(AREA_RATIO)},
        "evidence_tier": "S2",
        "summary": {
            "frames_total": len(frames_out),
            "frames_with_curve": counts.get("ok", 0) + counts.get("propagated", 0),
            "status_counts": counts,
        },
        "frames": frames_out,
    }
    (output_dir / "result.json").write_text(json.dumps(payload, indent=2, sort_keys=True, default=float) + "\n", encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Bridge gaps in a grounded-v1 result with SAM2 propagation.")
    parser.add_argument("frames_dir", type=Path)
    parser.add_argument("result_json", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--samples", type=int, default=24)
    parser.add_argument("--max-reach", type=int, default=MAX_REACH)
    args = parser.parse_args()
    result = run(frames_dir=args.frames_dir, result_json=args.result_json, output_dir=args.output_dir, device=args.device, sample_count=args.samples, max_reach=args.max_reach)
    print(json.dumps(result["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
