from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

import numpy as np
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from audio.acoustic_baselines import _align_probabilities, _feature_sets, _metrics, _to_matrix

DEFAULT_SHRINKAGE_TAU = 4.0
DEFAULT_PSEUDO_REPEATS = 20
DEFAULT_PSEUDO_SEED = 20260823
DEFAULT_BOOTSTRAP_REPS = 2000
DEFAULT_BOOTSTRAP_SEED = 20260824
METRIC_NAMES = [
    "balanced_accuracy",
    "macro_f1",
    "log_loss",
    "multiclass_brier",
    "top_label_ece",
]
HIGHER_IS_BETTER = {"balanced_accuracy", "macro_f1"}


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError("feature table is empty")
    return rows


def _derived_seed(base_seed: int, *parts: object) -> int:
    payload = "|".join([str(base_seed), *(str(part) for part in parts)]).encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big", signed=False)


def _fit_logistic(x: np.ndarray, y: np.ndarray) -> tuple[StandardScaler, LogisticRegression]:
    scaler = StandardScaler()
    x_scaled = scaler.fit_transform(x)
    model = LogisticRegression(max_iter=5000, class_weight="balanced")
    model.fit(x_scaled, y)
    return scaler, model


def _predict(
    scaler: StandardScaler,
    model: LogisticRegression,
    x: np.ndarray,
    classes: np.ndarray,
) -> np.ndarray:
    probability = model.predict_proba(scaler.transform(x))
    return _align_probabilities(model.classes_, probability, classes)


def _group_residualise(
    x: np.ndarray,
    labels: np.ndarray,
    population_mean: np.ndarray,
    *,
    tau: float | None,
) -> np.ndarray:
    result = np.empty_like(x, dtype=float)
    for label in sorted(set(labels.tolist())):
        indices = np.flatnonzero(labels == label)
        group_mean = x[indices].mean(axis=0)
        if tau is None:
            centre = group_mean
        else:
            n = len(indices)
            alpha = n / (n + tau)
            centre = alpha * group_mean + (1.0 - alpha) * population_mean
        result[indices] = x[indices] - centre
    return result


def _pseudo_labels(
    true_labels: np.ndarray,
    *,
    seed: int,
    held_out_cat: str,
    repeat: int,
) -> np.ndarray:
    counts = Counter(true_labels.tolist())
    group_labels: list[str] = []
    for label in sorted(counts):
        group_labels.extend([label] * counts[label])
    group_labels_array = np.asarray(group_labels, dtype=object)

    rng = np.random.default_rng(_derived_seed(seed, held_out_cat, repeat))
    permutation = rng.permutation(len(true_labels))
    assigned = np.empty(len(true_labels), dtype=object)
    assigned[permutation] = group_labels_array
    return assigned


def _between_group_variance_ratio(x: np.ndarray, labels: np.ndarray) -> float:
    overall = x.mean(axis=0)
    total_ss = np.sum((x - overall) ** 2, axis=0)
    between_ss = np.zeros(x.shape[1], dtype=float)
    for label in sorted(set(labels.tolist())):
        indices = np.flatnonzero(labels == label)
        mean = x[indices].mean(axis=0)
        between_ss += len(indices) * (mean - overall) ** 2

    valid = total_ss > 1e-12
    if not np.any(valid):
        return 0.0
    ratios = np.zeros_like(total_ss, dtype=float)
    ratios[valid] = between_ss[valid] / total_ss[valid]
    return float(np.mean(ratios[valid]))


def _delta(model: dict[str, float], baseline: dict[str, float]) -> dict[str, float]:
    return {metric: float(model[metric] - baseline[metric]) for metric in METRIC_NAMES}


