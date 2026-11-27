"""A learned tail-vs-not-tail probe on SigLIP crop embeddings, trained on pseudo-labels.

The crop check in ``grounded_tail_v1`` is zero-shot: SigLIP compares the crop to six
sentences. This module replaces the sentences with a logistic-regression probe trained
on crops the pipeline itself labelled: positives are the tail boxes the v1 method
accepted (precision about 0.95 on the review set), negatives are the candidates the
zero-shot check refused as paws plus every other candidate on frames where v1 refused.
That makes it self-training on model output, not human labels, and it is evaluated on
held-out clips for exactly that reason.

    python -m detail.tail_probe build  --clip <dense clip id> ...  --output detail/models/tail_probe_v0.json
    python -m detail.tail_probe score  --probe detail/models/tail_probe_v0.json  crop.jpg

The saved probe is a JSON file with the SigLIP model id, the weight vector and bias, so it
loads without sklearn.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from detail.grounded_tail_v1 import CLASSIFIER_ID, CROP_CHECK_PAD, pad_box

REPO_ROOT = Path(__file__).resolve().parents[1]


def _embedder(device: str, model_id: str = CLASSIFIER_ID) -> tuple[Any, Any]:
    import torch
    from transformers import AutoModel, AutoProcessor

    torch.set_grad_enabled(False)
    return AutoProcessor.from_pretrained(model_id), AutoModel.from_pretrained(model_id).to(device).eval()


def embed_crop(processor: Any, model: Any, image: Image.Image, box: list[float], device: str) -> np.ndarray:
    crop = image.crop(tuple(pad_box(box, CROP_CHECK_PAD, image.width, image.height)))
    inputs = processor(images=crop, return_tensors="pt").to(device)
    feats = model.get_image_features(**inputs)
    if hasattr(feats, "pooler_output"):  # transformers >= 5 returns a model output
        feats = feats.pooler_output
    feats = feats / feats.norm(dim=-1, keepdim=True)
    return feats[0].detach().cpu().numpy().astype(np.float32)


def harvest(result_json: Path, frames_dir: Path) -> tuple[list[tuple[str, list[float]]], list[tuple[str, list[float]]]]:
    """(positives, negatives) as (frame file, box) from a grounded-v1 result."""
    result = json.loads(result_json.read_text(encoding="utf-8"))
    positives: list[tuple[str, list[float]]] = []
    negatives: list[tuple[str, list[float]]] = []
    for f in result["frames"]:
        cands = f.get("candidates") or []
        if f["status"] == "ok" and f.get("tail"):
            positives.append((f["file"], f["tail"]["box"]))
            for c in cands:
                if c["box"] != f["tail"]["box"]:
                    negatives.append((f["file"], c["box"]))
        else:
            for c in cands:
                negatives.append((f["file"], c["box"]))
    return positives, negatives


def train(features: np.ndarray, labels: np.ndarray) -> dict[str, Any]:
    from sklearn.linear_model import LogisticRegression

    clf = LogisticRegression(C=1.0, class_weight="balanced", max_iter=2000)
    clf.fit(features, labels)
    return {"weights": clf.coef_[0].astype(float).tolist(), "bias": float(clf.intercept_[0])}


def probability(probe: dict[str, Any], embedding: np.ndarray) -> float:
    z = float(np.dot(np.asarray(probe["weights"], dtype=np.float32), embedding) + probe["bias"])
    return float(1.0 / (1.0 + np.exp(-z)))


def build(clip_ids: list[str], output: Path, device: str) -> dict[str, Any]:
    from review.common import clip_workdir, frames_dir

    processor, model = _embedder(device)
    feats: list[np.ndarray] = []
    labels: list[int] = []
    counts = {}
    for clip_id in clip_ids:
        work = clip_workdir(clip_id)
        pos, neg = harvest(work / "tail_grounded_v1" / "result.json", frames_dir(clip_id))
        counts[clip_id] = {"positives": len(pos), "negatives": len(neg)}
        cache: dict[str, Image.Image] = {}
        for label, items in ((1, pos), (0, neg)):
            for file, box in items:
                if file not in cache:
                    cache[file] = Image.open(frames_dir(clip_id) / file).convert("RGB")
                feats.append(embed_crop(processor, model, cache[file], box, device))
                labels.append(label)
    X = np.stack(feats)
    y = np.asarray(labels)
    params = train(X, y)
    # leave-one-clip-out sanity check, so the number reported is not training accuracy
    loco = {}
    if len(clip_ids) > 1:
        offsets = []
        start = 0
        for clip_id in clip_ids:
            n = counts[clip_id]["positives"] + counts[clip_id]["negatives"]
            offsets.append((clip_id, start, start + n))
            start += n
        for clip_id, a, b in offsets:
            mask = np.ones(len(y), dtype=bool)
            mask[a:b] = False
            p = train(X[mask], y[mask])
            pred = np.array([probability(p, x) >= 0.5 for x in X[a:b]])
            truth = y[a:b] == 1
            tp = int((pred & truth).sum()); fp = int((pred & ~truth).sum()); fn = int((~pred & truth).sum())
            loco[clip_id] = {"precision": tp / max(tp + fp, 1), "recall": tp / max(tp + fn, 1), "n": int(b - a)}
    probe = {
        "schema_version": "0.1.0",
        "embedder": CLASSIFIER_ID,
        "crop_pad": CROP_CHECK_PAD,
        "trained_on": counts,
        "n_positive": int(y.sum()),
        "n_negative": int((y == 0).sum()),
        "leave_one_clip_out": loco,
        "label_source": "grounded_tail_v1 accepted boxes (positive) vs every other candidate (negative); pseudo-labels, no human verdicts",
        **params,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(probe, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return probe


def main() -> None:
    parser = argparse.ArgumentParser(description="Train or apply the tail probe.")
    sub = parser.add_subparsers(dest="command", required=True)
    b = sub.add_parser("build")
    b.add_argument("--clip", action="append", required=True)
    b.add_argument("--output", type=Path, required=True)
    b.add_argument("--device", default="cpu")
    s = sub.add_parser("score")
    s.add_argument("--probe", type=Path, required=True)
    s.add_argument("image", type=Path)
    s.add_argument("--device", default="cpu")
    args = parser.parse_args()
    if args.command == "build":
        probe = build(args.clip, args.output, args.device)
        print(json.dumps({k: probe[k] for k in ("trained_on", "n_positive", "n_negative", "leave_one_clip_out")}, indent=2))
    else:
        probe = json.loads(args.probe.read_text(encoding="utf-8"))
        processor, model = _embedder(args.device, probe["embedder"])
        image = Image.open(args.image).convert("RGB")
        print(probability(probe, embed_crop(processor, model, image, [0, 0, image.width, image.height], args.device)))


if __name__ == "__main__":
    main()
