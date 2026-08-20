# L1.0 semantics-blind latent-state discovery protocol

Status: frozen software-only method for issue #59. No real feline result is reported by this protocol.

## Scientific question

Can leakage-safe multimodal episode predictors reveal reproducible latent structure that is not mostly cat, household or session identity?

L1.0 does **not** ask what a cluster “means.” It does not translate cat behaviour, infer a true internal state, or attach English intent labels.

## Input boundary

`latent/l1_input.schema.json` separates two information planes.

### Fit plane

`fit_features` contains only numeric or missing predictor values that were available at or before the prediction time. Every feature is declared in `feature_manifest` with:

- a source family;
- `semantic_role = predictor`;
- `source_time_rule = at_or_before_prediction_time`.

Names containing obvious future/semantic leakage tokens such as `intent`, `hypothesis`, `outcome`, `label`, `translation`, `termination`, or post-horizon response language fail validation.

### Audit plane

The following are retained for post-fit nuisance/association audits but never passed to the clustering function:

- `subject_id`;
- `household_id`;
- `session_id`;
- coarse `context_bucket`;
- `observable_outcome`.

Changing every audit-only value while holding `fit_features` fixed must leave every cluster assignment, silhouette and stability result unchanged. This is a regression test.

## Frozen model ladder

L1.0 intentionally uses one simple family rather than searching architectures:

1. median imputation fitted on the current fit subset;
2. standardisation fitted on the same subset;
3. KMeans with `k = 2..8`, `n_init = 20`;
4. deterministic seed `20260821`.

No HMM, neural embedding, contrastive objective, large multimodal model or semantic supervision belongs in L1.0.

## Stability

For each `k`:

- fit one full-data clustering;
- repeat 20 times with deterministic 80% episode subsamples;
- refit imputation, scaling and KMeans on each subsample;
- assign all episodes using each fitted pipeline;
- report mean pairwise adjusted Rand index across those all-episode assignments.

This asks whether the discovered partition is reproducible under modest data perturbation.

## Structural diagnostics

For each `k`, report:

- silhouette;
- repeated-subsample stability;
- cluster counts;
- smallest/largest cluster fraction;
- normalized cluster-size entropy;
- drop-one-feature-family silhouette sensitivity.

Opaque full-fit assignments are rendered only as `L1-Z<k>-c<n>`.

## Post-fit nuisance audit

Only after assignments exist, calculate adjusted mutual information against:

- cat identity;
- household identity;
- session identity;
- coarse context;
- observable outcome.

A deterministic nuisance warning is raised when the maximum identity/session AMI is at least 0.50 and at least 0.10 above the strongest context/outcome association.

The warning is deliberately conservative and is **not** an automatic proof that no behavioural structure exists. It means the discovered partition cannot presently be promoted as a candidate feline state.

## Advancement boundary

L1.0 never emits `advance=true`.

A later L1 stage may advance a latent representation only if it also adds held-out predictive or calibration value beyond the frozen B0 context/routine baseline while surviving subject/household/session controls. That evaluation must be frozen before looking at real latent-model results.

## Synthetic fixtures

The unit suite contains two software-only cases:

1. a three-regime numeric structure designed to be recoverable while remaining independent of identity;
2. a highly stable identity-dominated structure designed to look clusterable but trigger the nuisance warning.

These fixtures test methodology only. They are not cat data and do not establish that feline latent states exist in the same form.

## Claims boundary

A stable opaque cluster is not automatically:

- hunger;
- play;
- access-seeking;
- affection;
- threat;
- pain;
- stress;
- or any other named state.

Semantic interpretation, if ever attempted, requires independent observable consequences, prospective interventions/outcomes, calibration, and falsifiable competing hypotheses.
