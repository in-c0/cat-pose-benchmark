from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np
from sklearn.dummy import DummyClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import balanced_accuracy_score, f1_score, log_loss
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from audio.group_splits import leave_one_group_out, validate_folds

META_COLUMNS = {
    "path", "filename", "context_code", "context", "cat_id", "breed_code", "breed",
    "sex_code", "sex", "owner_id", "session", "vocalisation_index", "sequence_group",
}


def _feature_sets(columns: list[str]) -> dict[str, list[str]]:
    duration_f0 = [
        name for name in ["duration_s", "f0_median_hz", "f0_range_hz", "voiced_fraction"]
        if name in columns
    ]
    interpretable = [
        name for name in columns
        if name not in META_COLUMNS
        and not name.startswith("mfcc_")
        and not name.startswith("mfcc_delta_")
        and name != "sample_rate_hz"
    ]
    mfcc = [name for name in columns if name.startswith("mfcc_") or name.startswith("mfcc_delta_")]
    return {
        "duration_f0": duration_f0,
        "interpretable": interpretable,
        "mfcc": mfcc,
        "all_acoustic": sorted(set(interpretable + mfcc)),
    }


def _to_matrix(rows: list[dict[str, str]], feature_names: list[str]) -> np.ndarray:
    return np.asarray(
        [[float(row[name]) if row[name] not in {"", "nan", "NaN"} else np.nan for name in feature_names] for row in rows],
        dtype=float,
    )


def multiclass_brier(y_true: np.ndarray, probabilities: np.ndarray, classes: np.ndarray) -> float:
    one_hot = np.zeros_like(probabilities, dtype=float)
    class_to_index = {label: index for index, label in enumerate(classes)}
    for row_index, label in enumerate(y_true):
        one_hot[row_index, class_to_index[label]] = 1.0
    return float(np.mean(np.sum((probabilities - one_hot) ** 2, axis=1)))


def top_label_ece(y_true: np.ndarray, probabilities: np.ndarray, classes: np.ndarray, bins: int = 10) -> float:
    confidence = probabilities.max(axis=1)
    prediction = classes[np.argmax(probabilities, axis=1)]
    correct = (prediction == y_true).astype(float)
    edges = np.linspace(0.0, 1.0, bins + 1)
    ece = 0.0
    for index in range(bins):
        lower, upper = edges[index], edges[index + 1]
        mask = (confidence >= lower) & (confidence <= upper if index == bins - 1 else confidence < upper)
        if not np.any(mask):
            continue
        ece += float(np.mean(mask)) * abs(float(np.mean(correct[mask])) - float(np.mean(confidence[mask])))
    return float(ece)


def _align_probabilities(model_classes: np.ndarray, probabilities: np.ndarray, classes: np.ndarray) -> np.ndarray:
    aligned = np.zeros((probabilities.shape[0], len(classes)), dtype=float)
    target_index = {label: index for index, label in enumerate(classes)}
    for source_index, label in enumerate(model_classes):
        aligned[:, target_index[label]] = probabilities[:, source_index]
    return aligned


def _metrics(y_true: np.ndarray, probabilities: np.ndarray, classes: np.ndarray) -> dict[str, float]:
    prediction = classes[np.argmax(probabilities, axis=1)]
    return {
        "balanced_accuracy": float(balanced_accuracy_score(y_true, prediction)),
        "macro_f1": float(f1_score(y_true, prediction, average="macro", zero_division=0)),
        "log_loss": float(log_loss(y_true, probabilities, labels=classes)),
        "multiclass_brier": multiclass_brier(y_true, probabilities, classes),
        "top_label_ece": top_label_ece(y_true, probabilities, classes),
    }


def evaluate(features_csv: Path, group_key: str = "cat_id") -> dict[str, object]:
    with features_csv.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError("feature table is empty")
    if group_key not in rows[0]:
        raise ValueError(f"unknown group key: {group_key}")

    by_path = {row["path"]: row for row in rows}
    if len(by_path) != len(rows):
        raise ValueError("feature table contains duplicate paths")

    classes = np.asarray(sorted({row["context"] for row in rows}), dtype=object)
    if len(classes) < 2:
        raise ValueError("at least two contexts are required")

    feature_sets = _feature_sets(list(rows[0].keys()))
    folds = leave_one_group_out(rows, group_key)
    split_errors = validate_folds(rows, folds, group_key)
    if split_errors:
        raise ValueError("invalid grouped folds: " + "; ".join(split_errors))

    result: dict[str, object] = {
        "protocol": "A1.0-leave-one-group-out-v0.1",
        "group_key": group_key,
        "classes": classes.tolist(),
        "n_rows": len(rows),
        "n_groups": len(folds),
        "models": {},
    }

    y_all = np.asarray([row["context"] for row in rows], dtype=object)
    row_index = {row["path"]: index for index, row in enumerate(rows)}

    def run_model(name: str, factory, feature_names: list[str] | None) -> dict[str, object]:
        probability_rows = np.zeros((len(rows), len(classes)), dtype=float)
        covered = np.zeros(len(rows), dtype=bool)
        fold_reports: list[dict[str, object]] = []

        for fold in folds:
            train_rows = [by_path[path] for path in fold["train_paths"]]
            test_rows = [by_path[path] for path in fold["test_paths"]]
            y_train = np.asarray([row["context"] for row in train_rows], dtype=object)
            y_test = np.asarray([row["context"] for row in test_rows], dtype=object)

            if feature_names is None:
                x_train = np.zeros((len(train_rows), 1), dtype=float)
                x_test = np.zeros((len(test_rows), 1), dtype=float)
            else:
                x_train = _to_matrix(train_rows, feature_names)
                x_test = _to_matrix(test_rows, feature_names)

            model = factory()
            model.fit(x_train, y_train)
            probabilities = _align_probabilities(model.classes_, model.predict_proba(x_test), classes)
            for row, probability in zip(test_rows, probabilities):
                target = row_index[row["path"]]
                probability_rows[target] = probability
                covered[target] = True

            fold_reports.append({
                "held_out_group": fold["held_out_group"],
                "n_test": len(test_rows),
                "metrics": _metrics(y_test, probabilities, classes),
            })

        if not np.all(covered):
            raise RuntimeError(f"{name}: grouped folds did not cover every row exactly once")
        return {
            "features": feature_names or [],
            "overall": _metrics(y_all, probability_rows, classes),
            "folds": fold_reports,
        }

    result["models"]["majority"] = run_model("majority", lambda: DummyClassifier(strategy="most_frequent"), None)
    result["models"]["prevalence_prior"] = run_model("prevalence_prior", lambda: DummyClassifier(strategy="prior"), None)

    for set_name, feature_names in feature_sets.items():
        if not feature_names:
            continue
        result["models"][f"logistic_{set_name}"] = run_model(
            f"logistic_{set_name}",
            lambda: Pipeline([
                ("impute", SimpleImputer(strategy="median")),
                ("scale", StandardScaler()),
                ("model", LogisticRegression(max_iter=5000, class_weight="balanced")),
            ]),
            feature_names,
        )

    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate A1 acoustic baselines with held-out groups")
    parser.add_argument("features_csv", type=Path)
    parser.add_argument("--group-key", default="cat_id", choices=["cat_id", "owner_id", "sequence_group"])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = evaluate(args.features_csv, args.group_key)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote baseline report to {args.output}")


if __name__ == "__main__":
    main()
