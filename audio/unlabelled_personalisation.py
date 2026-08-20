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
DEFAULT_BOOTSTRAP_REPS = 2000
DEFAULT_BOOTSTRAP_SEED = 20260822
METRIC_NAMES = [
    "balanced_accuracy",
    "macro_f1",
    "log_loss",
    "multiclass_brier",
    "top_label_ece",
]


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


def _delta(model: dict[str, float], baseline: dict[str, float]) -> dict[str, float]:
    return {name: float(model[name] - baseline[name]) for name in baseline}


def _fold_metrics(fold: dict[str, object], budget: int, model_name: str) -> dict[str, float]:
    if model_name == "population_raw":
        return fold["population_raw_metrics"]  # type: ignore[return-value]
    if model_name == "centered_zero_shot":
        return fold["centered_zero_shot_metrics"]  # type: ignore[return-value]
    if model_name == "shrinkage_zero_shot":
        return fold["shrinkage_zero_shot_metrics"]  # type: ignore[return-value]
    return fold["by_budget"][str(budget)][f"{model_name}_metrics"]  # type: ignore[index,return-value]


def _cat_equal_delta_summary(
    folds: list[dict[str, object]],
    *,
    budget: int,
    model_name: str,
    baseline_name: str,
    bootstrap_reps: int,
    bootstrap_seed: int,
) -> dict[str, object]:
    by_cat: dict[str, list[dict[str, float]]] = defaultdict(list)
    for fold in folds:
        budget_record = fold["by_budget"].get(str(budget), {})  # type: ignore[union-attr]
        if not budget_record.get("supported", False):
            continue
        model_metrics = _fold_metrics(fold, budget, model_name)
        baseline_metrics = _fold_metrics(fold, budget, baseline_name)
        by_cat[str(fold["cat_id"])].append(_delta(model_metrics, baseline_metrics))

    if not by_cat:
        return {"n_cats": 0, "metrics": {}}

    cat_means: dict[str, dict[str, float]] = {}
    for cat_id, fold_deltas in sorted(by_cat.items()):
        cat_means[cat_id] = {
            metric: float(np.mean([delta[metric] for delta in fold_deltas]))
            for metric in METRIC_NAMES
        }

    metric_summary: dict[str, object] = {}
    for metric in METRIC_NAMES:
        values = np.asarray([cat_means[cat_id][metric] for cat_id in sorted(cat_means)], dtype=float)
        rng = np.random.default_rng(
            _derived_seed(bootstrap_seed, budget, model_name, baseline_name, metric)
        )
        if bootstrap_reps > 0:
            bootstrap_means = np.asarray(
                [float(np.mean(rng.choice(values, size=len(values), replace=True))) for _ in range(bootstrap_reps)],
                dtype=float,
            )
            ci_low, ci_high = np.quantile(bootstrap_means, [0.025, 0.975])
            ci: list[float] | None = [float(ci_low), float(ci_high)]
        else:
            ci = None

        metric_summary[metric] = {
            "cat_equal_mean_delta": float(np.mean(values)),
            "cat_equal_median_delta": float(np.median(values)),
            "bootstrap_mean_ci95": ci,
        }

    return {
        "comparison": f"{model_name}_minus_{baseline_name}",
        "n_cats": len(cat_means),
        "bootstrap_reps": bootstrap_reps,
        "bootstrap_unit": "cat",
        "metrics": metric_summary,
        "per_cat_mean_delta": cat_means,
    }


