# A1.1 acoustic latent-structure protocol

**Status:** protocol v0.1  
**Thread:** A1 — vocalisation acoustics  
**Parent issue:** #19

## Question

Do recurring, stable acoustic structures exist in CatMeows after standard acoustic preprocessing, and are those structures associated more strongly with experimental context or with individual/household identity?

A cluster is **not** an intent label. This stage intentionally delays semantic naming.

## Input

Use the feature table emitted by `audio.acoustic_features`. No raw audio is committed to this repository.

The analysis can be run on each frozen feature family:

- `duration_f0`;
- `interpretable`;
- `mfcc`;
- `all_acoustic`.

Missing numeric values are median-imputed and features are standardized once for this descriptive unsupervised analysis.

## Frozen candidate cluster counts

Report every `k = 2..8` that is valid for the available sample size. Do not search hundreds of cluster counts and publish only the visually attractive result.

For each `k`:

1. fit full-data K-means with fixed seed and multiple initialisations;
2. report silhouette score;
3. run repeated 80% subsamples;
4. fit K-means independently on each subsample;
5. assign all observations to each fitted solution;
6. report mean pairwise adjusted Rand index across repeat solutions;
7. report cluster sizes;
8. report adjusted mutual information between cluster assignment and context, cat ID, owner ID, breed, and sex where available.

Adjusted Rand/Mutual Information are label-permutation invariant, avoiding false disagreement caused only by arbitrary cluster numbering.

## Identity-confounding test

A context-associated cluster is not automatically a context signal.

Before interpretation, compare:

- `AMI(cluster, context)`;
- `AMI(cluster, cat_id)`;
- `AMI(cluster, owner_id)`;
- `AMI(cluster, breed)`;
- `AMI(cluster, sex)`.

If identity/owner/breed association dominates context association, the result is primarily evidence of confounding or individual vocal signatures, not shared context structure.

## Stability interpretation

Stability and silhouette are diagnostics, not proof of biological categories.

A useful candidate structure should ideally be:

- non-degenerate in cluster size;
- reasonably stable under resampling;
- reproducible across at least two feature families;
- not explained predominantly by identity/owner/breed;
- useful for held-out prediction in a later experiment before receiving a semantic interpretation.

## Output

`audio.cluster_stability` emits a JSON report containing all tested `k` values, stability, silhouette, metadata association diagnostics, and the exact seed/protocol parameters.

No automatic `best_k` or semantic cluster name is emitted in v0.1.

## Command

```bash
python -m audio.cluster_stability /tmp/catmeows-features.csv \
  --feature-set all_acoustic \
  --k-min 2 --k-max 8 --repeats 20 \
  --output /tmp/a1-cluster-stability.json
```

Repeat the same frozen analysis for `interpretable` and `mfcc` before making any structural claim.

## Advancement gate

A1.1 advances only after real-data reports are available and the result survives identity-confound review. A stable cluster may remain an unlabeled state such as `A-Z17`; stability alone never licenses a human-language meaning.
