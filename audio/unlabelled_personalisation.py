from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from audio.acoustic_baselines import _align_probabilities, _feature_sets, _metrics, _to_matrix

DEFAULT_BUDGETS = [1, 2, 4, 8]
DEFAULT_REPEATS = 20
DEFAULT_SEED = 20260821
DEFAULT_SHRINKAGE_TAU = 4.0


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError(f"empty table: {path}")
    return rows


def _stable_order(
    rows: list[dict[str, str]], *, seed: int, repeat: int, cat_id: str, test_session: int
) -> list[dict[str, str]]:
    def key(row: dict[str, str]) -> bytes:
        payload = f"{seed}|{repeat}|{cat_id}|{test_session}|{row['path']}".encode("utf-8")
        return hashlib.sha256(payload).digest()

    return sorted(rows, key=key)


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


def _cat_centres(
    x_population: np.ndarray,
    population_rows: list[dict[str, str]],
    population_mean: np.ndarray,
    tau: float | None,
) -> np.ndarray:
    indices: dict[str, list[int]] = defaultdict(list)
    for index, row in enumerate(population_rows):
        indices[row["cat_id"]].append(index)

    centres: dict[str, np.ndarray] = {}
    for cat_id, cat_indices in indices.items():
        cat_mean = x_population[cat_indices].mean(axis=0)
        if tau is None:
            centres[cat_id] = cat_mean
        else:
            n = len(cat_indices)
            alpha = n / (n + tau)
            centres[cat_id] = alpha * cat_mean + (1.0 - alpha) * population_mean

    return np.asarray(
        [x_population[index] - centres[row["cat_id"]] for index, row in enumerate(population_rows)],
        dtype=float,
    )


def _delta(personalised: dict[str, float], baseline: dict[str, float]) -> dict[str, float]:
    return {name: float(personalised[name] - baseline[name]) for name in baseline}


