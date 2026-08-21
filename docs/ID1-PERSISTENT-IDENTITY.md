# ID1 — Persistent feline identity and re-identification

**Status:** ID1.0 protocol frozen before feline REMIND results  
**Date:** 2026-08-22  
**Parent:** #68

## Research question

Can a visual system preserve the identity of the same physical cat across time when ordinary frame-to-frame tracking is no longer enough?

This is infrastructure for the wider feline-intent programme. It is not itself an intent, affect, language, health, or welfare model.

A downstream temporal model can only learn an individual cat's routines, vocal signatures, interaction history, adaptation curve, or response to interventions if observations attributed to that cat are actually from the same physical animal. ID1 therefore makes persistent subject association an independently measurable research problem.

## Why REMIND is the first baseline

ID1.0 uses **REMIND — RE-Identification with Memory for INDoor Navigation** (Diaz-Pereda et al., 2026, arXiv:2607.09267) as the first external long-term ReID baseline.

The upstream method is relevant because it:

- is online and monocular-RGB;
- does not require camera pose or depth;
- uses frozen DINOv3 patch features;
- maintains dual-bank appearance memory;
- includes global, part-level, and local-background descriptors;
- uses neighbour/context memory and Hungarian assignment;
- exposes ambiguous and provisional decisions instead of always forcing an identity;
- evaluates IDF1, identity switches, fragmentation, recovery, uncertainty, and runtime diagnostics.

The upstream repository is MIT licensed. ID1 does **not** vendor or silently modify it.

Frozen upstream revision:

`cvar-vision-dl/remind-reid-tracker@f88ea1d5d81da0a8ed28b206df6d4dab48327342`

The upstream authors report strong performance on generic indoor-object re-identification. Those numbers motivate the baseline but are not evidence of feline performance.

## Why cats are a distinct stress case

A cat is not a rigid indoor object. Persistent feline identity adds failure modes that may expose limitations in generic appearance memory:

- extreme non-rigid articulation;
- self-occlusion and curled/sitting/lying posture changes;
- large visible-area changes between frontal, dorsal, lateral and rear views;
- fur texture that can be repetitive or low-contrast;
- head/body appearance changing with grooming, lighting and motion blur;
- multiple same-breed or same-colour cats;
- close social contact where bodies overlap;
- crossing trajectories;
- rapid movement followed by long disappearance and re-entry;
- growth or long-term appearance change in later longitudinal work.

This is why REMIND should first be treated as a **baseline**, not assumed to solve feline identity unchanged.

## Frozen ID1.0 comparison

The first quantitative feline experiment compares the same labelled sequence wherever compatible:

1. `short_term_temporal_baseline` — the strongest already-available V1-compatible temporal/segmentation tracker that can be evaluated under the same identity ground truth;
2. `remind_unmodified` — the pinned upstream REMIND baseline.

Feline-specific modifications are blocked until the unmodified baseline has been measured. This prevents tuning the problem definition after seeing which cases REMIND fails on.

## Stress strata

Every scored interval must be assigned prospectively to one or more of the frozen strata below.

| Stratum | Operational question |
| --- | --- |
| `ordinary_continuity` | Can identity be maintained in ordinary visible motion? |
| `short_occlusion` | Does identity survive a brief partial/full occlusion? |
| `long_gap_reentry` | Is the same cat recovered after leaving the view for a meaningful temporal gap? |
| `viewpoint_pose_deformation` | Does identity survive major viewpoint or body-configuration change? |
| `illumination_change` | Does identity survive substantial lighting/exposure change? |
| `lookalike_multicat` | Can visually similar cats remain distinct in the same sequence? |
| `crossing_close_interaction` | Can IDs remain stable through close contact, overlap, or trajectory crossing? |

A sequence can contribute to multiple strata, but stratum assignment must not be chosen after observing model errors.

## Ground truth requirement

A real quantitative ID1 result requires persistent physical-cat identity ground truth. At minimum the run manifest must bind:

- pseudonymous subject IDs;
- source sequence ID and SHA-256;
- identity ground-truth artifact SHA-256;
- the exact upstream REMIND commit;
- declared stress strata;
- whether the run is quantitative;
- an explicit statement that persistent subject ground truth exists.

