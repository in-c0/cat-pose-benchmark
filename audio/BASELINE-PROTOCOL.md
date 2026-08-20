# A1.0 acoustic baseline protocol

**Status:** implementation protocol v0.1  
**Thread:** A1 — vocalisation acoustics  
**Primary issue:** #19

## Purpose

Establish whether simple acoustic information predicts the CatMeows emission context under cross-cat evaluation before adding large learned audio models.

The target is the supplied experimental context, not a semantic intent label.

## Feature extraction

Audio is loaded at its native sample rate and converted to mono for this baseline. The extractor records:

- duration;
- pYIN F0 median and range;
- voiced-frame fraction and mean pYIN voicing probability;
- RMS energy summaries;
- zero-crossing-rate summaries;
- spectral centroid, bandwidth, and 85% rolloff summaries;
- 20 MFCC mean/std summaries;
- first-order MFCC-delta mean/std summaries.

Amplitude-derived features are retained but must be interpreted cautiously because recording gain and distance can confound them.

The implementation uses `librosa.pyin` for probabilistic YIN F0 estimation and `librosa.feature.mfcc` for the MFCC track.

## Frozen evaluation groups

Primary result:

- leave-one-`cat_id`-out;
- every clip is test data exactly once;
- no cat appears in both train and test for a fold.

Sensitivity results may additionally use:

- leave-one-`owner_id`-out;
- leave-one-`sequence_group`-out.

Random clip-level splitting is not a valid headline result.

## Frozen baseline ladder

1. `majority` — most-frequent training class;
2. `prevalence_prior` — training-fold class prevalence probabilities;
3. `logistic_duration_f0` — duration, F0 median/range, voiced fraction;
4. `logistic_interpretable` — non-MFCC acoustic summaries;
5. `logistic_mfcc` — MFCC + MFCC-delta summaries;
6. `logistic_all_acoustic` — interpretable + MFCC summaries.

Each logistic model uses median imputation, standardisation, and balanced multinomial logistic classification. Preprocessing is fit on each training fold only.

A learned embedding model is deliberately deferred until this ladder is frozen and run.

## Metrics

Aggregate out-of-group predictions are scored with:

- balanced accuracy;
- macro F1;
- multiclass log loss;
- multiclass Brier score;
- top-label expected calibration error (ECE).

Fold-level versions are also retained to expose cats or groups on which performance collapses.

Brier score and log loss assess probabilistic quality but mix calibration and discrimination; ECE is therefore reported alongside them rather than interpreting a lower Brier score as calibration proof by itself.

## Calibration boundary

This first baseline measures the calibration of the model probabilities it naturally emits. It does **not** fit a calibrator on held-out test cats.

If explicit recalibration is added later, calibration data must be disjoint from the final test cat and all preprocessing/calibration choices must be fit inside the training side of each outer fold.

## Reproducible commands

Given a locally obtained CatMeows directory whose use complies with its terms:

```bash
python -m audio.catmeows_manifest /path/to/CatMeows --output /tmp/catmeows-manifest.csv
python -m audio.acoustic_features /tmp/catmeows-manifest.csv /path/to/CatMeows --output /tmp/catmeows-features.csv
python -m audio.acoustic_baselines /tmp/catmeows-features.csv --group-key cat_id --output /tmp/a1-baselines.json
```

The repository does not download, bundle, or redistribute CatMeows audio.

## Advancement gate

A1.0 advances to learned embeddings only after:

- the baseline report is generated under the frozen cross-cat protocol;
- per-fold failures are inspected;
- identity/owner/breed confounding is reviewed;
- the result is reported even if acoustics fail to beat priors;
- no result is described as literal translation.
