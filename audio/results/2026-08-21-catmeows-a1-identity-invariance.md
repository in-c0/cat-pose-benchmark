# A1.0c preliminary result — full cross-cat identity invariance

Date: 2026-08-21

## Question

Does suppressing cat-specific acoustic nuisance structure using **training cats only** improve zero-shot prediction of CatMeows elicitation context for an entirely unseen cat?

This is an acoustic context-generalisation experiment. It is not a test of literal feline language or a direct label of internal intent.

## Frozen protocol

The experiment uses the checksum-verified CatMeows v1.0.2 archive: 440 vocalisations from 21 cats.

The primary protocol was frozen before this full result was inspected:

- leave one cat out across all 21 cats;
- interpretable acoustic features only;
- raw population logistic baseline;
- true-cat centered zero-shot representation;
- true-cat shrinkage-centered zero-shot representation with `tau=4` carried forward from A1.0b;
- 20 deterministic pseudo-identity controls preserving the exact training-cat group-size multiset while scrambling which rows belong to each identity group;
- 2,000-replicate bootstrap over held-out cats;
- no target-cat audio used for preprocessing, centering, fitting, calibration, or adaptation.

For a held-out cat, residualised models subtract only the training-population mean from test features. Training cats may be centered by their own training-set acoustic means.

## Pooled result

| Model | Balanced accuracy | Macro F1 | Log loss | Brier | ECE |
| --- | ---: | ---: | ---: | ---: | ---: |
| Raw population | 0.5111 | 0.5036 | 1.0700 | 0.6109 | 0.1772 |
| True-cat centered zero-shot | **0.5261** | 0.5079 | 1.0437 | 0.6204 | **0.1646** |
| True-cat shrinkage zero-shot | 0.5138 | 0.4984 | 1.0854 | 0.6377 | 0.1903 |
| Mean of pseudo-identity centered controls | 0.5195 | **0.5107** | **1.0404** | **0.6066** | 0.1652 |

True-cat centering therefore improves pooled balanced accuracy by about **+0.0150** and log loss by **-0.0262** relative to the raw population model, but worsens Brier score by **+0.0094**.

Those small gains are not specific to the biologically correct cat grouping.

## Pseudo-identity specificity control

Twenty pseudo controls use the identical centering operation but assign training rows to deterministically scrambled pseudo identities while preserving the real training-cat group-size multiset.

For true-cat centered zero-shot versus raw population:

### Balanced accuracy

- true delta: **+0.0150**;
- pseudo mean delta: +0.0055;
- pseudo range: **[-0.0141, +0.0326]**;
- 30% of pseudo runs improve balanced accuracy at least as much as true identity centering.

### Log loss

- true delta: **-0.0262**;
- pseudo mean delta: -0.0163;
- pseudo range: **[-0.0494, +0.0247]**;
- 35% of pseudo runs improve log loss at least as much as true identity centering.

### Brier score

- true delta: **+0.0094** — worse than raw;
- pseudo mean delta: -0.0005;
- pseudo range: **[-0.0182, +0.0232]**;
- 80% of pseudo controls are at least as favourable as true identity centering on this metric.

The preregistered specificity criterion is therefore not met.

## Cat-equal robustness

Clip-pooled results can be dominated by cats with more recordings. The preregistered robustness analysis gives every held-out cat equal weight and bootstraps the 21 cats as clusters.

### True-cat centered versus raw

- balanced accuracy mean delta: **+0.0033**, median 0.0000, 95% bootstrap interval **[-0.0446, +0.0529]**;
- log-loss mean delta: **-0.0336**, median -0.0270, interval **[-0.1447, +0.0689]**;
- Brier mean delta: **+0.0011**, median +0.0219, interval **[-0.0572, +0.0602]**.

### Shrinkage-centered versus raw

- balanced accuracy: +0.0028, interval **[-0.0424, +0.0519]**;
- log loss: -0.0029, interval **[-0.1051, +0.0948]**;
- Brier: +0.0149, interval **[-0.0489, +0.0776]**.

Every interval crosses zero.

The pseudo-centered ensemble itself also gives small pooled improvements:

- balanced-accuracy cat-equal mean delta +0.0059, interval **[-0.0276, +0.0417]**;
- log-loss delta -0.0168, interval **[-0.0428, +0.0030]**;
- Brier delta -0.0012, interval **[-0.0077, +0.0054]**.

This is consistent with a generic recentering / regularisation effect rather than evidence that the correct biological identity grouping is uniquely useful.

## Did true centering remove identity structure?

Yes, very strongly.

The frozen diagnostic measures, feature by feature, the fraction of training variance attributable to between-cat means and averages that ratio across nonconstant features.

Mean across the 21 outer folds:

- raw acoustic representation: **0.311750**;
- true-cat centered: **0.000000**;
- true-cat shrinkage-centered: **0.015470**;
- pseudo-centered representation, evaluated against the real cat identities: **0.299480**.

True centering does exactly what it is supposed to geometrically: it removes virtually all between-cat mean structure from the training features. But that successful nuisance suppression does **not** translate into a specific, robust improvement in held-out context prediction.

This distinction matters. An invariance operation can demonstrably remove identity information without thereby isolating useful semantics.

## Interpretation

A1.1 showed strong cat/owner/breed structure in acoustic clusters. A1.0b initially suggested that removing cat-specific offsets might improve zero-shot transfer. A1.0c provides the decisive specificity test.

The result is negative/mixed:

1. correct cat centering slightly improves some pooled metrics;
2. it completely removes between-cat mean variance;
3. however, arbitrary same-sized pseudo-group centering often produces comparable improvements;
4. cat-equal uncertainty is wide and crosses zero;
5. Brier score is actually worse under true centering;
6. shrinkage centering does not rescue the effect.

Therefore the current evidence does **not** support escalating to a larger adversarial/deep identity-invariant acoustic model on CatMeows. Such a model could easily optimize an attractive invariance objective without demonstrating more transferable context information.

## What the CatMeows sequence has established

Across A1.0–A1.0c:

- vocal audio contains some signal about the experimental elicitation context;
- simple cross-cat discrimination reaches roughly 0.51 balanced accuracy versus 0.33 chance-like baselines;
- rich acoustic models can become badly overconfident;
- stable acoustic clusters predominantly encode individual/household/breed structure rather than context;
- few-shot unlabelled target-cat centering is not robustly supported;
- true identity residualisation removes identity structure but does not uniquely improve context generalisation.

This makes further CatMeows-only architecture optimisation a lower-value direction than adding evidence that the dataset does not contain: naturalistic context, routine history, spatial/object state, human input, temporal sequences, and prospective intervention outcomes.

## Limitations

- CatMeows labels are elicitation conditions, not internal-state ground truth.
- Some held-out cats contain only subsets of the three contexts, producing noisy per-cat classification metrics.
- Mean-centering addresses only one simple form of identity nuisance structure.
- Pseudo controls test specificity to grouping, not every possible explanation for the small recentering gain.
- The dataset is small for strong cat-level inference: 21 independent subjects.
- No conclusion here establishes that identity-invariant representation learning is generally useless; it establishes that the present evidence does not justify escalating it as the next research priority.

## Decision

**A1.0c advancement gate: FAIL.**

Do not escalate CatMeows identity-invariant model complexity.

Retain raw, centered, shrinkage, and pseudo-centered models as public baselines. Redirect the programme toward naturalistic **context/statistics + temporal history + multimodal + intervention/outcome** evidence, evaluated through the shared event contract and M1 ablation doctrine.