def evaluate(
    features_csv: Path,
    audit_json: Path,
    *,
    budgets: list[int] | None = None,
    repeats: int = DEFAULT_REPEATS,
    seed: int = DEFAULT_SEED,
    shrinkage_tau: float = DEFAULT_SHRINKAGE_TAU,
    bootstrap_reps: int = DEFAULT_BOOTSTRAP_REPS,
    bootstrap_seed: int = DEFAULT_BOOTSTRAP_SEED,
) -> dict[str, object]:
    if repeats < 1:
        raise ValueError("repeats must be >= 1")
    if shrinkage_tau <= 0:
        raise ValueError("shrinkage_tau must be > 0")
    if bootstrap_reps < 0:
        raise ValueError("bootstrap_reps must be >= 0")

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

    model_names = [
        "population_raw",
        "centered_zero_shot",
        "shrinkage_zero_shot",
        "centered_unshrunk",
        "centered_shrinkage",
    ]
    pooled: dict[int, dict[str, list[np.ndarray]]] = {
        budget: {"y": [], **{model_name: [] for model_name in model_names}}
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
        centered_zero_shot_probability = _predict(
            centered_scaler, centered_model, x_test - population_mean, classes
        )

        shrinkage_population = _cat_centres(
            x_population, population_rows, population_mean, tau=shrinkage_tau
        )
        shrinkage_scaler, shrinkage_model = _fit_logistic(shrinkage_population, y_population)
        shrinkage_zero_shot_probability = _predict(
            shrinkage_scaler, shrinkage_model, x_test - population_mean, classes
        )

        fold_report: dict[str, object] = {
            "cat_id": cat_id,
            "test_session": test_session,
            "n_test": len(test_rows),
            "n_adaptation_available": len(adaptation_rows),
            "test_contexts": sorted(set(y_test.tolist())),
            "population_raw_metrics": _metrics(y_test, raw_probability, classes),
            "centered_zero_shot_metrics": _metrics(y_test, centered_zero_shot_probability, classes),
            "shrinkage_zero_shot_metrics": _metrics(y_test, shrinkage_zero_shot_probability, classes),
            "by_budget": {},
        }

        adaptation_index = {row["path"]: index for index, row in enumerate(adaptation_rows)}
        for budget in budgets:
            if len(adaptation_rows) < budget:
                fold_report["by_budget"][str(budget)] = {"supported": False}  # type: ignore[index]
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

            budget_record = {
                "supported": True,
                "target_shrinkage_alpha": budget / (budget + shrinkage_tau),
                "centered_unshrunk_metrics": centered_metrics,
                "centered_shrinkage_metrics": shrinkage_metrics,
                "centered_unshrunk_delta_vs_population": _delta(
                    centered_metrics, fold_report["population_raw_metrics"]  # type: ignore[arg-type]
                ),
                "centered_shrinkage_delta_vs_population": _delta(
                    shrinkage_metrics, fold_report["population_raw_metrics"]  # type: ignore[arg-type]
                ),
                "centered_unshrunk_delta_vs_zero_shot": _delta(
                    centered_metrics, fold_report["centered_zero_shot_metrics"]  # type: ignore[arg-type]
                ),
                "centered_shrinkage_delta_vs_zero_shot": _delta(
                    shrinkage_metrics, fold_report["shrinkage_zero_shot_metrics"]  # type: ignore[arg-type]
                ),
            }
            fold_report["by_budget"][str(budget)] = budget_record  # type: ignore[index]

            pooled[budget]["y"].append(y_test)
            pooled[budget]["population_raw"].append(raw_probability)
            pooled[budget]["centered_zero_shot"].append(centered_zero_shot_probability)
            pooled[budget]["shrinkage_zero_shot"].append(shrinkage_zero_shot_probability)
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
        for model_name in model_names:
            probability = np.concatenate(pooled[budget][model_name], axis=0)
            model_metrics[model_name] = _metrics(y, probability, classes)

        population = model_metrics["population_raw"]
        by_budget[str(budget)] = {
            "supported_folds": len(pooled[budget]["y"]),
            "n_test_clips": len(y),
            "models": model_metrics,
            "delta_vs_population": {
                model_name: _delta(model_metrics[model_name], population)
                for model_name in model_names
                if model_name != "population_raw"
            },
            "target_adaptation_delta_vs_zero_shot": {
                "centered_unshrunk": _delta(
                    model_metrics["centered_unshrunk"], model_metrics["centered_zero_shot"]
                ),
                "centered_shrinkage": _delta(
                    model_metrics["centered_shrinkage"], model_metrics["shrinkage_zero_shot"]
                ),
            },
            "cat_equal_robustness": {
                "centered_zero_shot_vs_population": _cat_equal_delta_summary(
                    fold_reports,
                    budget=budget,
                    model_name="centered_zero_shot",
                    baseline_name="population_raw",
                    bootstrap_reps=bootstrap_reps,
                    bootstrap_seed=bootstrap_seed,
                ),
                "shrinkage_zero_shot_vs_population": _cat_equal_delta_summary(
                    fold_reports,
                    budget=budget,
                    model_name="shrinkage_zero_shot",
                    baseline_name="population_raw",
                    bootstrap_reps=bootstrap_reps,
                    bootstrap_seed=bootstrap_seed,
                ),
                "centered_unshrunk_vs_population": _cat_equal_delta_summary(
                    fold_reports,
                    budget=budget,
                    model_name="centered_unshrunk",
                    baseline_name="population_raw",
                    bootstrap_reps=bootstrap_reps,
                    bootstrap_seed=bootstrap_seed,
                ),
                "centered_unshrunk_vs_zero_shot": _cat_equal_delta_summary(
                    fold_reports,
                    budget=budget,
                    model_name="centered_unshrunk",
                    baseline_name="centered_zero_shot",
                    bootstrap_reps=bootstrap_reps,
                    bootstrap_seed=bootstrap_seed,
                ),
                "centered_shrinkage_vs_population": _cat_equal_delta_summary(
                    fold_reports,
                    budget=budget,
                    model_name="centered_shrinkage",
                    baseline_name="population_raw",
                    bootstrap_reps=bootstrap_reps,
                    bootstrap_seed=bootstrap_seed,
                ),
                "centered_shrinkage_vs_zero_shot": _cat_equal_delta_summary(
                    fold_reports,
                    budget=budget,
                    model_name="centered_shrinkage",
                    baseline_name="shrinkage_zero_shot",
                    bootstrap_reps=bootstrap_reps,
                    bootstrap_seed=bootstrap_seed,
                ),
            },
        }

    return {
        "protocol": "A1.0b-unlabelled-session-disjoint-identity-normalisation-v0.2",
        "feature_set": "interpretable",
        "feature_names": feature_names,
        "classes": classes.tolist(),
        "budgets": budgets,
        "repeats_per_budget": repeats,
        "adaptation_subset_policy": (
            "deterministic SHA-256 ordering using seed/repeat/cat/test-session/path; labels are not used; "
            "budget subsets are nested within each repeat"
        ),
        "zero_shot_comparator": (
            "training cats are identity-residualised exactly as in the personalised model, while the held-out "
            "target cat receives only the population centre; this isolates target-cat adaptation from the "
            "effect of residualising the population training representation"
        ),
        "seed": seed,
        "shrinkage_tau": shrinkage_tau,
        "n_preregistered_primary_folds": len(primary_folds),
        "post_run_robustness_analysis": {
            "status": "method added after the first pooled P2 result was observed; not preregistered confirmatory inference",
            "unit": "cat",
            "aggregation": "average fold delta within cat, then equal weight across cats",
            "bootstrap_reps": bootstrap_reps,
            "bootstrap_seed": bootstrap_seed,
        },
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
    parser.add_argument("--bootstrap-reps", type=int, default=DEFAULT_BOOTSTRAP_REPS)
    parser.add_argument("--bootstrap-seed", type=int, default=DEFAULT_BOOTSTRAP_SEED)
    args = parser.parse_args()

    report = evaluate(
        args.features_csv,
        args.audit_json,
        repeats=args.repeats,
        seed=args.seed,
        shrinkage_tau=args.shrinkage_tau,
        bootstrap_reps=args.bootstrap_reps,
        bootstrap_seed=args.bootstrap_seed,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote unlabelled personalisation report to {args.output}")


if __name__ == "__main__":
    main()