def _cat_equal_summary(
    folds: list[dict[str, object]],
    *,
    model_name: str,
    baseline_name: str,
    bootstrap_reps: int,
    bootstrap_seed: int,
) -> dict[str, object]:
    deltas: dict[str, dict[str, float]] = {}
    for fold in folds:
        cat_id = str(fold["held_out_cat"])
        model = fold["metrics"][model_name]  # type: ignore[index]
        baseline = fold["metrics"][baseline_name]  # type: ignore[index]
        deltas[cat_id] = _delta(model, baseline)  # type: ignore[arg-type]

    summary: dict[str, object] = {}
    cats = sorted(deltas)
    for metric in METRIC_NAMES:
        values = np.asarray([deltas[cat][metric] for cat in cats], dtype=float)
        rng = np.random.default_rng(
            _derived_seed(bootstrap_seed, model_name, baseline_name, metric)
        )
        if bootstrap_reps:
            means = np.asarray(
                [float(np.mean(rng.choice(values, size=len(values), replace=True))) for _ in range(bootstrap_reps)],
                dtype=float,
            )
            low, high = np.quantile(means, [0.025, 0.975])
            ci: list[float] | None = [float(low), float(high)]
        else:
            ci = None
        summary[metric] = {
            "mean_delta": float(np.mean(values)),
            "median_delta": float(np.median(values)),
            "bootstrap_mean_ci95": ci,
        }

    return {
        "comparison": f"{model_name}_minus_{baseline_name}",
        "n_cats": len(cats),
        "bootstrap_unit": "held_out_cat",
        "bootstrap_reps": bootstrap_reps,
        "metrics": summary,
        "per_cat_delta": deltas,
    }


def _pseudo_specificity(
    true_metrics: dict[str, float],
    raw_metrics: dict[str, float],
    pseudo_metrics: list[dict[str, float]],
) -> dict[str, object]:
    result: dict[str, object] = {}
    true_delta = _delta(true_metrics, raw_metrics)
    for metric in METRIC_NAMES:
        pseudo_deltas = [metrics[metric] - raw_metrics[metric] for metrics in pseudo_metrics]
        if metric in HIGHER_IS_BETTER:
            as_or_more = sum(delta >= true_delta[metric] for delta in pseudo_deltas)
        else:
            as_or_more = sum(delta <= true_delta[metric] for delta in pseudo_deltas)
        result[metric] = {
            "true_delta_vs_raw": true_delta[metric],
            "pseudo_delta_mean": float(np.mean(pseudo_deltas)),
            "pseudo_delta_min": float(np.min(pseudo_deltas)),
            "pseudo_delta_max": float(np.max(pseudo_deltas)),
            "pseudo_as_or_more_improved_fraction": as_or_more / len(pseudo_deltas),
            "pseudo_deltas": [float(value) for value in pseudo_deltas],
        }
    return result


