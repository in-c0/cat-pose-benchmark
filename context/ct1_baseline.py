from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

from sklearn.feature_extraction import DictVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import balanced_accuracy_score, f1_score, log_loss
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from context.ct1_features import extract_ct1_rows, load_events

ROUTINE_FEATURES = (
    "local_hour_sin",
    "local_hour_cos",
    "time_since_previous_episode_s",
    "time_since_previous_episode_s_missing",
    "episodes_last_1h",
    "episodes_last_24h",
    "previous_location",
    "previous_signalling_terminated",
    "previous_signalling_terminated_missing",
    "time_since_food_action_s",
    "time_since_food_action_s_missing",
    "time_since_play_action_s",
    "time_since_play_action_s_missing",
    "time_since_access_action_s",
    "time_since_access_action_s_missing",
    "time_since_social_action_s",
    "time_since_social_action_s_missing",
)

CONTEXT_FEATURES = (
    "location",
    "n_objects",
    "n_humans_present",
    "n_other_cats_present",
    "nearest_human_distance_m",
    "nearest_human_distance_m_missing",
    "door_present",
    "door_open",
    "door_closed",
    "toy_present",
    "food_area_present",
)

MODEL_FEATURES = {
    "routine_history": ROUTINE_FEATURES,
    "object_location": CONTEXT_FEATURES,
    "context_routine": CONTEXT_FEATURES + ROUTINE_FEATURES,
}


def _ece_binary(y_true: list[int], probabilities: list[float], bins: int = 10) -> float:
    total = len(y_true)
    if total == 0:
        return float("nan")
    ece = 0.0
    for index in range(bins):
        lo = index / bins
        hi = (index + 1) / bins
        if index == bins - 1:
            members = [i for i, p in enumerate(probabilities) if lo <= p <= hi]
        else:
            members = [i for i, p in enumerate(probabilities) if lo <= p < hi]
        if not members:
            continue
        confidence = sum(probabilities[i] for i in members) / len(members)
        frequency = sum(y_true[i] for i in members) / len(members)
        ece += len(members) / total * abs(confidence - frequency)
    return ece


def _metrics(y_true: list[int], probabilities: list[float]) -> dict[str, float]:
    clipped = [min(max(float(p), 1e-9), 1.0 - 1e-9) for p in probabilities]
    predictions = [int(p >= 0.5) for p in clipped]
    return {
        "balanced_accuracy": float(balanced_accuracy_score(y_true, predictions)),
        "macro_f1": float(f1_score(y_true, predictions, average="macro", labels=[0, 1], zero_division=0)),
        "log_loss": float(log_loss(y_true, [[1.0 - p, p] for p in clipped], labels=[0, 1])),
        "brier": float(sum((p - y) ** 2 for p, y in zip(clipped, y_true)) / len(y_true)),
        "ece": float(_ece_binary(y_true, clipped)),
    }


def _selected_features(row: dict[str, Any], names: tuple[str, ...]) -> dict[str, Any]:
    features = row["features"]
    return {name: features[name] for name in names}


def _fit_probabilities(
    train_rows: list[dict[str, Any]],
    test_rows: list[dict[str, Any]],
    names: tuple[str, ...],
) -> tuple[list[float] | None, str | None]:
    y_train = [int(row["target_signalling_terminated"]) for row in train_rows]
    if len(set(y_train)) < 2:
        return None, "training split contains only one class"

    model = Pipeline(
        [
            ("vectorizer", DictVectorizer(sparse=True)),
            ("scale", StandardScaler(with_mean=False)),
            (
                "classifier",
                LogisticRegression(
                    C=1.0,
                    class_weight="balanced",
                    max_iter=2000,
                    solver="liblinear",
                    random_state=20260821,
                ),
            ),
        ]
    )
    model.fit([_selected_features(row, names) for row in train_rows], y_train)
    probabilities = model.predict_proba([_selected_features(row, names) for row in test_rows])[:, 1]
    return [float(value) for value in probabilities], None


def evaluate_single_household_chronological(
    rows: list[dict[str, Any]],
    train_fraction: float = 0.67,
) -> dict[str, Any]:
    labelled = [row for row in rows if isinstance(row.get("target_signalling_terminated"), bool)]
    labelled.sort(key=lambda row: row["prediction_time"])
    if len(labelled) < 6:
        raise ValueError("need at least 6 labelled rows for CT1.1 chronological evaluation")

    households = {row["household_id"] for row in labelled}
    if len(households) != 1:
        raise ValueError(
            "CT1.1 evaluator is intentionally single-household; use a future group-aware evaluator for multiple households"
        )

    split = max(2, min(len(labelled) - 2, int(math.floor(len(labelled) * train_fraction))))
    train_rows = labelled[:split]
    test_rows = labelled[split:]

    y_train = [int(row["target_signalling_terminated"]) for row in train_rows]
    y_test = [int(row["target_signalling_terminated"]) for row in test_rows]

    prevalence = (sum(y_train) + 1.0) / (len(y_train) + 2.0)
    report: dict[str, Any] = {
        "scope": "CT1.1 single-household chronological blocked sensitivity",
        "target": "signalling_terminated",
        "n_rows": len(labelled),
        "n_train": len(train_rows),
        "n_test": len(test_rows),
        "train_start": train_rows[0]["prediction_time"],
        "train_end": train_rows[-1]["prediction_time"],
        "test_start": test_rows[0]["prediction_time"],
        "test_end": test_rows[-1]["prediction_time"],
        "models": {
            "prevalence": {
                "status": "ok",
                "probability": prevalence,
                "metrics": _metrics(y_test, [prevalence] * len(test_rows)),
            }
        },
    }

    for name, feature_names in MODEL_FEATURES.items():
        probabilities, reason = _fit_probabilities(train_rows, test_rows, feature_names)
        if probabilities is None:
            report["models"][name] = {"status": "unsupported", "reason": reason}
            continue
        report["models"][name] = {
            "status": "ok",
            "features": list(feature_names),
            "metrics": _metrics(y_test, probabilities),
        }

    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the CT1.1 signalling-termination baseline")
    parser.add_argument("events", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--train-fraction", type=float, default=0.67)
    args = parser.parse_args()

    rows = extract_ct1_rows(load_events(args.events))
    report = evaluate_single_household_chronological(rows, train_fraction=args.train_fraction)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote CT1.1 baseline report to {args.output}")


if __name__ == "__main__":
    main()
