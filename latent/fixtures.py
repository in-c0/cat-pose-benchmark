from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import numpy as np


FEATURE_MANIFEST = [
    {
        "name": "audio_shape_0",
        "family": "audio",
        "semantic_role": "predictor",
        "source_time_rule": "at_or_before_prediction_time",
        "description": "Synthetic pre-outcome acoustic coordinate.",
    },
    {
        "name": "visual_motion_0",
        "family": "visual",
        "semantic_role": "predictor",
        "source_time_rule": "at_or_before_prediction_time",
        "description": "Synthetic pre-outcome visual-motion coordinate.",
    },
    {
        "name": "routine_phase_0",
        "family": "routine",
        "semantic_role": "predictor",
        "source_time_rule": "at_or_before_prediction_time",
        "description": "Synthetic pre-outcome routine coordinate.",
    },
]


def _episode(
    index: int,
    *,
    subject_id: str,
    household_id: str,
    session_id: str,
    features: dict[str, float | None],
    context_bucket: str | None,
    observable_outcome: str | None,
) -> dict[str, Any]:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=3 * index)
    return {
        "episode_id": f"synthetic-episode-{index:04d}",
        "subject_id": subject_id,
        "household_id": household_id,
        "session_id": session_id,
        "start_time": start.isoformat(),
        "fit_features": features,
        "audit_only": {
            "context_bucket": context_bucket,
            "observable_outcome": observable_outcome,
        },
    }


def build_recoverable_fixture(n: int = 120) -> tuple[dict[str, Any], list[int]]:
    """Software-only fixture with three latent numeric regimes independent of identity."""
    rng = np.random.default_rng(59001)
    centers = np.asarray(
        [
            [-2.5, -1.2, 0.2],
            [0.1, 2.4, -1.8],
            [2.6, -0.6, 1.9],
        ],
        dtype=float,
    )
    episodes: list[dict[str, Any]] = []
    truth: list[int] = []
    for index in range(n):
        latent = (index * 7) % 3
        subject_index = index % 6
        subject_id = f"cat-{subject_index:02d}"
        household_id = f"hh-{subject_index % 3:02d}"
        session_id = f"session-{index // 10:03d}"
        values = centers[latent] + rng.normal(0.0, 0.28, size=3)
        # Deterministic sparse missingness exercises median imputation without erasing structure.
        routine_value: float | None = float(values[2])
        if index % 17 == 0:
            routine_value = None
        context_bucket = ["ctx-a", "ctx-b", "ctx-c"][(latent + index // 9) % 3]
        observable_outcome = ["obs-0", "obs-1", "obs-2"][(latent + (index % 5 == 0)) % 3]
        episodes.append(
            _episode(
                index,
                subject_id=subject_id,
                household_id=household_id,
                session_id=session_id,
                features={
                    "audio_shape_0": float(values[0]),
                    "visual_motion_0": float(values[1]),
                    "routine_phase_0": routine_value,
                },
                context_bucket=context_bucket,
                observable_outcome=observable_outcome,
            )
        )
        truth.append(latent)
    return {
        "dataset_version": "L1-input-v0",
        "feature_manifest": FEATURE_MANIFEST,
        "episodes": episodes,
    }, truth


def build_identity_confounded_fixture(n_per_subject: int = 30) -> dict[str, Any]:
    """Software-only fixture whose strongest structure is deliberately cat identity."""
    rng = np.random.default_rng(59002)
    subject_centers = np.asarray(
        [
            [-4.0, -3.0, -2.0],
            [-1.2, 3.5, 2.6],
            [2.3, -3.6, 3.4],
            [4.4, 3.2, -3.1],
        ],
        dtype=float,
    )
    episodes: list[dict[str, Any]] = []
    index = 0
    for subject_index in range(4):
        for local_index in range(n_per_subject):
            values = subject_centers[subject_index] + rng.normal(0.0, 0.22, size=3)
            # Audit labels vary within subject so they cannot explain the dominant geometry.
            context_bucket = f"ctx-{local_index % 3}"
            observable_outcome = f"obs-{(local_index * 5 + subject_index) % 3}"
            episodes.append(
                _episode(
                    index,
                    subject_id=f"cat-{subject_index:02d}",
                    household_id=f"hh-{subject_index // 2:02d}",
                    session_id=f"session-{subject_index:02d}-{local_index // 10:02d}",
                    features={
                        "audio_shape_0": float(values[0]),
                        "visual_motion_0": float(values[1]),
                        "routine_phase_0": float(values[2]),
                    },
                    context_bucket=context_bucket,
                    observable_outcome=observable_outcome,
                )
            )
            index += 1
    return {
        "dataset_version": "L1-input-v0",
        "feature_manifest": FEATURE_MANIFEST,
        "episodes": episodes,
    }
