"""v4: contiguous-gap tracking on top of grounded v1 (ChatGPT pass 8 rule).

The unit is a contiguous run of fillable refusals in the v1 result, not "N frames from a
seed". Two cases:

A. Run bounded by an accepted frame on both sides: propagate the left seed forward and the
   right seed backward with SAM2, accept the INTERSECTION on every frame where both masks
   are non-empty, the intersection is non-empty and a centreline can be extracted. No
   maximum run length, no area gate.
B. Run bounded on one side only (clip start/end, or a hard refusal such as
   all_look_like_paw on the other side): propagate outward from the nearest accepted seed
   and accept consecutive masks while the mask is non-empty, a centreline can be extracted
   and area / seed_area < ``max_area_ratio`` (2.5, v2's blob guard). The FIRST failure
   terminates that propagation permanently; a later non-empty mask is not re-admitted.

Previous-frame IoU and the SigLIP crop probabilities are recorded as diagnostics only
(``track_diag.json``); neither is a stopping rule.
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
from detail.grounded_tail_v1 import CLASSIFIER_ID, _crop_probs
from detail.mask_centerline import mask_to_tail_samples
from detail.tail_bridge import FILLABLE, _mask_from_logits
from detail.tail_bridge_bidir import _bbox, _seed_mask

MAX_AREA_RATIO = 2.5


def runs(statuses: list[str]) -> list[dict[str, Any]]:
    """Contiguous fillable runs with their bounding accepted seeds (None when the run
    touches the clip edge or a non-fillable, non-accepted frame)."""
    out = []
    n = len(statuses)
    i = 0
    while i < n:
        if statuses[i] in FILLABLE:
            j = i
            while j + 1 < n and statuses[j + 1] in FILLABLE:
                j += 1
            left = i - 1 if i > 0 and statuses[i - 1] == "ok" else None
            right = j + 1 if j < n - 1 and statuses[j + 1] == "ok" else None
            kind = "two_sided" if left is not None and right is not None else ("one_sided" if left is not None or right is not None else "unseeded")
            out.append({"first": i, "last": j, "left": left, "right": right, "kind": kind})
            i = j + 1
        else:
            i += 1
    return out


def run(*, frames_dir: Path, v1_json: Path, output_dir: Path, device: str, sample_count: int, max_area_ratio: float = MAX_AREA_RATIO) -> dict[str, Any]:
    from sam2.sam2_image_predictor import SAM2ImagePredictor
    from sam2.sam2_video_predictor import SAM2VideoPredictor
    from transformers import AutoModel, AutoProcessor

    v1 = json.loads(v1_json.read_text(encoding="utf-8"))
    frames = v1["frames"]
    statuses = [f["status"] for f in frames]
    gaps = runs(statuses)
    predictor = SAM2VideoPredictor.from_pretrained("facebook/sam2.1-hiera-tiny", device=device)
    img_pred = SAM2ImagePredictor.from_pretrained("facebook/sam2.1-hiera-tiny", device=device)
    clf = {"clf_processor": AutoProcessor.from_pretrained(CLASSIFIER_ID), "classifier": AutoModel.from_pretrained(CLASSIFIER_ID).to(device).eval()}
    state = predictor.init_state(video_path=str(frames_dir))
    diag: list[dict[str, Any]] = []
    fills: dict[int, dict[str, Any]] = {}
    (output_dir / "overlays").mkdir(parents=True, exist_ok=True)

    def propagate(seed: int, first: int, last: int, reverse: bool) -> tuple[dict[int, np.ndarray], int]:
        sm = _seed_mask(img_pred, frames_dir, frames[seed])
        predictor.reset_state(state)
        predictor.add_new_mask(inference_state=state, frame_idx=seed, obj_id=1, mask=sm)
        masks = {}
        for frame_idx, _ids, logits in predictor.propagate_in_video(state, start_frame_idx=seed, max_frame_num_to_track=last - first + 1, reverse=reverse):
            t = int(frame_idx)
            if first <= t <= last:
                masks[t] = _mask_from_logits(logits)
        return masks, max(int(sm.sum()), 1)

    def siglip(t: int, m: np.ndarray):
        b = _bbox(m)
        return _crop_probs(clf, Image.open(frames_dir / frames[t]["file"]).convert("RGB"), b, device) if b else None

    def accept(t: int, m: np.ndarray, seed: int, how: str, extra: dict[str, Any]) -> bool:
        seed_f = frames[seed]
        try:
            samples = mask_to_tail_samples(m, base_xy=tuple(seed_f["root_xy"]) if seed_f.get("root_xy") else base_point(m, None, seed_f["cat"]["box"]), sample_count=sample_count, provenance=f"sam2_track_{how}_v4")
        except ValueError as e:
            extra["stop"] = "centreline"
            extra["error"] = str(e)
            return False
        track = {"how": how, "seed": seed, **{k: v for k, v in extra.items() if k in ("distance", "iou_lr", "area_ratio")}}
        fills[t] = {"status": "propagated", "curve": {"samples": samples}, "root_xy": [samples[0]["x_px"], samples[0]["y_px"]], "tip_xy": [samples[-1]["x_px"], samples[-1]["y_px"]], "mask_area_px": int(m.sum()), "track": track}
        image = Image.open(frames_dir / frames[t]["file"]).convert("RGBA")
        ov = np.zeros((*m.shape, 4), dtype=np.uint8)
        ov[m] = (255, 160, 0, 120)
        comp = Image.alpha_composite(image, Image.fromarray(ov, "RGBA"))
        dr = ImageDraw.Draw(comp)
        dr.line([(s["x_px"], s["y_px"]) for s in samples], fill=(255, 255, 0, 255), width=4)
        lab = f"{v1['clip_id']} f{t:03d} v4 {how} seed f{seed:03d}"
        dr.rectangle((8, 8, 8 + 11 * len(lab), 34), fill=(0, 0, 0, 170))
        dr.text((14, 14), lab, fill=(255, 255, 255, 255))
        comp.convert("RGB").save(output_dir / "overlays" / frames[t]["file"], quality=90)
        return True

    for g in gaps:
        first, last = g["first"], g["last"]
        if g["kind"] == "two_sided":
            ml, al = propagate(g["left"], first, last, False)
            mr, ar = propagate(g["right"], first, last, True)
            for t in range(first, last + 1):
                a, b = ml.get(t), mr.get(t)
                d: dict[str, Any] = {"frame_index": t, "kind": "two_sided", "left": g["left"], "right": g["right"], "stop": None}
                if a is None or b is None or not a.any() or not b.any():
                    d["stop"] = "one_side_empty"
                    diag.append(d)
                    continue
                inter = np.logical_and(a, b)
                union = np.logical_or(a, b)
                d["iou_lr"] = float(inter.sum() / union.sum())
                d["area_ratio_left"] = a.sum() / al
                d["area_ratio_right"] = b.sum() / ar
                if not inter.any():
                    d["stop"] = "intersection_empty"
                    diag.append(d)
                    continue
                d["siglip"] = siglip(t, inter)
                accept(t, inter, g["left"], "intersection", d)
                diag.append(d)
        elif g["kind"] == "one_sided":
            seed = g["left"] if g["left"] is not None else g["right"]
            reverse = g["left"] is None
            masks, sa = propagate(seed, first, last, reverse)
            order = range(first, last + 1) if not reverse else range(last, first - 1, -1)
            prev = None
            for t in order:
                m = masks.get(t)
                d = {"frame_index": t, "kind": "one_sided", "seed": seed, "distance": abs(t - seed), "stop": None}
                if m is None or not m.any():
                    d["stop"] = "empty"
                    diag.append(d)
                    break
                d["area_ratio"] = m.sum() / sa
                if prev is not None:
                    u = np.logical_or(m, prev).sum()
                    d["iou_prev"] = float(np.logical_and(m, prev).sum() / u) if u else 0.0
                d["siglip"] = siglip(t, m)
                if d["area_ratio"] >= max_area_ratio:
                    d["stop"] = "area_blowup"
                    diag.append(d)
                    break
                ok = accept(t, m, seed, "forward" if not reverse else "back", d)
                diag.append(d)
                if not ok:
                    break
                prev = m

    out_frames: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    src_overlays = v1_json.parent / "overlays"
    for i, f in enumerate(frames):
        rec = dict(f)
        if i in fills:
            rec = {k: v for k, v in f.items() if k not in ("curve", "root_xy", "tip_xy", "mask_area_px")}
            rec.update(fills[i])
        elif rec["status"] == "ok" and (src_overlays / f["file"]).exists():
            shutil.copy2(src_overlays / f["file"], output_dir / "overlays" / f["file"])
        counts[rec["status"]] = counts.get(rec["status"], 0) + 1
        out_frames.append(rec)
    payload = {
        "schema_version": "0.1.0", "clip_id": v1["clip_id"], "method": "tail_grounded_v4", "base": "tail_grounded_v1",
        "rules": {"two_sided": "intersection, non-empty both sides, centreline; no length limit", "one_sided": f"non-empty, centreline, area/seed < {max_area_ratio}; first failure terminates", "diagnostics_only": ["iou_prev", "siglip"]},
        "gaps": gaps,
        "summary": {"frames_total": len(frames), "frames_with_curve": counts.get("ok", 0) + counts.get("propagated", 0), "status_counts": counts},
        "frames": out_frames,
    }
    (output_dir / "result.json").write_text(json.dumps(payload, indent=2, sort_keys=True, default=float) + "\n", encoding="utf-8")
    (output_dir / "track_diag.json").write_text(json.dumps(diag, indent=2, default=float) + "\n", encoding="utf-8")
    return payload


def main() -> None:
    from review.common import clip_workdir, frames_dir, load_clips

    p = argparse.ArgumentParser()
    p.add_argument("--clip", action="append")
    p.add_argument("--device", default="cpu")
    p.add_argument("--tag", default="tail_grounded_v4")
    p.add_argument("--max-area", type=float, default=MAX_AREA_RATIO)
    p.add_argument("--samples", type=int, default=24)
    a = p.parse_args()
    for c in load_clips():
        if (a.clip and c["clip_id"] not in a.clip) or (not a.clip and not c.get("review", True)):
            continue
        w = clip_workdir(c["clip_id"])
        out = w / a.tag
        if out.exists():
            shutil.rmtree(out)
        r = run(frames_dir=frames_dir(c["clip_id"]), v1_json=w / "tail_grounded_v1" / "result.json", output_dir=out, device=a.device, sample_count=a.samples, max_area_ratio=a.max_area)
        print(json.dumps({"clip_id": c["clip_id"], "gaps": r["gaps"], **r["summary"]}))


if __name__ == "__main__":
    main()
