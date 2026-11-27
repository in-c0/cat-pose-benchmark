"""Linear verifier probe on frozen SigLIP embeddings of accepted v3 crops (ChatGPT pass 18).

EXPLORATORY. The labels are the frozen-truth verdicts on every accepted v3 frame across
the 16 clips (191 true tails, 46 wrong assertions) — model-annotated, human pass pending —
so nothing here is promotable. The protocol is as the reviewer specified, and is not
changed after looking at fold results:

- representation: SigLIP image embedding of the existing v1 detector-box crop, frozen;
- classifier: L2 logistic regression, C = 1.0, no hidden layers, no feature selection;
  standardisation fitted on training clips only;
- sample weights: each clip contributes equal total weight, and within a clip each
  contiguous same-label run contributes equal weight (so 17 rump frames are one mistake);
- evaluation: exhaustive leave-two-clips-out (120 folds); per fold the rejection threshold
  is the highest that keeps >= 98 % of weighted training true positives (fixed, not tuned);
- criterion (predeclared): pooled held-out FP reduction >= 25 % with TP loss <= 2 %; the FP
  reduction must occur on >= 3 different held-out clips; no held-out clip with >= 10
  baseline TPs may lose more than 1 TP; results reported per FP class.

    python -m detail.verifier_probe --device cuda
"""

from __future__ import annotations

import argparse
import itertools
import json
from collections import defaultdict

import numpy as np
from PIL import Image

from detail.tail_probe import _embedder, embed_crop
from review.common import clip_workdir, frames_dir

TP_KEEP = 0.98
C = 1.0


def load_rows(method: str) -> list[dict]:
    return json.loads((clip_workdir("_audit") / f"structural_audit_{method}.json").read_text(encoding="utf-8"))


def embeddings(rows: list[dict], method: str, device: str) -> np.ndarray:
    processor, model = _embedder(device)
    out = []
    cache: dict[tuple[str, int], Image.Image] = {}
    results: dict[str, dict[int, dict]] = {}
    for r in rows:
        clip = r["clip"]
        if clip not in results:
            results[clip] = {f["frame_index"]: f for f in json.loads((clip_workdir(clip) / method / "result.json").read_text(encoding="utf-8"))["frames"]}
        f = results[clip][r["frame"]]
        if f.get("tail") and f["tail"].get("box"):
            box = f["tail"]["box"]
        else:
            xs = [s["x_px"] for s in f["curve"]["samples"]]
            ys = [s["y_px"] for s in f["curve"]["samples"]]
            box = [min(xs), min(ys), max(xs), max(ys)]
        key = (clip, r["frame"])
        if key not in cache:
            cache[key] = Image.open(frames_dir(clip) / f["file"]).convert("RGB")
        out.append(embed_crop(processor, model, cache[key], box, device))
    return np.stack(out)


def run_weights(rows: list[dict]) -> np.ndarray:
    """Equal total weight per clip; within a clip, equal total weight per contiguous
    same-label run (frames sorted by index)."""
    w = np.zeros(len(rows))
    by_clip: dict[str, list[int]] = defaultdict(list)
    for i, r in enumerate(rows):
        by_clip[r["clip"]].append(i)
    for clip, idx in by_clip.items():
        idx.sort(key=lambda i: rows[i]["frame"])
        runs: list[list[int]] = []
        for i in idx:
            if runs and rows[runs[-1][-1]]["verdict"] == rows[i]["verdict"] and rows[i]["frame"] == rows[runs[-1][-1]]["frame"] + 1:
                runs[-1].append(i)
            else:
                runs.append([i])
        for run in runs:
            for i in run:
                w[i] = 1.0 / len(runs) / len(run)
    return w


