from __future__ import annotations

import argparse
import json
import math
from itertools import combinations
from pathlib import Path
from typing import Any

import numpy as np
from jsonschema import Draft202012Validator, FormatChecker
from sklearn.cluster import KMeans
from sklearn.impute import SimpleImputer
from sklearn.metrics import adjusted_mutual_info_score, adjusted_rand_score, silhouette_score
from sklearn.preprocessing import StandardScaler

INPUT_VERSION = "L1-input-v0"
REPORT_VERSION = "L1-discovery-v0"
SCHEMA_PATH = Path(__file__).with_name("l1_input.schema.json")
K_VALUES = tuple(range(2, 9))
SUBSAMPLE_FRACTION = 0.80
STABILITY_REPEATS = 20
RANDOM_SEED = 20260821
FORBIDDEN_FIT_TOKENS = (
    "intent",
    "hypothesis",
    "translation",
    "outcome",
    "label",
    "termination",
    "future",
    "post_horizon",
    "post-horizon",
    "intervention_response",
    "response_after",
)


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_input(payload: Any) -> list[str]:
    schema = _load_json(SCHEMA_PATH)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors: list[str] = []
    for error in sorted(validator.iter_errors(payload), key=lambda item: list(item.absolute_path)):
        path = ".".join(str(part) for part in error.absolute_path) or "<root>"
        errors.append(f"schema.{path}: {error.message}")
    if errors or not isinstance(payload, dict):
        return errors or ["schema.<root>: L1 input must be an object"]

    manifest = payload["feature_manifest"]
    names = [item["name"] for item in manifest]
    if len(names) != len(set(names)):
        errors.append("feature_manifest: feature names must be unique")

    lowered_names = {name: name.lower() for name in names}
    for name, lowered in lowered_names.items():
        matched = [token for token in FORBIDDEN_FIT_TOKENS if token in lowered]
        if matched:
            errors.append(
                f"feature_manifest.{name}: fit feature name contains forbidden semantic/future token(s): {','.join(matched)}"
            )

    expected = set(names)
    episode_ids: list[str] = []
    for index, episode in enumerate(payload["episodes"]):
        episode_ids.append(episode["episode_id"])
        actual = set(episode["fit_features"])
        if actual != expected:
            missing = sorted(expected - actual)
            extra = sorted(actual - expected)
            errors.append(
                f"episodes.{index}.fit_features: keys must exactly match feature_manifest; missing={missing}, extra={extra}"
            )
        for key, value in episode["fit_features"].items():
            if isinstance(value, (int, float)) and not isinstance(value, bool) and not math.isfinite(float(value)):
                errors.append(f"episodes.{index}.fit_features.{key}: value must be finite or null")

    if len(episode_ids) != len(set(episode_ids)):
        errors.append("episodes: episode_id values must be unique")

    for name in names:
        values = [episode["fit_features"].get(name) for episode in payload["episodes"]]
        if all(value is None for value in values):
            errors.append(f"feature_manifest.{name}: feature is null for every episode")

    return errors


def extract_fit_matrix(payload: dict[str, Any]) -> tuple[np.ndarray, list[str], list[str]]:
    """Return only predictor data.

    This function deliberately does not return subject/household/session IDs, audit
    context or outcomes. The fitter below therefore cannot access those columns.
    """
    manifest = payload["feature_manifest"]
    names = [item["name"] for item in manifest]
    families = [item["family"] for item in manifest]
    rows = [
        [episode["fit_features"][name] for name in names]
        for episode in payload["episodes"]
    ]
    return np.asarray(rows, dtype=float), names, families


def _preprocess_fit_predict(
    X: np.ndarray,
    fit_indices: np.ndarray,
    *,
    k: int,
    seed: int,
) -> tuple[np.ndarray, np.ndarray]:
    imputer = SimpleImputer(strategy="median")
    scaler = StandardScaler()
    X_fit_imputed = imputer.fit_transform(X[fit_indices])
    X_all_imputed = imputer.transform(X)
    X_fit_scaled = scaler.fit_transform(X_fit_imputed)
    X_all_scaled = scaler.transform(X_all_imputed)
    model = KMeans(n_clusters=k, random_state=seed, n_init=20)
    model.fit(X_fit_scaled)
    labels = model.predict(X_all_scaled)
    return labels.astype(int), model.cluster_centers_


