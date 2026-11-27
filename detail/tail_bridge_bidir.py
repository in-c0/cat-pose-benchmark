"""Bidirectional-consensus bridging of short refusal gaps in a grounded-v1 result.

For every gap of refused frames (any status except a paw refusal) of length <= ``max_gap``
that has an accepted frame on both sides, propagate the left seed's mask forward and the
right seed's mask backward with SAM2's video predictor, and record for each frame in the
gap: IoU(left, right), each mask's area ratio to its seed, and the SigLIP paw check on
each mask's bounding box. Four fixed outputs are written as separate result sets, each
starting from the v2 (reach-1, one-sided) result and replacing the gap frames:

    left, right, intersection, union

so that each can be scored against frozen truth before any agreement threshold is chosen.
One-sided gaps keep whatever v2 did.
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
from detail.tail_bridge import FILLABLE, _mask_from_logits

VARIANTS = ("left", "right", "intersection", "union")


def two_sided_gaps(statuses: list[str], max_gap: int) -> list[tuple[int, int, int, int]]:
    """(left_seed, first, last, right_seed) for each run of fillable frames of length <=
    max_gap with 'ok' frames immediately on both sides."""
    gaps = []
    n = len(statuses)
    i = 0
    while i < n:
        if statuses[i] in FILLABLE:
            j = i
            while j + 1 < n and statuses[j + 1] in FILLABLE:
                j += 1
            if i > 0 and j < n - 1 and statuses[i - 1] == "ok" and statuses[j + 1] == "ok" and (j - i + 1) <= max_gap:
                gaps.append((i - 1, i, j, j + 1))
            i = j + 1
        else:
            i += 1
    return gaps


def _seed_mask(img_pred, frames_dir: Path, frame: dict[str, Any]) -> np.ndarray:
    image = np.asarray(Image.open(frames_dir / frame["file"]).convert("RGB"))
    img_pred.set_image(image)
    masks, scores, _ = img_pred.predict(box=np.array(frame["tail"]["box"], dtype=np.float32), multimask_output=True)
    m = np.asarray(masks)[int(np.argmax(np.asarray(scores).reshape(-1)))].astype(bool)
    x0, y0, x1, y1 = (int(round(v)) for v in frame["tail"]["box"])
    out = np.zeros_like(m)
    out[max(0, y0) : y1 + 1, max(0, x0) : x1 + 1] = m[max(0, y0) : y1 + 1, max(0, x0) : x1 + 1]
    return out


def _bbox(mask: np.ndarray) -> list[float] | None:
    if not mask.any():
        return None
    ys, xs = np.nonzero(mask)
    return [float(xs.min()), float(ys.min()), float(xs.max()), float(ys.max())]


def run(*, frames_dir: Path, v1_json: Path, v2_json: Path, output_root: Path, device: str, sample_count: int, max_gap: int, tag_prefix: str) -> dict[str, Any]:
    from sam2.sam2_image_predictor import SAM2ImagePredictor
    from sam2.sam2_video_predictor import SAM2VideoPredictor
    from transformers import AutoModel, AutoProcessor

    v1 = json.loads(v1_json.read_text(encoding="utf-8"))
    v2 = json.loads(v2_json.read_text(encoding="utf-8"))
    frames = v1["frames"]
    statuses = [f["status"] for f in frames]
    gaps = two_sided_gaps(statuses, max_gap)
    diag: dict[str, Any] = {"clip_id": v1["clip_id"], "max_gap": max_gap, "gaps": [], "per_frame": []}
    per_variant: dict[str, dict[int, dict[str, Any]]] = {v: {} for v in VARIANTS}
    if gaps:
        predictor = SAM2VideoPredictor.from_pretrained("facebook/sam2.1-hiera-tiny", device=device)
        img_pred = SAM2ImagePredictor.from_pretrained("facebook/sam2.1-hiera-tiny", device=device)
        clf = {"clf_processor": AutoProcessor.from_pretrained(CLASSIFIER_ID), "classifier": AutoModel.from_pretrained(CLASSIFIER_ID).to(device).eval()}
        state = predictor.init_state(video_path=str(frames_dir))
        for left, first, last, right in gaps:
            diag["gaps"].append({"left_seed": left, "first": first, "last": last, "right_seed": right})
            masks: dict[str, dict[int, np.ndarray]] = {"left": {}, "right": {}}
            areas = {}
            for side, seed, reverse in (("left", left, False), ("right", right, True)):
                seed_mask = _seed_mask(img_pred, frames_dir, frames[seed])
                areas[side] = int(seed_mask.sum())
                predictor.reset_state(state)
                predictor.add_new_mask(inference_state=state, frame_idx=seed, obj_id=1, mask=seed_mask)
                for frame_idx, _ids, logits in predictor.propagate_in_video(state, start_frame_idx=seed, max_frame_num_to_track=max_gap, reverse=reverse):
                    if first <= int(frame_idx) <= last:
                        masks[side][int(frame_idx)] = _mask_from_logits(logits)
            for t in range(first, last + 1):
                ml, mr = masks["left"].get(t), masks["right"].get(t)
                if ml is None or mr is None:
                    continue
                inter = np.logical_and(ml, mr); union = np.logical_or(ml, mr)
                iou = float(inter.sum() / union.sum()) if union.sum() else 0.0
                image = Image.open(frames_dir / frames[t]["file"]).convert("RGB")
                rec = {"frame_index": t, "iou": iou, "area_ratio_left": ml.sum() / max(areas["left"], 1), "area_ratio_right": mr.sum() / max(areas["right"], 1)}
                for side, m in (("left", ml), ("right", mr)):
                    b = _bbox(m)
                    rec[f"siglip_{side}"] = _crop_probs(clf, image, b, device) if b else None
                    rec[f"paw_{side}"] = looks_like_paw(rec[f"siglip_{side}"]) if b else None
                diag["per_frame"].append(rec)
                for name, m in (("left", ml), ("right", mr), ("intersection", inter), ("union", union)):
                    if not m.any():
                        per_variant[name][t] = {"status": "bidir_empty"}
                        continue
                    seed = frames[left]
                    try:
                        samples = mask_to_tail_samples(m, base_xy=tuple(seed["root_xy"]) if seed.get("root_xy") else base_point(m, None, seed["cat"]["box"]), sample_count=sample_count, provenance=f"bidir_{name}_v1")
                    except ValueError as e:
                        per_variant[name][t] = {"status": "bidir_centreline_failed", "error": str(e)}
                        continue
                    per_variant[name][t] = {"status": "propagated", "curve": {"samples": samples}, "root_xy": [samples[0]["x_px"], samples[0]["y_px"]], "tip_xy": [samples[-1]["x_px"], samples[-1]["y_px"]], "mask_area_px": int(m.sum()), "bidir": name, "iou_lr": iou}
                    # overlay
                    im = image.convert("RGBA")
                    ov = np.zeros((*m.shape, 4), dtype=np.uint8); ov[m] = (0, 200, 255, 120)
                    comp = Image.alpha_composite(im, Image.fromarray(ov, "RGBA")); dr = ImageDraw.Draw(comp)
                    dr.line([(s["x_px"], s["y_px"]) for s in samples], fill=(255, 255, 0, 255), width=4)
                    lab = f"{v1['clip_id']} f{t:03d} bidir {name} iou {iou:.2f}"
                    dr.rectangle((8, 8, 8 + 11 * len(lab), 34), fill=(0, 0, 0, 170)); dr.text((14, 14), lab, fill=(255, 255, 255, 255))
                    d = output_root / f"{tag_prefix}_{name}" / "overlays"; d.mkdir(parents=True, exist_ok=True)
                    comp.convert("RGB").save(d / frames[t]["file"], quality=90)
    # write the four result sets on top of v2
    summaries = {}
    for name in VARIANTS:
        out_frames = []
        counts: dict[str, int] = {}
        for f in v2["frames"]:
            rec = dict(f)
            rep = per_variant[name].get(f["frame_index"])
            if rep is not None:
                rec = {k: v for k, v in f.items() if k not in ("curve", "root_xy", "tip_xy", "mask_area_px")}
                rec.update(rep)
            counts[rec["status"]] = counts.get(rec["status"], 0) + 1
            out_frames.append(rec)
        d = output_root / f"{tag_prefix}_{name}"; d.mkdir(parents=True, exist_ok=True)
        payload = {"schema_version": "0.1.0", "clip_id": v1["clip_id"], "method": f"{tag_prefix}_{name}", "base": "tail_grounded_v2", "bidir_variant": name, "max_gap": max_gap, "summary": {"frames_total": len(out_frames), "frames_with_curve": counts.get("ok", 0) + counts.get("propagated", 0), "status_counts": counts}, "frames": out_frames}
        (d / "result.json").write_text(json.dumps(payload, indent=2, sort_keys=True, default=float) + "\n", encoding="utf-8")
        # keep v2 overlays for the untouched frames
        src = v2_json.parent / "overlays"
        if src.exists():
            (d / "overlays").mkdir(exist_ok=True)
            for p in src.glob("*.jpg"):
                if not (d / "overlays" / p.name).exists():
                    shutil.copy2(p, d / "overlays" / p.name)
        summaries[name] = payload["summary"]["status_counts"]
    (output_root / f"{tag_prefix}_diag.json").write_text(json.dumps(diag, indent=2, default=float) + "\n", encoding="utf-8")
    return {"gaps": diag["gaps"], "per_frame": diag["per_frame"], "summaries": summaries}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--clip", action="append", required=True)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--max-gap", type=int, default=2)
    parser.add_argument("--samples", type=int, default=24)
    parser.add_argument("--tag", default="v2b")
    args = parser.parse_args()
    from review.common import clip_workdir, frames_dir
    for clip in args.clip:
        work = clip_workdir(clip)
        r = run(frames_dir=frames_dir(clip), v1_json=work / "tail_grounded_v1" / "result.json", v2_json=work / "tail_grounded_v2" / "result.json", output_root=work, device=args.device, sample_count=args.samples, max_gap=args.max_gap, tag_prefix=args.tag)
        print(clip, "gaps", r["gaps"])
        for pf in r["per_frame"]:
            print("  f%03d iou %.2f areaL %.2f areaR %.2f pawL %s pawR %s" % (pf["frame_index"], pf["iou"], pf["area_ratio_left"], pf["area_ratio_right"], pf["paw_left"], pf["paw_right"]))


if __name__ == "__main__":
    main()