Synthetic/software fixtures may test the adapter and metric contract but cannot become a feline identity result.

## Metrics

### Primary

- `idf1` — identity F1 across visible GT observations;
- `idsw` — identity switches;
- `frag` — fragmentation;
- `tracking_recall` — visible GT cases correctly tracked;
- `reopen_rate_existing` — rate at which an already-known subject is incorrectly reopened as new;
- `objects_recovered_reference` — subjects that recover their original reference identity after disruption;
- `coverage_firm` — fraction of cases for which the system makes a firm decision;
- `firm_accuracy` — accuracy conditioned on a firm decision;
- `uncertain_rate` — ambiguity/provisional decision rate.

### Resource diagnostics

- `total_runtime_seconds`;
- `avg_loop_ms`.

Additional REMIND telemetry may be retained for diagnosis, but ID1.0 should not move the headline goalposts after results are observed.

## Ambiguity is not automatically failure

For the intended downstream system, a calibrated `unknown / ambiguous identity` can be safer than a confident identity swap.

Therefore ID1 reports both identity quality and decision coverage. A system that obtains higher apparent accuracy by silently discarding difficult observations or constantly abstaining is not necessarily better. Conversely, forcing every frame to a subject ID can contaminate long-term personalisation data.

This makes `coverage_firm`, `firm_accuracy`, and `uncertain_rate` first-class alongside IDF1.

## Adapter and provenance boundary

`identity/remind_adapter.py` consumes the upstream `summary_global.csv` plus an ID1 run manifest and emits a compact `ID1-result-v0` packet.

The adapter fails closed when:

- the upstream revision differs from the frozen commit;
- a quantitative run lacks persistent subject ground truth;
- sequence/ground-truth hashes are malformed;
- an undeclared stress stratum is used;
- a quantitative run is missing a frozen primary metric.

Every emitted packet explicitly states that intent inference, translation claims, and health/welfare inference were not performed.

## First execution packet

A quantitative REMIND run should be launched only when a provenance-valid labelled feline sequence exists in an execution environment. The upstream evaluator already supports custom DAVIS-style frame/mask/metadata inputs, so ID1 should adapt the dataset to that interface rather than fork REMIND prematurely.

Conceptually:

```text
labelled cat frames + persistent instance masks
    -> upstream REMIND @ frozen commit
    -> testing/run_tracking_batch.py custom DAVIS input
    -> summary_global.csv + per_case.csv + telemetry
    -> identity.remind_adapter + frozen run manifest
    -> ID1-result-v0
    -> stratum analysis / baseline comparison
```

Raw household video and private identity annotations remain local unless an explicit data-release decision is made.

## What to try only after the baseline

If unmodified REMIND fails systematically, candidate feline adaptations become separate ablations rather than hidden improvements:

1. face/head-specific descriptors;
2. fur-pattern descriptors;
3. pose-normalised body-part descriptors;
4. gait or temporal-motion identity signatures;
5. explicit occlusion-state memory;
6. later multimodal identity evidence such as vocal signature or household context.

Each adaptation should answer a narrow question: **does this cue reduce identity error on held-out cats or held-out sequences beyond the frozen REMIND baseline?**

## Relationship to other threads

ID1 is upstream infrastructure for several programme threads:

- **T1 temporal routines:** prevents history from being assigned to the wrong cat;
- **P1 personalisation:** defines whose adaptation history is being learned;
- **S1 social/proxemic context:** keeps multiple cats distinct during interactions;
- **A1/A2 audio:** enables later study of whether vocal identity agrees with visual identity;
- **M1 fusion:** can use identity confidence as provenance/uncertainty, not as intent evidence;
- **L1 latent-state discovery:** reduces the risk that clusters are artefacts of accidental cross-subject mixing.

ID1 does not replace V1 pose/motion. V1 asks what the body is doing; ID1 asks whose body/observation this is across time.

## Advancement rule

ID1.0 advances from protocol/software-only to an empirical baseline only after a provenance-valid feline sequence is executed through the frozen upstream revision and the result packet passes the adapter.

Until then the correct result is:

`feline_remind_performance = not_run`
