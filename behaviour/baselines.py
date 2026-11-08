"""BH1 baselines (PROTOCOL.md section 7.4): what a method has to beat.

* ``majority``: predicts the most frequent class of the training folds. Never abstains.
* ``motion_lr``: 22 motion-energy features per segment, computed from frame differences alone,
  with standardisation and multinomial logistic regression (C = 1.0, balanced class weights,
  no tuning). It abstains when its top probability is below 0.5.

Neither sees pose, a detector, or any model output. ``motion_lr`` measures how much of the task
is solvable from raw pixel motion, so a pose-based method that does not beat it has not shown
that pose adds anything.

Both run in two cross-validation regimes, five group folds each (fewer if there are fewer
groups):

* ``clip_disjoint``: folds grouped by clip. A test cat may appear in training through another clip.
* ``cat_disjoint``: folds grouped by ``cat_id``. Every test cat is unseen.

Only segments whose human truth is one of the five classes enter training or testing. Each run
writes ``predictions/<method>--<regime>.csv`` (out-of-fold, one row per decided segment), the
format the scorer reads from any candidate method.

    python -m behaviour.baselines            # after release; reads work/frames, key.json, the locked labels
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Callable, Sequence

import numpy as np

from behaviour.common import CLASSES, HERE, write_csv

N_FOLDS = 5
MOTION_THRESHOLD = 0.1
FEATURE_WIDTH = 64
FEATURE_NAMES = (
    ["energy_mean", "energy_std", "energy_max", "energy_min", "area_mean", "area_max",
     "speed_x_mean", "speed_y_mean", "speed_y_max", "net_dx", "net_dy", "path_length", "centroid_y_std"]
    + [f"grid_{r}{c}" for r in range(3) for c in range(3)]
)
PRED_COLUMNS = ["segment_id", "regime", "method", "fold", "pred", "prob_max", "cat_seen_in_training"]


def motion_features(frames: np.ndarray) -> np.ndarray:
    """(T, H, W) grayscale frames, uint8 or [0, 1] floats -> 22 features. T >= 3."""
    f = frames.astype(np.float32)
    if f.max() > 1.0:
        f = f / 255.0
    d = np.abs(np.diff(f, axis=0))
    t, h, w = d.shape
    energy = d.mean(axis=(1, 2))
    area = (d > MOTION_THRESHOLD).mean(axis=(1, 2))
    ys, xs = np.mgrid[0:h, 0:w]
    xs, ys = (xs + 0.5) / w, (ys + 0.5) / h
    mass = d.sum(axis=(1, 2))
    still = mass < 1e-6
    safe = np.where(still, 1.0, mass)
    cx = np.where(still, 0.5, (d * xs).sum(axis=(1, 2)) / safe)
    cy = np.where(still, 0.5, (d * ys).sum(axis=(1, 2)) / safe)
    vx, vy = np.diff(cx), np.diff(cy)
    grid = np.array([d[:, r * h // 3:(r + 1) * h // 3, c * w // 3:(c + 1) * w // 3].sum() for r in range(3) for c in range(3)])
    grid = grid / grid.sum() if grid.sum() > 0 else np.full(9, 1 / 9)
    return np.concatenate([
        [energy.mean(), energy.std(), energy.max(), energy.min(), area.mean(), area.max(),
         np.abs(vx).mean(), np.abs(vy).mean(), np.abs(vy).max(), cx[-1] - cx[0], cy[-1] - cy[0], np.hypot(vx, vy).sum(), cy.std()],
        grid,
    ]).astype(np.float64)


def _model(method: str):
    from sklearn.dummy import DummyClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    if method == "majority":
        return DummyClassifier(strategy="most_frequent")
    if method == "motion_lr":
        return make_pipeline(StandardScaler(), LogisticRegression(C=1.0, class_weight="balanced", max_iter=1000))
    raise ValueError(method)


def cross_validate(X: np.ndarray, y: Sequence[str], groups: Sequence[str], cats: Sequence[str], method: str) -> list[dict[str, Any]]:
    """Out-of-fold predictions. ``groups`` defines the folds; ``cats`` is used only to record whether
    a test segment's cat appears in that fold's training data."""
    from sklearn.model_selection import GroupKFold

    y, groups, cats = np.asarray(y), np.asarray(groups), np.asarray(cats)
    k = min(N_FOLDS, len(set(groups)))
    out: list[dict[str, Any] | None] = [None] * len(y)
    for fold, (tr, te) in enumerate(GroupKFold(n_splits=k).split(X, y, groups)):
        classes = sorted(set(y[tr]))
        if len(classes) == 1:
            pred, prob = np.array([classes[0]] * len(te)), np.ones(len(te))
        else:
            m = _model(method).fit(X[tr], y[tr])
            proba = m.predict_proba(X[te])
            pred = np.asarray(m.classes_)[proba.argmax(axis=1)]
            prob = np.ones(len(te)) if method == "majority" else proba.max(axis=1)
        seen = set(cats[tr])
        for i, p, q in zip(te, pred, prob):
            out[i] = {"fold": fold, "pred": str(p), "prob_max": round(float(q), 4), "cat_seen_in_training": int(cats[i] in seen)}
    return out  # type: ignore[return-value]


def run(segments: list[str], X: np.ndarray, y: list[str], clip_of: dict[str, str], cat_of: dict[str, str],
        methods: Sequence[str] = ("majority", "motion_lr")) -> dict[str, list[dict[str, Any]]]:
    out = {}
    cats = [cat_of[s] for s in segments]
    for regime, groups in (("clip_disjoint", [clip_of[s] for s in segments]), ("cat_disjoint", cats)):
        for method in methods:
            rows = cross_validate(X, y, groups, cats, method)
            out[f"{method}--{regime}"] = [{"segment_id": s, "regime": regime, "method": method, **r} for s, r in zip(segments, rows)]
    return out


def segment_array(frames: list[Any]) -> np.ndarray:
    """PIL frames of one segment -> (T, H, W) grayscale at 64 px wide."""
    from PIL import Image

    arr = []
    for im in frames:
        g = im.convert("L")
        g = g.resize((FEATURE_WIDTH, max(1, round(g.height * FEATURE_WIDTH / g.width))), Image.BILINEAR)
        arr.append(np.asarray(g))
    return np.stack(arr)


def features_for(segments: list[str], key: dict[str, Any], frames: Callable[[str], list[tuple[float, Any]]]) -> np.ndarray:
    from behaviour.build import segment_frames

    cache: dict[str, list] = {}
    rows = []
    for s in segments:
        clip, k = s.rsplit("-S", 1)
        title = key["clips"][clip]["title"]
        if title not in cache:
            cache[title] = frames(title)
        rows.append(motion_features(segment_array(segment_frames(cache[title], int(k)))))
    return np.stack(rows)


def main() -> None:
    from behaviour.build import frames_from_work
    from behaviour.common import read_csv
    from behaviour.score import consensus, latest_per_labeller, load_labels

    p = argparse.ArgumentParser(description="Run the BH1 baselines on the locked labels.")
    p.add_argument("--out", type=Path, default=HERE / "predictions")
    a = p.parse_args()
    key = json.loads((HERE / "key.json").read_text(encoding="utf-8"))
    template = [r["segment_id"] for r in read_csv(HERE / "package" / "label-TEMPLATE.csv")]
    paths = sorted((HERE / "submissions" / "labels").glob("labels-*.csv"))
    labels = {h: load_labels(pth, template) for h, pth in latest_per_labeller(paths).items()}
    truth = {s: t for s, t in consensus(labels).items() if t in CLASSES}
    segments = sorted(truth)
    clip_of = {s: s.rsplit("-S", 1)[0] for s in segments}
    cat_of = {s: key["clips"][clip_of[s]]["cat_id"] for s in segments}
    X = features_for(segments, key, frames_from_work)
    for name, rows in run(segments, X, [truth[s] for s in segments], clip_of, cat_of).items():
        write_csv(a.out / f"{name}.csv", PRED_COLUMNS, rows)
        print(name, len(rows))


if __name__ == "__main__":
    main()
