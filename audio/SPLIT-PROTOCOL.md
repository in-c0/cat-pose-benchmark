# A1.0 split protocol — CatMeows context baseline

**Status:** frozen protocol v0.1  
**Issue:** #19

## Objective

Measure whether cat vocal audio predicts the supplied CatMeows emission context under evaluation that does not leak the same cat across train and test.

The primary result is not a literal-intent result. It is a cross-cat context-classification result on an external research-only dataset.

## Unit of analysis

One trimmed CatMeows `.wav` file is one vocalisation sample.

Metadata comes only from the declared filename convention. The parser records cat, owner, breed, sex, session, context, and vocalisation index. It also derives `sequence_group = cat_id:session` for later within-cat analyses.

## Primary split — leave one cat out

The primary A1.0 estimate uses **leave-one-cat-out (LOCO)** evaluation.

For every unique cat ID:

1. all vocalisations from that cat form the test fold;
2. every vocalisation from every other cat forms the development pool;
3. no feature normalisation, selection, calibration, threshold tuning, or hyperparameter search may inspect the held-out cat;
4. predictions from all held-out cats are concatenated to compute the headline cross-cat metrics.

Why: random clip splitting can let a model identify an individual cat or recording chain and then exploit correlations between identity and context. LOCO directly asks whether an acoustic signal generalises to an unseen cat.

## Nested development inside each LOCO fold

Any tuning inside a LOCO training pool must itself use grouped splits by `cat_id`. If calibration is learned, calibration data must come from training cats only.

The exact inner-fold count may be chosen after inspecting class/group feasibility, but the held-out outer cat can never influence that choice after model results are viewed.

## Owner-group sensitivity analysis

Generate **leave-one-owner-out** folds as a sensitivity analysis.

This is not interchangeable with LOCO. Owner and breed structure are not balanced in CatMeows, so owner-group results are interpreted as a confound stress test rather than a clean estimate of population performance.

Report:

- number of owners;
- cats per owner;
- context counts per owner;
- folds where one or more contexts are absent from training or test.

Do not discard difficult folds merely because they lower performance.

## Within-cat secondary analysis

If a within-cat model is studied, do not randomly split calls from the same session.

Use `sequence_group = cat_id:session` so an entire recording session is held together. Within-cat results must be reported separately from cross-cat LOCO results and must not be presented as evidence of cross-cat generalisation.

## Feature and preprocessing leakage

The following are fit on training data only within each outer fold:

- scaling/normalisation statistics;
- silence/activity thresholds learned from the dataset;
- PCA or other dimensionality reduction;
- feature selection;
- learned embeddings that are fine-tuned on CatMeows;
- class weighting derived from observed labels;
- hyperparameters;
- probability calibration.

Fixed signal-processing constants chosen before evaluation may be applied globally if they do not depend on dataset labels/test samples.

## Metrics

Headline metrics from concatenated LOCO predictions:

- balanced accuracy;
- macro F1;
- per-context precision/recall;
- confusion matrix;
- log loss for probabilistic models;
- Brier score and calibration diagnostics where probability semantics permit.

Report the number of test examples contributed by each held-out cat. Where uncertainty intervals are computed, resampling must respect cat grouping.

## Required baselines

Freeze before adding a large learned model:

1. majority/prevalence prior;
2. metadata/confound baselines where meaningful;
3. duration + F0 summary features;
4. MFCC baseline;
5. MFCC + temporal-modulation replication-style baseline.

A learned embedding model is an additional comparator, not a replacement for these baselines.

## Failure and abstention

A null result is valid. If cross-cat performance falls to baseline after controlling identity/session leakage, report that directly.

Future naturalistic data should support an explicit unknown/abstain state. CatMeows itself has exactly three supplied elicitation contexts, so A1.0 context classification does not manufacture an `unknown` class by relabelling test samples.

## Dataset boundary

CatMeows states scientific-research/non-commercial use. A1.0 code may parse metadata and evaluate locally, but this repository must not bundle its audio or silently treat research-only source material as commercial training data.

## Reproducibility outputs

Every A1.0 run should preserve:

- manifest checksum;
- fold-generation protocol/version;
- exact held-out cat per fold;
- feature/model configuration;
- software versions;
- out-of-fold prediction table;
- aggregate and per-cat metrics.
