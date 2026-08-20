# M1.2 modality-readiness and shared-cohort contract

Status: performance-blind cohort instrumentation for M1 #21 / M1.2 #44.

## Why this exists

M1.1 prevents a future result table from comparing different held-out episode sets. M1.2 moves that protection earlier: before any model is fit, it converts shared #18 events into one deterministic modality-readiness manifest and freezes the episode IDs available to the initial fusion matrix.

## Frozen first experiment

- observable target: `signalling_terminated`;
- target horizon: 60 seconds;
- B0 context snapshot: prospective CT1.2-valid event at `t0`;
- V1/A1 evidence window: 0–5,000 ms after event start;
- primary cohort: labelled strict-B0 episodes with both eligible V1 `visual_pose` and A1 `audio_vocalisation` observations.

The 5-second sensor evidence window is frozen before compatible real M1 data exist. Sensor observations ending after 5,000 ms are listed separately and are not eligible inputs to this experiment.

## Same cohort for every primary ablation

The manifest assigns the exact same sorted episode IDs to:

`B0`, `V`, `A`, `BV`, `BA`, `VA`, `BVA`, `BVA-V`, and `BVA-A`.

This is intentionally conservative. A larger V1-only or A1-only dataset may be described as a separate sensitivity dataset, but it cannot replace the shared complete-case cohort in the headline incremental-information comparison.

## Event-level fields

Each manifest event contains only integration metadata:

- event, episode, subject, household and session IDs;
- start timestamp;
- target availability/value;
- B0/V1/A1 support flags;
- exact eligible V1/A1 observation refs;
- post-5s sensor refs that were excluded;
- observed and declared-missing modality sets;
- modality conflicts;
- primary-cohort eligibility;
- explicit exclusion reasons.

No predictor is fit and no feature/target association or performance metric is calculated.

## Target semantics

A `true` termination observation may occur at any time within the 60-second horizon. A `false`/continued label must be observed at the 60-second horizon; an earlier `false` observation does not prove the episode remained active through 60 seconds.

Contradictory boolean termination annotations are excluded rather than reconciled post hoc. Missing/unknown termination remains visible in the manifest but is not scored.

## Modality integrity

An observation does not count as modality support when the same modality is declared in `missing_modalities`. Such records are flagged as conflicts. V1/A1 observations after the frozen 5-second evidence cutoff are retained in provenance but cannot make an episode primary-cohort eligible.

## Usage

Generate the software-only fixture and manifest:

```bash
python -m fusion.fixtures.m1_cohort_events --output /tmp/m1-events.json
python -m fusion.m1_cohort_manifest /tmp/m1-events.json --output /tmp/m1-cohort.json
```

For future real data, the input remains a JSON array of #18 event records. The resulting `primary_episode_sha256` and per-row episode IDs should be carried into the M1.1 result contract so result-time validation can verify that the frozen cohort was not changed after model fitting.

## Boundaries

- The synthetic fixtures are software tests only.
- M1.2 does not create CT1.3 owner-operated episodes.
- A one-household cohort does not imply cross-cat or cross-household generalisation.
- No `true_intent`, emotion, pain, disease or literal-language target is created here.
