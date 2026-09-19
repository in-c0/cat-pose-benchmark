"""Segmentation-conditioned semantic audit (ChatGPT pass 14).

For every frame v1 accepted, recompute the SAM2 mask from the accepted tail box (the same
box-prompted image-predictor call v1 makes), take the mask's tight bounding box padded by
10 % on each side, and re-score that RGB crop with the same SigLIP model and the same six
prompts. Compare the margin tail - max(others) with the detector-box crop's margin from
``detail.semantic_audit``. No thresholds, no new prompts, no model change; an offline
separability diagnostic (rank-only AUROC of the margin for TP vs FP, before and after).

    python -m detail.semantic_audit_mask --device cuda            # dev clips
    python -m detail.semantic_audit_mask --device cuda --holdout  # holdout clips
"""

from __future__ import annotations

import argparse
import json

import numpy as np
from PIL import Image

from detail.grounded_tail_v1 import CLASSIFIER_ID, _crop_probs
from detail.semantic_audit import NEG
from detail.tail_bridge_bidir import _bbox, _seed_mask
from review.common import clip_workdir, frames_dir


def auroc(pos: list[float], neg: list[float]) -> float | None:
    if not pos or not neg:
        return None
    wins = sum((p > n) + 0.5 * (p == n) for p in pos for n in neg)
    return wins / (len(pos) * len(neg))


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--holdout", action="store_true")
    p.add_argument("--device", default="cpu")
    p.add_argument("--pad", type=float, default=0.10)
    a = p.parse_args()
    from sam2.sam2_image_predictor import SAM2ImagePredictor
    from transformers import AutoModel, AutoProcessor

    tag = "tail_grounded_v1" + ("+holdout" if a.holdout else "")
    rows = json.loads((clip_workdir("_audit") / f"semantic_audit_{tag}.json").read_text(encoding="utf-8"))
    img_pred = SAM2ImagePredictor.from_pretrained("facebook/sam2.1-hiera-tiny", device=a.device)
    clf = {"clf_processor": AutoProcessor.from_pretrained(CLASSIFIER_ID), "classifier": AutoModel.from_pretrained(CLASSIFIER_ID).to(a.device).eval()}
    results = {}
    for clip in sorted({r["clip"] for r in rows}):
        results[clip] = {f["frame_index"]: f for f in json.loads((clip_workdir(clip) / "tail_grounded_v1" / "result.json").read_text(encoding="utf-8"))["frames"]}
    out = []
    for r in rows:
        f = results[r["clip"]][r["frame"]]
        fd = frames_dir(r["clip"])
        mask = _seed_mask(img_pred, fd, f)
        b = _bbox(mask)
        rec = dict(r)
        if b is None:
            rec.update({"mask_empty": True})
            out.append(rec)
            continue
        w, h = b[2] - b[0], b[3] - b[1]
        image = Image.open(fd / f["file"]).convert("RGB")
        tight = [max(0, b[0] - a.pad * w), max(0, b[1] - a.pad * h), min(image.width, b[2] + a.pad * w), min(image.height, b[3] + a.pad * h)]
        pr = _crop_probs(clf, image, tight, a.device)
        worst = max(NEG, key=lambda k: pr.get(k, 0.0))
        rec.update({"mask_box": tight, "mask_area_frac": float(mask.sum() / max(1.0, (f["tail"]["box"][2] - f["tail"]["box"][0]) * (f["tail"]["box"][3] - f["tail"]["box"][1]))), "tail2": pr["tail"], "worst2": worst, "worst2_p": pr[worst], "margin2": pr["tail"] - pr[worst]})
        out.append(rec)
    (clip_workdir("_audit") / f"semantic_audit_mask_{tag}.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    # report
    for clip in sorted({r["clip"] for r in out}):
        sub = [r for r in out if r["clip"] == clip and "margin2" in r]
        for v in ("TP", "FP"):
            s = [r for r in sub if r["verdict"] == v]
            if not s:
                continue
            before = sum(1 for r in s if r["margin"] > 0)
            after = sum(1 for r in s if r["margin2"] > 0)
            improved = sum(1 for r in s if r["margin2"] > r["margin"])
            flips_down = sum(1 for r in s if r["margin"] > 0 and r["margin2"] <= 0)
            flips_up = sum(1 for r in s if r["margin"] <= 0 and r["margin2"] > 0)
            print(f"{clip[8:24]:16s} {v}: n {len(s)} tail-wins before {before} after {after}; margin improved on {improved}; wins->loses {flips_down}, loses->wins {flips_up}; winners after: { {k: sum(1 for r in s if r['margin2'] <= 0 and r['worst2'] == k) for k in NEG} }")
    tp = [r for r in out if r["verdict"] == "TP" and "margin2" in r]
    fp = [r for r in out if r["verdict"] == "FP" and "margin2" in r]
    print(f"AUROC(margin, TP vs FP) before {auroc([r['margin'] for r in tp], [r['margin'] for r in fp])}  after {auroc([r['margin2'] for r in tp], [r['margin2'] for r in fp])}")
    print("per-frame (holdout Larry/Taiwan and dev FPs):")
    for r in out:
        if "margin2" in r and (r["clip"].startswith("holdout") or r["verdict"] == "FP"):
            print(f"   {r['clip'][8:22]} f{r['frame']:03d} {r['verdict']:2s} before tail {r['tail']:.2f} {r['worst']} {r['worst_p']:.2f} m {r['margin']:+.2f} | after tail {r['tail2']:.2f} {r['worst2']} {r['worst2_p']:.2f} m {r['margin2']:+.2f}  mask/box {r['mask_area_frac']:.2f}")


if __name__ == "__main__":
    main()