def main() -> None:
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler

    p = argparse.ArgumentParser()
    p.add_argument("--device", default="cpu")
    p.add_argument("--method", default="tail_grounded_v3")
    a = p.parse_args()
    rows = load_rows(a.method)
    X = embeddings(rows, a.method, a.device)
    y = np.array([1 if r["verdict"] == "TP" else 0 for r in rows])
    w = run_weights(rows)
    clips = sorted({r["clip"] for r in rows})
    clip_of = np.array([r["clip"] for r in rows])
    print(f"rows {len(rows)} (TP {int(y.sum())}, FP {int((1 - y).sum())}) across {len(clips)} clips; {len(list(itertools.combinations(clips, 2)))} folds")
    # per-frame held-out decisions accumulate over every fold the frame is held out in
    kept = defaultdict(list)  # (clip, frame) -> list of keep decisions
    for held in itertools.combinations(clips, 2):
        test = np.isin(clip_of, held)
        train = ~test
        if y[train].min() == y[train].max():
            continue
        sc = StandardScaler().fit(X[train])
        clf = LogisticRegression(C=C, max_iter=2000).fit(sc.transform(X[train]), y[train], sample_weight=w[train])
        s_train = clf.decision_function(sc.transform(X[train]))
        # highest threshold keeping >= 98 % of weighted training TPs
        tp_idx = np.where(y[train] == 1)[0]
        order = np.argsort(s_train[tp_idx])
        cum = np.cumsum(w[train][tp_idx][order]) / w[train][tp_idx].sum()
        k = int(np.searchsorted(cum, 1 - TP_KEEP, side="right"))
        thr = s_train[tp_idx][order][k] if k < len(order) else -np.inf
        s_test = clf.decision_function(sc.transform(X[test]))
        for i, s in zip(np.where(test)[0], s_test):
            kept[(rows[i]["clip"], rows[i]["frame"])].append(bool(s >= thr))
    # a frame is held out in 15 folds; take the majority decision
    decision = {k: (sum(v) > len(v) / 2) for k, v in kept.items()}
    base_tp = int(y.sum()); base_fp = int((1 - y).sum())
    tp_kept = sum(1 for r in rows if r["verdict"] == "TP" and decision[(r["clip"], r["frame"])])
    fp_kept = sum(1 for r in rows if r["verdict"] == "FP" and decision[(r["clip"], r["frame"])])
    print(f"pooled held-out: TP {base_tp} -> {tp_kept} (loss {100 * (base_tp - tp_kept) / base_tp:.1f} %), FP {base_fp} -> {fp_kept} (reduction {100 * (base_fp - fp_kept) / max(base_fp, 1):.1f} %)")
    per_clip = defaultdict(lambda: [0, 0, 0, 0])
    for r in rows:
        d = decision[(r["clip"], r["frame"])]
        c = per_clip[r["clip"]]
        if r["verdict"] == "TP":
            c[0] += 1; c[1] += int(d)
        else:
            c[2] += 1; c[3] += int(d)
    clips_with_fp_reduction = 0
    violations = []
    for clip, (tp_n, tp_k, fp_n, fp_k) in sorted(per_clip.items()):
        if fp_n and fp_k < fp_n:
            clips_with_fp_reduction += 1
        if tp_n >= 10 and tp_n - tp_k > 1:
            violations.append(clip)
        print(f"   {clip[8:28]:20s} TP {tp_n:3d} -> {tp_k:3d}   FP {fp_n:3d} -> {fp_k:3d}")
    per_class = defaultdict(lambda: [0, 0])
    for r in rows:
        if r["verdict"] == "FP":
            per_class[r["failure"]][0] += 1
            per_class[r["failure"]][1] += int(decision[(r["clip"], r["frame"])])
    for cls, (n, k) in sorted(per_class.items()):
        print(f"   FP class {cls}: {n} -> {k}")
    print(f"clips with an FP reduction: {clips_with_fp_reduction}; clips with >= 10 TP losing > 1: {violations}")
    (clip_workdir("_audit") / "verifier_probe_result.json").write_text(json.dumps({"rows": len(rows), "base_tp": base_tp, "base_fp": base_fp, "tp_kept": tp_kept, "fp_kept": fp_kept, "per_clip": per_clip, "per_class": per_class, "clips_with_fp_reduction": clips_with_fp_reduction, "violations": violations, "protocol": {"C": C, "tp_keep": TP_KEEP, "folds": "leave-two-clips-out, majority over the 15 folds a frame is held out in"}}, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
