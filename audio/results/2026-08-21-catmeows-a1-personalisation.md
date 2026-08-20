# A1.0b preliminary result — unlabelled target-cat adaptation

Date: 2026-08-21

## Question

Does a small amount of **unlabelled audio from a new cat**, taken from recording sessions disjoint from evaluation, improve acoustic prediction of the CatMeows elicitation context?

This is a sensitivity analysis of context-conditioned vocal acoustics. It is **not** a test of literal feline-language translation.

## Dataset and feasibility gate

The experiment uses the checksum-verified CatMeows v1.0.2 archive from A1.0.

Before fitting any personalised model, P0 audited cat × session × context coverage. Of 21 cats:

- 18 have at least two recording sessions;
- 48 cat/session leave-one-session-out folds are possible;
- 26 folds across 11 cats satisfy the frozen primary rule: the held-out session contains at least two contexts and every held-out context is represented in the cat's other sessions.

The primary unlabelled adaptation budgets were frozen before model results were inspected:

- 1 clip: 26/26 folds supported;
- 2 clips: 26/26;
- 4 clips: 26/26;
- 8 clips: 25/26.

The unsupported budget-8 fold is left missing rather than replaced.

## Frozen P2 setup

Primary features are the interpretable acoustic descriptors from A1.0. For every feasible fold:

1. the target cat is completely absent from population-model training;
2. one target-cat session is held out for evaluation;
3. unlabelled adaptation clips may come only from the target cat's other sessions;
4. adaptation subsets are selected without context labels by deterministic SHA-256 ordering;
5. 20 subset repetitions are averaged for each budget;
6. shrinkage strength is fixed at `tau=4`.

The originally frozen comparison was raw population prediction versus target-centred prediction. After the first pooled P2 output was observed, a necessary attribution control was added: a **matched zero-shot identity-residualised model**. It residualises each training cat in exactly the same way as the personalised model, but the unseen target cat receives only the population centre. This separates the benefit of removing identity structure during training from the incremental benefit of observing the target cat.

The cat-equal bootstrap uncertainty analysis was also added after the first pooled result was observed. It is therefore a robustness analysis, not preregistered confirmatory inference.

## Pooled paired result

### Budget = 1 unlabelled clip

| Model | Balanced accuracy | Macro F1 | Log loss | Brier | ECE |
| --- | ---: | ---: | ---: | ---: | ---: |
| Raw population | 0.4511 | 0.4509 | 1.2668 | 0.7109 | 0.2542 |
| Centered zero-shot | **0.5097** | **0.5081** | **1.1303** | **0.6537** | 0.1758 |
| Shrinkage zero-shot | 0.4948 | 0.4951 | 1.1804 | 0.6714 | 0.1981 |
| Target-adapted centered | 0.4370 | 0.4366 | 1.0910 | 0.6700 | 0.1750 |
| Target-adapted shrinkage | 0.5043 | 0.5037 | 1.1426 | 0.6585 | **0.1719** |

The initial raw-population comparison made the one-clip shrinkage result look strongly positive: balanced accuracy increased by about 0.053 and log loss decreased by about 0.124.

The matched attribution comparison is much smaller:

- target-adapted shrinkage minus shrinkage zero-shot:
  - balanced accuracy: **+0.0094**;
  - macro F1: **+0.0086**;
  - log loss: **-0.0378**;
  - Brier: **-0.0128**.

Thus most of the apparent gain is explained by the identity-residualised training representation rather than by the single target-cat clip.

## Adaptation-budget curve against matched zero-shot

For the shrinkage model:

| Unlabelled clips | Δ balanced accuracy | Δ log loss | Δ Brier | Interpretation |
| ---: | ---: | ---: | ---: | --- |
| 1 | +0.0094 | -0.0378 | -0.0128 | small pooled probability gain |
| 2 | +0.0012 | -0.0348 | -0.0123 | essentially no discrimination gain |
| 4 | -0.0097 | -0.0460 | -0.0157 | probability gain, discrimination slightly worse |
| 8 | -0.0407 | -0.0255 | -0.0050 | discrimination materially worse |

There is no monotonic evidence that more unlabelled target-cat audio improves prediction. A plausible explanation is that an empirical target mean contains not only stable individual acoustic structure but also the context/session mixture present in the adaptation sample. Increasing trust in that mean can therefore remove useful context signal as well as identity signal.