def _canonical_cluster_ids(labels: np.ndarray, centers: np.ndarray, k: int) -> list[str]:
    order = sorted(
        range(k),
        key=lambda index: tuple(float(value) for value in centers[index]),
    )
    mapping = {raw: position + 1 for position, raw in enumerate(order)}
    return [f"L1-Z{k:02d}-c{mapping[int(label)]}" for label in labels]


def _mean_pairwise_ari(label_sets: list[np.ndarray]) -> float:
    if len(label_sets) < 2:
        return float("nan")
    values = [adjusted_rand_score(a, b) for a, b in combinations(label_sets, 2)]
    return float(np.mean(values))


def _cluster_shape(cluster_ids: list[str]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for cluster_id in cluster_ids:
        counts[cluster_id] = counts.get(cluster_id, 0) + 1
    total = sum(counts.values())
    fractions = [count / total for count in counts.values()]
    entropy = -sum(value * math.log(value) for value in fractions if value > 0)
    normalized_entropy = entropy / math.log(len(fractions)) if len(fractions) > 1 else 0.0
    return {
        "counts": dict(sorted(counts.items())),
        "smallest_fraction": float(min(fractions)),
        "largest_fraction": float(max(fractions)),
        "normalized_entropy": float(normalized_entropy),
    }


def _single_full_fit_silhouette(X: np.ndarray, *, k: int, seed: int) -> float | None:
    if len(X) <= k:
        return None
    labels, _ = _preprocess_fit_predict(
        X,
        np.arange(len(X), dtype=int),
        k=k,
        seed=seed,
    )
    if len(set(labels.tolist())) < 2:
        return None
    imputer = SimpleImputer(strategy="median")
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(imputer.fit_transform(X))
    return float(silhouette_score(X_scaled, labels))


def _fit_latent_structure(
    X: np.ndarray,
    feature_names: list[str],
    feature_families: list[str],
    *,
    k_values: tuple[int, ...] = K_VALUES,
    repeats: int = STABILITY_REPEATS,
    seed: int = RANDOM_SEED,
) -> dict[str, Any]:
    """Fit latent structure from X only; no audit/semantic columns are accepted."""
    n = len(X)
    rng = np.random.default_rng(seed)
    per_k: list[dict[str, Any]] = []

    for k in k_values:
        if n <= k:
            per_k.append({"k": k, "eligible": False, "reason": "n_episodes_must_exceed_k"})
            continue

        full_indices = np.arange(n, dtype=int)
        full_labels, full_centers = _preprocess_fit_predict(
            X,
            full_indices,
            k=k,
            seed=seed + k,
        )
        cluster_ids = _canonical_cluster_ids(full_labels, full_centers, k)

        imputer = SimpleImputer(strategy="median")
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(imputer.fit_transform(X))
        silhouette = (
            float(silhouette_score(X_scaled, full_labels))
            if len(set(full_labels.tolist())) > 1
            else None
        )

        subset_size = max(k + 1, int(math.floor(SUBSAMPLE_FRACTION * n)))
        subset_size = min(subset_size, n)
        stability_labels: list[np.ndarray] = []
        for repeat in range(repeats):
            subset = np.sort(rng.choice(n, size=subset_size, replace=False))
            labels, _ = _preprocess_fit_predict(
                X,
                subset,
                k=k,
                seed=seed + 1000 * k + repeat,
            )
            stability_labels.append(labels)

        family_ablation: dict[str, Any] = {}
        for family in sorted(set(feature_families)):
            keep = [index for index, value in enumerate(feature_families) if value != family]
            if not keep:
                family_ablation[family] = {"eligible": False, "reason": "would_remove_all_features"}
                continue
            reduced = X[:, keep]
            reduced_silhouette = _single_full_fit_silhouette(
                reduced,
                k=k,
                seed=seed + 10_000 + k,
            )
            family_ablation[family] = {
                "eligible": True,
                "silhouette_without_family": reduced_silhouette,
                "delta_vs_full": (
                    None
                    if silhouette is None or reduced_silhouette is None
                    else float(reduced_silhouette - silhouette)
                ),
                "remaining_feature_count": len(keep),
            }

        per_k.append(
            {
                "k": k,
                "eligible": True,
                "silhouette": silhouette,
                "stability_mean_pairwise_ari": _mean_pairwise_ari(stability_labels),
                "cluster_shape": _cluster_shape(cluster_ids),
                "cluster_ids": cluster_ids,
                "drop_one_feature_family": family_ablation,
            }
        )

    return {
        "n_episodes": n,
        "n_features": int(X.shape[1]),
        "feature_names": feature_names,
        "feature_families": feature_families,
        "k_values": list(k_values),
        "subsample_fraction": SUBSAMPLE_FRACTION,
        "stability_repeats": repeats,
        "random_seed": seed,
        "per_k": per_k,
    }


def _ami(cluster_ids: list[str], labels: list[Any]) -> float | None:
    pairs = [(cluster, label) for cluster, label in zip(cluster_ids, labels) if label is not None]
    if len(pairs) < 2:
        return None
    y_cluster = [cluster for cluster, _ in pairs]
    y_label = [str(label) for _, label in pairs]
    if len(set(y_label)) < 2:
        return 0.0
    return float(adjusted_mutual_info_score(y_label, y_cluster))


def _audit_assignments(payload: dict[str, Any], fit_report: dict[str, Any]) -> list[dict[str, Any]]:
    episodes = payload["episodes"]
    subject = [item["subject_id"] for item in episodes]
    household = [item["household_id"] for item in episodes]
    session = [item["session_id"] for item in episodes]
    context = [item["audit_only"].get("context_bucket") for item in episodes]
    outcome = [item["audit_only"].get("observable_outcome") for item in episodes]

    audited: list[dict[str, Any]] = []
    for row in fit_report["per_k"]:
        if not row.get("eligible"):
            audited.append({"k": row["k"], "eligible": False})
            continue
        cluster_ids = row["cluster_ids"]
        associations = {
            "subject_id_ami": _ami(cluster_ids, subject),
            "household_id_ami": _ami(cluster_ids, household),
            "session_id_ami": _ami(cluster_ids, session),
            "context_bucket_ami": _ami(cluster_ids, context),
            "observable_outcome_ami": _ami(cluster_ids, outcome),
        }
        identity_values = [
            associations["subject_id_ami"],
            associations["household_id_ami"],
            associations["session_id_ami"],
        ]
        identity_max = max(value for value in identity_values if value is not None)
        comparison_values = [
            value
            for value in (
                associations["context_bucket_ami"],
                associations["observable_outcome_ami"],
            )
            if value is not None
        ]
        nonidentity_max = max(comparison_values) if comparison_values else 0.0
        confounded = identity_max >= 0.50 and identity_max >= nonidentity_max + 0.10
        audited.append(
            {
                "k": row["k"],
                "eligible": True,
                "audit_associations": associations,
                "identity_max_ami": float(identity_max),
                "nonidentity_max_ami": float(nonidentity_max),
                "identity_confound_warning": bool(confounded),
            }
        )
    return audited


def run_discovery(payload: dict[str, Any]) -> dict[str, Any]:
    errors = validate_input(payload)
    if errors:
        raise ValueError("invalid L1 input:\n- " + "\n- ".join(errors))

    X, feature_names, feature_families = extract_fit_matrix(payload)
    fit_report = _fit_latent_structure(X, feature_names, feature_families)
    audits = _audit_assignments(payload, fit_report)
    audit_by_k = {item["k"]: item for item in audits}

    per_k: list[dict[str, Any]] = []
    for row in fit_report["per_k"]:
        merged = dict(row)
        merged.update(audit_by_k[row["k"]])
        per_k.append(merged)

    return {
        "report_version": REPORT_VERSION,
        "input_version": payload["dataset_version"],
        "performance_analysis_performed": False,
        "semantic_naming_performed": False,
        "fit_inputs": {
            "n_episodes": fit_report["n_episodes"],
            "n_features": fit_report["n_features"],
            "feature_names": fit_report["feature_names"],
            "feature_families": fit_report["feature_families"],
        },
        "frozen_method": {
            "algorithm": "KMeans",
            "k_values": fit_report["k_values"],
            "preprocessing": "median_impute_then_standardize",
            "subsample_fraction": fit_report["subsample_fraction"],
            "stability_repeats": fit_report["stability_repeats"],
            "random_seed": fit_report["random_seed"],
        },
        "per_k": per_k,
        "advancement_decision": "not_evaluated_l1_0_requires_downstream_predictive_value_beyond_B0",
        "claims_boundary": "opaque latent structure and nuisance audit only; no feline intent semantics",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run L1.0 semantics-blind latent-state discovery audit")
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    payload = _load_json(args.input)
    report = run_discovery(payload)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "report_version": report["report_version"],
                "n_episodes": report["fit_inputs"]["n_episodes"],
                "n_features": report["fit_inputs"]["n_features"],
                "semantic_naming_performed": report["semantic_naming_performed"],
                "advancement_decision": report["advancement_decision"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