def evaluate(
    features_csv: Path,
    *,
    pseudo_repeats: int = DEFAULT_PSEUDO_REPEATS,
    pseudo_seed: int = DEFAULT_PSEUDO_SEED,
    shrinkage_tau: float = DEFAULT_SHRINKAGE_TAU,
    bootstrap_reps: int = DEFAULT_BOOTSTRAP_REPS,
    bootstrap_seed: int = DEFAULT_BOOTSTRAP_SEED,
) -> dict[str, object]:
    if pseudo_repeats < 1:
        raise ValueError("pseudo_repeats must be >= 1")
    if shrinkage_tau <= 0:
        raise ValueError("shrinkage_tau must be > 0")
    if bootstrap_reps < 0:
        raise ValueError("bootstrap_reps must be >= 0")

    rows = _read_rows(features_csv)
    classes = np.asarray(sorted({row["context"] for row in rows}), dtype=object)
    cats = sorted({row["cat_id"] for row in rows})
    if len(cats) < 2:
        raise ValueError("at least two cats are required")

    feature_names = _feature_sets(list(rows[0].keys()))["interpretable"]
    if not feature_names:
        raise ValueError("no interpretable acoustic features found")

    pooled_y: list[np.ndarray] = []
    pooled: dict[str, list[np.ndarray]] = {
        "raw_population": [],
        "true_centered_zero_shot": [],
        "true_shrinkage_zero_shot": [],
        "pseudo_centered_mean": [],
    }
    pooled_pseudo_by_repeat: list[list[np.ndarray]] = [[] for _ in range(pseudo_repeats)]
    fold_reports: list[dict[str, object]] = []

    for held_out_cat in cats:
        train_rows = [row for row in rows if row["cat_id"] != held_out_cat]
        test_rows = [row for row in rows if row["cat_id"] == held_out_cat]
        y_train = np.asarray([row["context"] for row in train_rows], dtype=object)
        y_test = np.asarray([row["context"] for row in test_rows], dtype=object)
        true_labels = np.asarray([row["cat_id"] for row in train_rows], dtype=object)

        imputer = SimpleImputer(strategy="median")
        x_train = imputer.fit_transform(_to_matrix(train_rows, feature_names))
        x_test = imputer.transform(_to_matrix(test_rows, feature_names))
        population_mean = x_train.mean(axis=0)
        zero_shot_test = x_test - population_mean

        raw_scaler, raw_model = _fit_logistic(x_train, y_train)
        raw_probability = _predict(raw_scaler, raw_model, x_test, classes)

        true_centered_train = _group_residualise(
            x_train, true_labels, population_mean, tau=None
        )
        centered_scaler, centered_model = _fit_logistic(true_centered_train, y_train)
        centered_probability = _predict(
            centered_scaler, centered_model, zero_shot_test, classes
        )

        true_shrinkage_train = _group_residualise(
            x_train, true_labels, population_mean, tau=shrinkage_tau
        )
        shrinkage_scaler, shrinkage_model = _fit_logistic(true_shrinkage_train, y_train)
        shrinkage_probability = _predict(
            shrinkage_scaler, shrinkage_model, zero_shot_test, classes
        )

        pseudo_probabilities: list[np.ndarray] = []
        pseudo_fold_metrics: list[dict[str, float]] = []
        pseudo_identity_ratios: list[float] = []
        for repeat in range(pseudo_repeats):
            pseudo = _pseudo_labels(
                true_labels,
                seed=pseudo_seed,
                held_out_cat=held_out_cat,
                repeat=repeat,
            )
            pseudo_train = _group_residualise(
                x_train, pseudo, population_mean, tau=None
            )
            pseudo_scaler, pseudo_model = _fit_logistic(pseudo_train, y_train)
            probability = _predict(pseudo_scaler, pseudo_model, zero_shot_test, classes)
            pseudo_probabilities.append(probability)
            pseudo_fold_metrics.append(_metrics(y_test, probability, classes))
            pseudo_identity_ratios.append(
                _between_group_variance_ratio(pseudo_train, true_labels)
            )
            pooled_pseudo_by_repeat[repeat].append(probability)

        pseudo_mean_probability = np.mean(pseudo_probabilities, axis=0)

        metrics = {
            "raw_population": _metrics(y_test, raw_probability, classes),
            "true_centered_zero_shot": _metrics(y_test, centered_probability, classes),
            "true_shrinkage_zero_shot": _metrics(y_test, shrinkage_probability, classes),
            "pseudo_centered_mean": _metrics(y_test, pseudo_mean_probability, classes),
        }
        fold_reports.append({
            "held_out_cat": held_out_cat,
            "n_test": len(test_rows),
            "test_contexts": sorted(set(y_test.tolist())),
            "metrics": metrics,
            "pseudo_repeat_metrics": pseudo_fold_metrics,
            "identity_structure": {
                "raw_between_cat_variance_ratio": _between_group_variance_ratio(x_train, true_labels),
                "true_centered_between_cat_variance_ratio": _between_group_variance_ratio(
                    true_centered_train, true_labels
                ),
                "true_shrinkage_between_cat_variance_ratio": _between_group_variance_ratio(
                    true_shrinkage_train, true_labels
                ),
                "pseudo_centered_between_cat_variance_ratio_mean": float(
                    np.mean(pseudo_identity_ratios)
                ),
                "pseudo_centered_between_cat_variance_ratio_values": pseudo_identity_ratios,
            },
        })

        pooled_y.append(y_test)
        pooled["raw_population"].append(raw_probability)
        pooled["true_centered_zero_shot"].append(centered_probability)
        pooled["true_shrinkage_zero_shot"].append(shrinkage_probability)
        pooled["pseudo_centered_mean"].append(pseudo_mean_probability)

    y_all = np.concatenate(pooled_y)
    pooled_metrics = {
        model_name: _metrics(y_all, np.concatenate(probabilities, axis=0), classes)
        for model_name, probabilities in pooled.items()
    }
    pseudo_repeat_metrics = [
        _metrics(y_all, np.concatenate(probabilities, axis=0), classes)
        for probabilities in pooled_pseudo_by_repeat
    ]

    raw_metrics = pooled_metrics["raw_population"]
    return {
        "protocol": "A1.0c-full-leave-one-cat-out-identity-invariance-v0.1",
        "feature_set": "interpretable",
        "feature_names": feature_names,
        "classes": classes.tolist(),
        "n_rows": len(rows),
        "n_cats": len(cats),
        "outer_split": "leave_one_cat_out_all_21_cats",
        "shrinkage_tau": shrinkage_tau,
        "pseudo_control": {
            "repeats": pseudo_repeats,
            "seed": pseudo_seed,
            "construction": (
                "within each training fold, deterministically permute row membership across pseudo identity "
                "groups while preserving the true training-cat group-size multiset"
            ),
            "pooled_repeat_metrics": pseudo_repeat_metrics,
        },
        "identity_variance_ratio_definition": (
            "for each feature: between-true-cat sum of squares / total sum of squares on training rows; "
            "report the mean across nonconstant features"
        ),
        "pooled_metrics": pooled_metrics,
        "pooled_delta_vs_raw": {
            model_name: _delta(metrics, raw_metrics)
            for model_name, metrics in pooled_metrics.items()
            if model_name != "raw_population"
        },
        "pseudo_specificity": {
            "true_centered_zero_shot": _pseudo_specificity(
                pooled_metrics["true_centered_zero_shot"], raw_metrics, pseudo_repeat_metrics
            ),
            "true_shrinkage_zero_shot": _pseudo_specificity(
                pooled_metrics["true_shrinkage_zero_shot"], raw_metrics, pseudo_repeat_metrics
            ),
        },
        "cat_equal_robustness": {
            "true_centered_vs_raw": _cat_equal_summary(
                fold_reports,
                model_name="true_centered_zero_shot",
                baseline_name="raw_population",
                bootstrap_reps=bootstrap_reps,
                bootstrap_seed=bootstrap_seed,
            ),
            "true_shrinkage_vs_raw": _cat_equal_summary(
                fold_reports,
                model_name="true_shrinkage_zero_shot",
                baseline_name="raw_population",
                bootstrap_reps=bootstrap_reps,
                bootstrap_seed=bootstrap_seed,
            ),
            "pseudo_mean_vs_raw": _cat_equal_summary(
                fold_reports,
                model_name="pseudo_centered_mean",
                baseline_name="raw_population",
                bootstrap_reps=bootstrap_reps,
                bootstrap_seed=bootstrap_seed,
            ),
        },
        "bootstrap": {
            "reps": bootstrap_reps,
            "seed": bootstrap_seed,
            "unit": "held_out_cat",
        },
        "folds": fold_reports,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate full cross-cat acoustic identity invariance")
    parser.add_argument("features_csv", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--pseudo-repeats", type=int, default=DEFAULT_PSEUDO_REPEATS)
    parser.add_argument("--pseudo-seed", type=int, default=DEFAULT_PSEUDO_SEED)
    parser.add_argument("--shrinkage-tau", type=float, default=DEFAULT_SHRINKAGE_TAU)
    parser.add_argument("--bootstrap-reps", type=int, default=DEFAULT_BOOTSTRAP_REPS)
    parser.add_argument("--bootstrap-seed", type=int, default=DEFAULT_BOOTSTRAP_SEED)
    args = parser.parse_args()

    report = evaluate(
        args.features_csv,
        pseudo_repeats=args.pseudo_repeats,
        pseudo_seed=args.pseudo_seed,
        shrinkage_tau=args.shrinkage_tau,
        bootstrap_reps=args.bootstrap_reps,
        bootstrap_seed=args.bootstrap_seed,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote identity-invariance report to {args.output}")


if __name__ == "__main__":
    main()