def evaluate(
    features_csv: Path,
    audit_json: Path,
    *,
    budgets: list[int] | None = None,
    repeats: int = DEFAULT_REPEATS,
    seed: int = DEFAULT_SEED,
    shrinkage_tau: float = DEFAULT_SHRINKAGE_TAU,
) -> dict[str, object]:
    if repeats < 1:
        raise ValueError("repeats must be >= 1")
    if shrinkage_tau <= 0:
        raise ValueError("shrinkage_tau must be > 0")

    rows = _read_csv(features_csv)
    audit_report = json.loads(audit_json.read_text(encoding="utf-8"))
    budgets = sorted(set(budgets or DEFAULT_BUDGETS))
    if any(budget < 1 for budget in budgets):
        raise ValueError("adaptation budgets must be positive")

    classes = np.asarray(sorted({row["context"] for row in rows}), dtype=object)
    if len(classes) < 2:
        raise ValueError("at least two contexts are required")

    feature_names = _feature_sets(list(rows[0].keys()))["interpretable"]
    if not feature_names:
        raise ValueError("no interpretable acoustic features found")

    primary_folds: list[dict[str, object]] = []
    for cat_id, cat_report in audit_report["cats"].items():
        for fold in cat_report["folds"]:
            if fold["primary_feasible"]:
                primary_folds.append({"cat_id": cat_id, **fold})
    primary_folds.sort(key=lambda fold: (str(fold["cat_id"]), int(fold["test_session"])))
    if not primary_folds:
        raise ValueError("audit contains no primary-feasible folds")

    pooled: dict[int, dict[str, list[np.ndarray]]] = {
        budget: {
            "y": [],
            "population_raw": [],
            "centered_unshrunk": [],
            "centered_shrinkage": [],
        }
        for budget in budgets
    }
    fold_reports: list[dict[str, object]] = []

    for fold in primary_folds:
        cat_id = str(fold["cat_id"])
        test_session = int(fold["test_session"])
        population_rows = [row for row in rows if row["cat_id"] != cat_id]
        test_rows = [
            row for row in rows
            if row["cat_id"] == cat_id and int(row["session"]) == test_session
        ]
        adaptation_rows = [
            row for row in rows
            if row["cat_id"] == cat_id and int(row["session"]) != test_session
        ]
        if not population_rows or not test_rows or not adaptation_rows:
            raise RuntimeError(f"invalid fold materialisation for {cat_id}/session-{test_session}")

        y_population = np.asarray([row["context"] for row in population_rows], dtype=object)
        y_test = np.asarray([row["context"] for row in test_rows], dtype=object)

        imputer = SimpleImputer(strategy="median")
        x_population = imputer.fit_transform(_to_matrix(population_rows, feature_names))
        x_test = imputer.transform(_to_matrix(test_rows, feature_names))
        x_adaptation = imputer.transform(_to_matrix(adaptation_rows, feature_names))
        population_mean = x_population.mean(axis=0)

        raw_scaler, raw_model = _fit_logistic(x_population, y_population)
        raw_probability = _predict(raw_scaler, raw_model, x_test, classes)

        centered_population = _cat_centres(
            x_population, population_rows, population_mean, tau=None
        )
        centered_scaler, centered_model = _fit_logistic(centered_population, y_population)

        shrinkage_population = _cat_centres(
            x_population, population_rows, population_mean, tau=shrinkage_tau
        )
        shrinkage_scaler, shrinkage_model = _fit_logistic(shrinkage_population, y_population)

        fold_report: dict[str, object] = {
            "cat_id": cat_id,
            "test_session": test_session,
            "n_test": len(test_rows),
            "n_adaptation_available": len(adaptation_rows),
            "test_contexts": sorted(set(y_test.tolist())),
            "population_raw_metrics": _metrics(y_test, raw_probability, classes),
            "by_budget": {},
        }

        adaptation_index = {row["path"]: index for index, row in enumerate(adaptation_rows)}
        for budget in budgets:
            if len(adaptation_rows) < budget:
                fold_report["by_budget"][str(budget)] = {"supported": False}
                continue

            centered_probabilities: list[np.ndarray] = []
            shrinkage_probabilities: list[np.ndarray] = []
            for repeat in range(repeats):
                ordered = _stable_order(
                    adaptation_rows,
                    seed=seed,
                    repeat=repeat,
                    cat_id=cat_id,
                    test_session=test_session,
                )
                selected = ordered[:budget]
                selected_indices = [adaptation_index[row["path"]] for row in selected]
                adaptation_mean = x_adaptation[selected_indices].mean(axis=0)

                centered_test = x_test - adaptation_mean
                centered_probabilities.append(
                    _predict(centered_scaler, centered_model, centered_test, classes)
                )

                alpha = budget / (budget + shrinkage_tau)
                shrunk_target_centre = alpha * adaptation_mean + (1.0 - alpha) * population_mean
                shrinkage_test = x_test - shrunk_target_centre
                shrinkage_probabilities.append(
                    _predict(shrinkage_scaler, shrinkage_model, shrinkage_test, classes)
                )

            centered_probability = np.mean(centered_probabilities, axis=0)
            shrinkage_probability = np.mean(shrinkage_probabilities, axis=0)
            centered_metrics = _metrics(y_test, centered_probability, classes)
            shrinkage_metrics = _metrics(y_test, shrinkage_probability, classes)

            fold_report["by_budget"][str(budget)] = {
                "supported": True,
                "target_shrinkage_alpha": budget / (budget + shrinkage_tau),
                "centered_unshrunk_metrics": centered_metrics,
                "centered_shrinkage_metrics": shrinkage_metrics,
                "centered_unshrunk_delta_vs_population": _delta(
                    centered_metrics, fold_report["population_raw_metrics"]
                ),
                "centered_shrinkage_delta_vs_population": _delta(
                    shrinkage_metrics, fold_report["population_raw_metrics"]
                ),
            }

            pooled[budget]["y"].append(y_test)
            pooled[budget]["population_raw"].append(raw_probability)
            pooled[budget]["centered_unshrunk"].append(centered_probability)
            pooled[budget]["centered_shrinkage"].append(shrinkage_probability)

        fold_reports.append(fold_report)

    by_budget: dict[str, object] = {}
    for budget in budgets:
        if not pooled[budget]["y"]:
            by_budget[str(budget)] = {"supported_folds": 0}
            continue
        y = np.concatenate(pooled[budget]["y"])
        model_metrics: dict[str, dict[str, float]] = {}
        for model_name in ["population_raw", "centered_unshrunk", "centered_shrinkage"]:
            probability = np.concatenate(pooled[budget][model_name], axis=0)
            model_metrics[model_name] = _metrics(y, probability, classes)
        baseline = model_metrics["population_raw"]
        by_budget[str(budget)] = {
            "supported_folds": len(pooled[budget]["y"]),
            "n_test_clips": len(y),
            "models": model_metrics,
            "delta_vs_population": {
                "centered_unshrunk": _delta(model_metrics["centered_unshrunk"], baseline),
                "centered_shrinkage": _delta(model_metrics["centered_shrinkage"], baseline),
            },
        }

    return {
        "protocol": "A1.0b-unlabelled-session-disjoint-identity-normalisation-v0.1",
        "feature_set": "interpretable",
        "feature_names": feature_names,
        "classes": classes.tolist(),
        "budgets": budgets,
        "repeats_per_budget": repeats,
        "adaptation_subset_policy": (
            "deterministic SHA-256 ordering using seed/repeat/cat/test-session/path; labels are not used; "
            "budget subsets are nested within each repeat"
        ),
        "seed": seed,
        "shrinkage_tau": shrinkage_tau,
        "n_preregistered_primary_folds": len(primary_folds),
        "by_budget": by_budget,
        "folds": fold_reports,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate session-disjoint unlabelled cat personalisation")
    parser.add_argument("features_csv", type=Path)
    parser.add_argument("audit_json", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=DEFAULT_REPEATS)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--shrinkage-tau", type=float, default=DEFAULT_SHRINKAGE_TAU)
    args = parser.parse_args()

    report = evaluate(
        args.features_csv,
        args.audit_json,
        repeats=args.repeats,
        seed=args.seed,
        shrinkage_tau=args.shrinkage_tau,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote unlabelled personalisation report to {args.output}")


if __name__ == "__main__":
    main()
