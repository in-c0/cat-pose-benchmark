from __future__ import annotations

import argparse
import csv
import json
from itertools import combinations
from pathlib import Path

import numpy as np
from sklearn.cluster import KMeans
from sklearn.impute import SimpleImputer
from sklearn.metrics import adjusted_mutual_info_score, adjusted_rand_score, silhouette_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from audio.acoustic_baselines import _feature_sets, _to_matrix


def _mean_pairwise_ari(labelings: list[np.ndarray]) -> float:
    if len(labelings) < 2:
        return float("nan")
    scores = [adjusted_rand_score(left, right) for left, right in combinations(labelings, 2)]
    return float(np.mean(scores))


def analyse(
    features_csv: Path,
    feature_set: str = "all_acoustic",
    k_min: int = 2,
    k_max: int = 8,
    repeats: int = 20,
    subsample_fraction: float = 0.8,
    seed: int = 20260821,
) -> dict[str, object]:
    with features_csv.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) < 4:
        raise ValueError("at least four rows are required")

    feature_sets = _feature_sets(list(rows[0].keys()))
    if feature_set not in feature_sets:
        raise ValueError(f"unknown feature set: {feature_set}")
    feature_names = feature_sets[feature_set]
    if not feature_names:
        raise ValueError(f"feature set {feature_set} is empty")

    raw = _to_matrix(rows, feature_names)
    transform = Pipeline([
        ("impute", SimpleImputer(strategy="median")),
        ("scale", StandardScaler()),
    ])
    x = transform.fit_transform(raw)

    labels_by_metadata = {
        key: np.asarray([row[key] for row in rows], dtype=object)
        for key in ["context", "cat_id", "owner_id", "breed", "sex"]
        if key in rows[0]
    }

    max_valid_k = min(k_max, len(rows) - 1)
    if k_min < 2 or k_min > max_valid_k:
        raise ValueError("invalid k range")
    if not 0.5 <= subsample_fraction < 1.0:
        raise ValueError("subsample_fraction must be in [0.5, 1.0)")
    if repeats < 2:
        raise ValueError("repeats must be at least 2")

    rng = np.random.default_rng(seed)
    by_k: dict[str, object] = {}
    for k in range(k_min, max_valid_k + 1):
        full_model = KMeans(n_clusters=k, n_init=50, random_state=seed + k)
        full_labels = full_model.fit_predict(x)
        silhouette = float(silhouette_score(x, full_labels))

        metadata_ami = {
            key: float(adjusted_mutual_info_score(values, full_labels))
            for key, values in labels_by_metadata.items()
        }

        subsample_size = max(k + 1, int(round(len(rows) * subsample_fraction)))
        subsample_size = min(subsample_size, len(rows) - 1)
        repeat_labelings: list[np.ndarray] = []
        for repeat_index in range(repeats):
            subset = np.sort(rng.choice(len(rows), size=subsample_size, replace=False))
            model = KMeans(n_clusters=k, n_init=20, random_state=seed + 1000 * k + repeat_index)
            model.fit(x[subset])
            repeat_labelings.append(model.predict(x))

        stability = _mean_pairwise_ari(repeat_labelings)
        by_k[str(k)] = {
            "silhouette": silhouette,
            "subsample_stability_mean_pairwise_ari": stability,
            "metadata_adjusted_mutual_information": metadata_ami,
            "cluster_sizes": np.bincount(full_labels, minlength=k).astype(int).tolist(),
        }

    return {
        "protocol": "A1.1-acoustic-cluster-stability-v0.1",
        "feature_set": feature_set,
        "features": feature_names,
        "n_rows": len(rows),
        "k_range": [k_min, max_valid_k],
        "repeats": repeats,
        "subsample_fraction": subsample_fraction,
        "seed": seed,
        "interpretation_rule": (
            "Report all k values. Stable clusters are not semantic intents. Compare context AMI "
            "against cat/owner/breed/sex AMI before assigning any behavioural interpretation."
        ),
        "by_k": by_k,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="A1.1 unsupervised acoustic cluster stability analysis")
    parser.add_argument("features_csv", type=Path)
    parser.add_argument("--feature-set", default="all_acoustic", choices=["duration_f0", "interpretable", "mfcc", "all_acoustic"])
    parser.add_argument("--k-min", type=int, default=2)
    parser.add_argument("--k-max", type=int, default=8)
    parser.add_argument("--repeats", type=int, default=20)
    parser.add_argument("--subsample-fraction", type=float, default=0.8)
    parser.add_argument("--seed", type=int, default=20260821)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    report = analyse(
        args.features_csv,
        feature_set=args.feature_set,
        k_min=args.k_min,
        k_max=args.k_max,
        repeats=args.repeats,
        subsample_fraction=args.subsample_fraction,
        seed=args.seed,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote cluster-stability report to {args.output}")


if __name__ == "__main__":
    main()