That mechanism remains a hypothesis, not a demonstrated causal explanation.

## Cat-equal robustness analysis

Pooled clip-level metrics weight cats/sessions with more held-out clips more heavily. As a post-run robustness analysis, fold deltas were first averaged within each cat, then the 11 cats were weighted equally. Cats were bootstrapped as clusters for 2,000 replicates.

For **target-adapted shrinkage versus matched shrinkage zero-shot**:

### 1 clip

- balanced-accuracy mean delta: -0.0082; 95% bootstrap interval **[-0.0489, +0.0299]**;
- log-loss mean delta: -0.0241; interval **[-0.0721, +0.0169]**;
- Brier mean delta: -0.0054; interval **[-0.0336, +0.0207]**.

### 2 clips

- balanced accuracy: -0.0065 **[-0.0615, +0.0433]**;
- log loss: -0.0139 **[-0.0882, +0.0565]**;
- Brier: -0.0026 **[-0.0481, +0.0418]**.

### 4 clips

- balanced accuracy: -0.0308 **[-0.1065, +0.0314]**;
- log loss: -0.0189 **[-0.1259, +0.0846]**;
- Brier: -0.0040 **[-0.0695, +0.0563]**.

### 8 clips

- balanced accuracy: -0.0597 **[-0.1518, +0.0237]**;
- log loss: +0.0129 **[-0.1344, +0.1495]**;
- Brier: +0.0158 **[-0.0692, +0.1022]**.

Every interval crosses zero. With only 11 feasible cats, these data do not provide robust evidence that unlabelled target-cat centering improves over the matched zero-shot representation.

## What *did* improve?

The more promising signal is **zero-shot identity residualisation** itself.

On the 26 feasible folds, centered zero-shot versus the raw population model changes pooled performance from:

- balanced accuracy: 0.4511 → **0.5097**;
- macro F1: 0.4509 → **0.5081**;
- log loss: 1.2668 → **1.1303**;
- Brier: 0.7109 → **0.6537**;
- ECE: 0.2542 → **0.1758**.

Cat-equal mean deltas for centered zero-shot versus raw population are approximately:

- balanced accuracy: +0.0499, bootstrap interval **[-0.0309, +0.1253]**;
- log loss: -0.1162, interval **[-0.3445, +0.1086]**;
- Brier: -0.0633, interval **[-0.1770, +0.0309]**.

Those intervals also cross zero on this small 11-cat sensitivity subset, so this is not yet confirmatory evidence. However, unlike target adaptation, identity residualisation can be evaluated on the full 21-cat cross-cat benchmark and is the next higher-value experiment.

## Interpretation

A1.1 showed that stable acoustic clusters are much more associated with cat/owner/breed than with elicitation context. A1.0b now suggests that the useful response to that observation may be to **learn representations that suppress individual identity nuisance structure**, not simply to personalise the classifier with a few unlabelled target-cat examples.

This distinguishes two hypotheses that initially looked similar:

1. **Personalisation hypothesis:** learn the new cat so its vocalisations become easier to interpret.
2. **Identity-invariance hypothesis:** remove cat-specific acoustic structure so population-level context signal transfers better to unseen cats.

On CatMeows, the second hypothesis currently has stronger evidence.

## Limitations

- Only 11/21 cats support the primary session-disjoint personalisation folds.
- Context labels are elicitation conditions, not observed internal intent.
- Adaptation clips are unlabelled but not guaranteed to be context-balanced.
- The centering model is deliberately simple and may remove both nuisance identity and meaningful state information.
- Fold-level class support varies; the primary probabilistic metrics should be read alongside, not replaced by, per-fold balanced accuracy.
- The cat-level bootstrap was selected after the first pooled result and is descriptive robustness analysis.
- No claim is made that personalisation is generally useless; only that this particular unlabelled mean-centering strategy is not robustly supported here.

## Decision

**Do not advance this unlabelled target-centering method as a core personalisation mechanism.** Retain it as a negative/mixed baseline.

Advance the identity-invariance hypothesis next using the full cross-cat dataset, with residualisation/adversarial or nuisance-controlled representations compared against the frozen A1.0 population baselines.
