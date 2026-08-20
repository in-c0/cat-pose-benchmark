from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path

import librosa
import numpy as np

FMIN_HZ = 60.0
FMAX_HZ = 1600.0
N_MFCC = 20


def _summary(prefix: str, values: np.ndarray) -> dict[str, float]:
    finite = np.asarray(values, dtype=float)
    finite = finite[np.isfinite(finite)]
    if finite.size == 0:
        return {
            f"{prefix}_mean": math.nan,
            f"{prefix}_std": math.nan,
            f"{prefix}_median": math.nan,
            f"{prefix}_min": math.nan,
            f"{prefix}_max": math.nan,
        }
    return {
        f"{prefix}_mean": float(np.mean(finite)),
        f"{prefix}_std": float(np.std(finite)),
        f"{prefix}_median": float(np.median(finite)),
        f"{prefix}_min": float(np.min(finite)),
        f"{prefix}_max": float(np.max(finite)),
    }


def extract_features(path: Path) -> dict[str, float]:
    y, sr = librosa.load(path, sr=None, mono=True)
    if sr <= 0 or y.size == 0:
        raise ValueError(f"empty or invalid audio: {path}")

    duration_s = float(y.size / sr)
    nyquist = sr / 2.0
    fmax = min(FMAX_HZ, nyquist * 0.95)
    if fmax <= FMIN_HZ:
        raise ValueError(f"sample rate too low for configured F0 range: {sr}")

    rms = librosa.feature.rms(y=y)[0]
    zcr = librosa.feature.zero_crossing_rate(y)[0]
    centroid = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
    bandwidth = librosa.feature.spectral_bandwidth(y=y, sr=sr)[0]
    rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr, roll_percent=0.85)[0]

    f0, voiced_flag, voiced_prob = librosa.pyin(
        y,
        fmin=FMIN_HZ,
        fmax=fmax,
        sr=sr,
    )
    voiced_f0 = f0[np.isfinite(f0)] if f0 is not None else np.array([], dtype=float)
    voiced_fraction = float(np.mean(voiced_flag)) if voiced_flag is not None else 0.0
    mean_voiced_probability = (
        float(np.nanmean(voiced_prob))
        if voiced_prob is not None and np.any(np.isfinite(voiced_prob))
        else math.nan
    )

    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=N_MFCC)
    mfcc_delta = librosa.feature.delta(mfcc)

    features: dict[str, float] = {
        "sample_rate_hz": float(sr),
        "duration_s": duration_s,
        "voiced_fraction": voiced_fraction,
        "mean_voiced_probability": mean_voiced_probability,
        "f0_median_hz": float(np.median(voiced_f0)) if voiced_f0.size else math.nan,
        "f0_range_hz": float(np.ptp(voiced_f0)) if voiced_f0.size else math.nan,
    }
    features.update(_summary("rms", rms))
    features.update(_summary("zcr", zcr))
    features.update(_summary("spectral_centroid_hz", centroid))
    features.update(_summary("spectral_bandwidth_hz", bandwidth))
    features.update(_summary("spectral_rolloff85_hz", rolloff))

    for index in range(N_MFCC):
        features[f"mfcc_{index + 1:02d}_mean"] = float(np.mean(mfcc[index]))
        features[f"mfcc_{index + 1:02d}_std"] = float(np.std(mfcc[index]))
        features[f"mfcc_delta_{index + 1:02d}_mean"] = float(np.mean(mfcc_delta[index]))
        features[f"mfcc_delta_{index + 1:02d}_std"] = float(np.std(mfcc_delta[index]))

    return features


def extract_manifest(manifest_path: Path, dataset_root: Path, output_path: Path) -> None:
    with manifest_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError("manifest is empty")

    output_rows: list[dict[str, object]] = []
    for row in rows:
        audio_path = dataset_root / row["path"]
        if not audio_path.is_file():
            raise FileNotFoundError(audio_path)
        output_rows.append({**row, **extract_features(audio_path)})

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(output_rows[0].keys())
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output_rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract deterministic A1 acoustic features")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("dataset_root", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    extract_manifest(args.manifest, args.dataset_root, args.output)
    print(f"wrote acoustic features to {args.output}")


if __name__ == "__main__":
    main()
