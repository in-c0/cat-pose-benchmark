"""Threshold-free structural audit of every accepted v3 output (ChatGPT pass 16).

For each accepted frame on the development clips, holdout #1 and holdout #2, recompute
the tail mask (box-prompted SAM2, as v1 does) and a whole-cat mask (SAM2 on the cat box),
and record six features: the four from ``detail.grounded_tail.geometry_features``
(inside_body_fraction, body_contact_fraction, elongation, tail_to_cat_area) plus
tail_box_area / cat_box_area and tail_mask_area / cat_box_area. Cross them with the frozen
truth verdict and, for wrong assertions, the failure class from the overrides. Report
percentiles per class, rank AUROC (TP vs FP) pooled and per set, and whether the
direction replicates. No threshold is chosen here.

    python -m detail.structural_audit --device cuda
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict

import numpy as np
from PIL import Image

from detail.grounded_tail import geometry_features
from detail.semantic_audit_mask import auroc
from detail.tail_bridge_bidir import _seed_mask
from review.common import clip_workdir, frames_dir
from review.score_truth import frame_class, judge, load_overrides, load_truth

FEATURES = ("tail_to_cat_area", "inside_body_fraction", "body_contact_fraction", "elongation", "box_ratio", "mask_over_cat_box")
SETS = {"dev1": ("frames.csv", ""), "dev2": ("holdout_frames.csv", "+holdout"), "dev3": ("holdout2_frames.csv", "+holdout2")}
CLASS_OF_PART = {"torso": "whole_cat_or_torso", "hind_leg": "paw_or_leg", "paw": "paw_or_leg", "ear": "face_edge", "other": "other"}


def failure_class(note: str, part: str) -> str:
    n = (note or "").lower()
    if "face" in n and "edge" in n or "strip" in n:
        return "face_edge"
    if "leaf" in n or "person" in n or "man's face" in n or "ground in front" in n:
        return "foreign_object"
    if "whole body" in n or "whole cat" in n or "rump" in n or "torso" in n or "body on the dog" in n:
        return "whole_cat_or_torso"
    return CLASS_OF_PART.get(part, "other")


def cat_mask_for(img_pred, image: np.ndarray, box) -> np.ndarray:
    img_pred.set_image(image)
    masks, scores, _ = img_pred.predict(box=np.array(box, dtype=np.float32), multimask_output=True)
    return np.asarray(masks)[int(np.argmax(np.asarray(scores).reshape(-1)))].astype(bool)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--device", default="cpu")
    p.add_argument("--method", default="tail_grounded_v3")
    a = p.parse_args()
    from sam2.sam2_image_predictor import SAM2ImagePredictor

    img_pred = SAM2ImagePredictor.from_pretrained("facebook/sam2.1-hiera-tiny", device=a.device)
    overrides = load_overrides()
    rows = []
    for set_name, (truth_file, suffix) in SETS.items():
        truth = load_truth(truth_file)
        tag = a.method + suffix
        for clip in sorted({k[0] for k in truth}):
            judged = {r["frame_index"]: r for r in judge(a.method, clip, clip, 1, truth, overrides, tag)}
            if not judged:
                continue
            res = json.loads((clip_workdir(clip) / a.method / "result.json").read_text(encoding="utf-8"))
            fd = frames_dir(clip)
            cache_img = None
            for f in res["frames"]:
                j = judged.get(f["frame_index"])
                if j is None or f["status"] not in ("ok", "propagated"):
                    continue
                t = truth[(clip, f["frame_index"])]
                fc = frame_class(t)
                if fc == "ambiguous":
                    continue
                verdict = "TP" if (fc == "visible" and j["output_status"] in ("correct", "partial")) else "FP"
                if f.get("tail") and f["tail"].get("box"):
                    tail_box = f["tail"]["box"]
                elif f.get("curve"):
                    xs = [s["x_px"] for s in f["curve"]["samples"]]
                    ys = [s["y_px"] for s in f["curve"]["samples"]]
                    tail_box = [min(xs), min(ys), max(xs), max(ys)]
                else:
                    continue
                cat = f.get("cat")
                if not cat:
                    continue
                image = np.asarray(Image.open(fd / f["file"]).convert("RGB"))
                tail_mask = _seed_mask(img_pred, fd, {**f, "tail": {"box": tail_box}})
                cat_mask = cat_mask_for(img_pred, image, cat["box"])
                samples = f["curve"]["samples"] if f.get("curve") else None
                feats = geometry_features(tail_mask, cat_mask, cat["box"], samples)
                cb = max((cat["box"][2] - cat["box"][0]) * (cat["box"][3] - cat["box"][1]), 1.0)
                feats["box_ratio"] = (tail_box[2] - tail_box[0]) * (tail_box[3] - tail_box[1]) / cb
                feats["mask_over_cat_box"] = float(tail_mask.sum()) / cb
                rows.append({"set": set_name, "clip": clip, "frame": f["frame_index"], "verdict": verdict, "status": f["status"],
                             "failure": failure_class(j.get("note", ""), j.get("wrong_part", "")) if verdict == "FP" else "", **feats})
    out = clip_workdir("_audit") / f"structural_audit_{a.method}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rows, indent=1) + "\n", encoding="utf-8")

    def pct(v, q):
        return float(np.percentile(v, q)) if v else float("nan")

    tp = [r for r in rows if r["verdict"] == "TP"]
    fp = [r for r in rows if r["verdict"] == "FP"]
    print(f"accepted frames: TP {len(tp)} FP {len(fp)}; FP classes {dict(sorted(((k, sum(1 for r in fp if r['failure'] == k)) for k in {r['failure'] for r in fp})))}")
    for feat in FEATURES:
        tv = [r[feat] for r in tp]
        fv = [r[feat] for r in fp]
        print(f"\n{feat}: TP p05 {pct(tv, 5):.3f} p10 {pct(tv, 10):.3f} med {pct(tv, 50):.3f} p90 {pct(tv, 90):.3f} p95 {pct(tv, 95):.3f} | FP p05 {pct(fv, 5):.3f} p10 {pct(fv, 10):.3f} med {pct(fv, 50):.3f} p90 {pct(fv, 90):.3f} p95 {pct(fv, 95):.3f} | pooled AUROC(TP>FP) {auroc(tv, fv):.3f}")
        for s in SETS:
            stv = [r[feat] for r in tp if r["set"] == s]
            sfv = [r[feat] for r in fp if r["set"] == s]
            au = auroc(stv, sfv)
            print(f"   {s}: TP n {len(stv)} med {pct(stv, 50):.3f} | FP n {len(sfv)} med {pct(sfv, 50):.3f} | AUROC {au if au is None else round(au, 3)}")
        for cls in sorted({r["failure"] for r in fp}):
            cv = [r[feat] for r in fp if r["failure"] == cls]
            print(f"   FP {cls}: n {len(cv)} med {pct(cv, 50):.3f} p10 {pct(cv, 10):.3f} p90 {pct(cv, 90):.3f} AUROC vs TP {auroc(tv, cv):.3f}")


if __name__ == "__main__":
    main()
