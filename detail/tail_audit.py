"""Bidirectional consensus as an auditor of locally accepted frames (ChatGPT pass 9).

v3 fills refusals between two accepted neighbours with the intersection of their
propagated masks. This runs the same machinery the other way round: for every frame the
detector accepted locally (v1 ``ok``), drop it as an anchor, take the nearest ``ok`` frame
on each side within ``horizon`` frames, propagate both to it, and if both masks are
non-empty, their intersection is non-empty and a centreline can be extracted, REPLACE the
local mask with the consensus mask. No IoU, SigLIP or agreement threshold: consensus
either forms or it does not. Frames where it cannot form keep the local output.

The audited result set is written on top of v3 as ``tail_grounded_v3a``; every replaced
frame keeps its original box under ``audit.original_box`` and the diagnostics file lists
the per-frame observables (IoU of the two propagated masks, IoU of consensus vs local).
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
from detail.mask_centerline import mask_to_tail_samples
from detail.tail_bridge import _mask_from_logits
from detail.tail_bridge_bidir import _bbox, _seed_mask

HORIZON = 3


def anchors(ok: list[int], t: int, horizon: int) -> tuple[int | None, int | None]:
    left = max((i for i in ok if t - horizon <= i < t), default=None)
    right = min((i for i in ok if t < i <= t + horizon), default=None)
    return left, right


def run(*, frames_dir: Path, v1_json: Path, base_json: Path, output_dir: Path, device: str, sample_count: int, horizon: int = HORIZON) -> dict[str, Any]:
    from sam2.sam2_image_predictor import SAM2ImagePredictor
    from sam2.sam2_video_predictor import SAM2VideoPredictor

    v1 = json.loads(v1_json.read_text(encoding="utf-8"))
    base = json.loads(base_json.read_text(encoding="utf-8"))
    frames = v1["frames"]
    ok = [f["frame_index"] for f in frames if f["status"] == "ok" and f.get("tail")]
    predictor = SAM2VideoPredictor.from_pretrained("facebook/sam2.1-hiera-tiny", device=device)
    img_pred = SAM2ImagePredictor.from_pretrained("facebook/sam2.1-hiera-tiny", device=device)
    state = predictor.init_state(video_path=str(frames_dir))
    seed_cache: dict[int, np.ndarray] = {}

    def seed(i: int) -> np.ndarray:
        if i not in seed_cache:
            seed_cache[i] = _seed_mask(img_pred, frames_dir, frames[i])
        return seed_cache[i]

    def propagate_to(src: int, t: int) -> np.ndarray | None:
        predictor.reset_state(state)
        predictor.add_new_mask(inference_state=state, frame_idx=src, obj_id=1, mask=seed(src))
        for frame_idx, _ids, logits in predictor.propagate_in_video(state, start_frame_idx=src, max_frame_num_to_track=abs(t - src), reverse=(t < src)):
            if int(frame_idx) == t:
                return _mask_from_logits(logits)
        return None

    (output_dir / "overlays").mkdir(parents=True, exist_ok=True)
    diag: list[dict[str, Any]] = []
    replaced: dict[int, dict[str, Any]] = {}
    for t in ok:
        left, right = anchors(ok, t, horizon)
        d: dict[str, Any] = {"frame_index": t, "left": left, "right": right, "outcome": None}
        if left is None or right is None:
            d["outcome"] = "no_two_anchors"
            diag.append(d)
            continue
        ml, mr = propagate_to(left, t), propagate_to(right, t)
        if ml is None or mr is None or not ml.any() or not mr.any():
            d["outcome"] = "one_side_empty"
            diag.append(d)
            continue
        inter = np.logical_and(ml, mr)
        union = np.logical_or(ml, mr)
        d["iou_lr"] = float(inter.sum() / union.sum())
        if not inter.any():
            d["outcome"] = "intersection_empty"
            diag.append(d)
            continue
        local = seed(t)
        lu = np.logical_or(inter, local).sum()
        d["iou_consensus_local"] = float(np.logical_and(inter, local).sum() / lu) if lu else 0.0
        d["area_consensus_over_local"] = float(inter.sum() / max(int(local.sum()), 1))
        f = frames[t]
        try:
            samples = mask_to_tail_samples(inter, base_xy=tuple(f["root_xy"]) if f.get("root_xy") else base_point(inter, None, f["cat"]["box"]), sample_count=sample_count, provenance="sam2_bidir_audit_v1")
        except ValueError as e:
            d["outcome"] = "centreline_failed"
            d["error"] = str(e)
            diag.append(d)
            continue
        d["outcome"] = "replaced"
        d["consensus_box"] = _bbox(inter)
        diag.append(d)
        replaced[t] = {"status": "ok", "curve": {"samples": samples}, "root_xy": [samples[0]["x_px"], samples[0]["y_px"]], "tip_xy": [samples[-1]["x_px"], samples[-1]["y_px"]], "mask_area_px": int(inter.sum()),
                       "tail": {**f["tail"], "box": _bbox(inter)}, "audit": {"left": left, "right": right, "original_box": f["tail"]["box"], "iou_lr": d["iou_lr"], "iou_consensus_local": d["iou_consensus_local"]}}
        image = Image.open(frames_dir / f["file"]).convert("RGBA")
        ov = np.zeros((*inter.shape, 4), dtype=np.uint8)
        ov[local & ~inter] = (255, 0, 0, 90)
        ov[inter] = (0, 255, 120, 130)
        comp = Image.alpha_composite(image, Image.fromarray(ov, "RGBA"))
        dr = ImageDraw.Draw(comp)
        dr.line([(s["x_px"], s["y_px"]) for s in samples], fill=(255, 255, 0, 255), width=4)
        dr.rectangle(f["tail"]["box"], outline=(255, 0, 0, 255), width=2)
        lab = f"{v1['clip_id']} f{t:03d} audit L{left} R{right} iou_lr {d['iou_lr']:.2f} vs local {d['iou_consensus_local']:.2f}"
        dr.rectangle((8, 8, 8 + 11 * len(lab), 34), fill=(0, 0, 0, 170))
        dr.text((14, 14), lab, fill=(255, 255, 255, 255))
        comp.convert("RGB").save(output_dir / "overlays" / f["file"], quality=90)

    out_frames: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    src_overlays = base_json.parent / "overlays"
    for f in base["frames"]:
        i = f["frame_index"]
        rec = dict(f)
        if i in replaced:
            rec = {k: v for k, v in f.items() if k not in ("curve", "root_xy", "tip_xy", "mask_area_px", "tail")}
            rec.update(replaced[i])
        elif (src_overlays / f["file"]).exists():
            shutil.copy2(src_overlays / f["file"], output_dir / "overlays" / f["file"])
        counts[rec["status"]] = counts.get(rec["status"], 0) + 1
        out_frames.append(rec)
    payload = {
        "schema_version": "0.1.0", "clip_id": v1["clip_id"], "method": "tail_grounded_v3a", "base": base.get("method"),
        "audit": {"horizon": horizon, "rule": "replace local mask with L∩R consensus when both non-empty, intersection non-empty, centreline ok; else keep local", "replaced": sorted(replaced), "outcomes": {o: sum(1 for d in diag if d["outcome"] == o) for o in sorted({d["outcome"] for d in diag})}},
        "summary": {"frames_total": len(out_frames), "frames_with_curve": counts.get("ok", 0) + counts.get("propagated", 0), "status_counts": counts},
        "frames": out_frames,
    }
    (output_dir / "result.json").write_text(json.dumps(payload, indent=2, sort_keys=True, default=float) + "\n", encoding="utf-8")
    (output_dir / "audit_diag.json").write_text(json.dumps(diag, indent=2, default=float) + "\n", encoding="utf-8")
    return payload


def main() -> None:
    from review.common import clip_workdir, frames_dir, load_clips

    p = argparse.ArgumentParser()
    p.add_argument("--clip", action="append")
    p.add_argument("--device", default="cpu")
    p.add_argument("--base", default="tail_grounded_v3")
    p.add_argument("--tag", default="tail_grounded_v3a")
    p.add_argument("--horizon", type=int, default=HORIZON)
    p.add_argument("--samples", type=int, default=24)
    a = p.parse_args()
    for c in load_clips():
        if (a.clip and c["clip_id"] not in a.clip) or (not a.clip and not c.get("review", True)):
            continue
        w = clip_workdir(c["clip_id"])
        out = w / a.tag
        if out.exists():
            shutil.rmtree(out)
        r = run(frames_dir=frames_dir(c["clip_id"]), v1_json=w / "tail_grounded_v1" / "result.json", base_json=w / a.base / "result.json", output_dir=out, device=a.device, sample_count=a.samples, horizon=a.horizon)
        print(json.dumps({"clip_id": c["clip_id"], **r["audit"], **r["summary"]}))


if __name__ == "__main__":
    main()
