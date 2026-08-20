# A2.0 passive non-vocal audio protocol

Status: software/provenance slice for issue #62. No naturalistic A2 performance result exists yet.

## Question

Can generic non-vocal/environmental acoustic evidence from the **same prospective 0–5 s WAV already captured for A1** add held-out information beyond strong context/routine and vocal-acoustic baselines?

A2 is not a second cat translator. Its first job is passive context observation.

## Why this thread exists

A1 showed that vocal acoustics contain some cross-cat context signal, but also strong identity/owner/breed structure and weak probability calibration. CT1, meanwhile, gives us a strong structured context/routine baseline but requires those contextual facts to be captured explicitly.

A2 tests whether ordinary room audio can recover useful activity/environment evidence at zero additional sensing burden.

The hypothesis is therefore incremental:

`B0 context/routine`  
`A1 vocal acoustics`  
`A2 weak passive acoustic context`  
`B0 + A1 + A2`

All comparisons must eventually use the same held-out episodes.

## External taxonomy/model boundary

Generic pretrained audio models are permitted as weak feature extractors, not semantic authorities.

The initial projection vocabulary is intentionally conservative:

| A2 family | External acoustic names that may contribute | Specificity | Forbidden interpretation |
| --- | --- | --- | --- |
| `purr_acoustic` | `Purr` | cat-specific acoustic | affect/contentment ground truth |
| `surface_contact_proxy` | `Scratch`, `Scrape`, `Rub` | generic sound proxy | `cat_scratching` |
| `ingestion_sound_proxy` | `Chewing, mastication`, `Biting` | generic sound proxy | `cat_eating` |
| `liquid_sound_proxy` | `Liquid`, `Splash, splatter`, `Drip`, `Pour`, `Fill (with liquid)` | generic sound proxy | `cat_drinking` |
| `generic_activity` | all supplied classes | generic sound proxy | source/action identity |

Exact display-name matching is deliberate. For example, AudioSet's musical `Scratching (performance technique)` is not surface-contact `Scratch` and cannot enter that proxy family.

The programme should expect taxonomy noise. Public AudioSet pages themselves report materially different sample-quality estimates across classes such as Purr, Scratch and Scrape. A generic pretrained score is consequently a noisy measurement channel, not a label for what the cat did.

## Input contract

`audio/a2_score_packet.schema.json` represents frame-level scores already produced by a generic audio model. A2.0 does not bundle, download or fine-tune such a model.

Every packet must declare:

- event and episode identity;
- exact source-audio artifact SHA-256;
- exact sealed A1 record SHA-256;
- source-audio interval, ending no later than 5,000 ms;
- source model name/version/family;
- exact weights SHA-256;
- exact class-map SHA-256;
- ordered class IDs/display names;
- frame-relative start/end times;
- one score vector matching the declared class map;
- `semantic_ground_truth = false`.

The semantic validator additionally requires unique classes/frames, finite scores, non-decreasing timing and complete containment inside the immutable source-audio interval.

Overlapping acoustic frames are allowed because common audio-event models use overlapping windows.

## Frozen projection

For each configured proxy family:

1. match external class display names exactly;
2. for each frame, take the maximum score among matched classes in that family;
3. emit the mean and maximum of those per-frame proxy scores;
4. if no configured class exists in the source class map, emit `null` and `available=false`, never a silent zero.

Two deliberately generic activity summaries are also emitted:

- mean per-frame top-class score;
- mean number of classes per frame with score at least `0.25`.

This threshold is an instrumentation constant for A2.0, not a biological threshold.

## Evidence boundary

The projection output explicitly states:

- `semantic_ground_truth = false`;
- `intent_inference_performed = false`;
- `performance_analysis_performed = false`.

Feature provenance records configured and actually matched source classes, specificity and aggregation. Generic proxy names are the furthest semantic layer A2.0 is allowed to expose.

A high `ingestion_sound_proxy` score means only that a generic model heard something acoustically similar to its ingestion-related classes. It does not establish that the cat ate, that the sound came from the cat, or that the cat was hungry.

Likewise, `purr_acoustic` is an acoustic event feature. A2.0 does not convert it into an affect label.

## Naturalistic evaluation gate

No A2 performance analysis belongs in this PR.

Before real evaluation, freeze an adapter from A2 projection rows into the existing M1/shared-cohort machinery. Then compare on identical chronological/grouped held-out episodes:

1. B0;
2. A1;
3. A2;
4. B0 + A1;
5. B0 + A2;
6. A1 + A2;
7. B0 + A1 + A2.

Primary metrics remain paired log loss and Brier score. Balanced accuracy and calibration diagnostics remain secondary. Household/session/device/room association must be audited explicitly.

A2 advances only if it adds held-out probability information beyond the strongest relevant comparator, or under a separately frozen test measurably reduces the burden/error of explicit context observation.

Stable device, room, TV, appliance or microphone signatures are nuisance findings unless separately shown to generalise and add behavioural information.

## What A2.0 does not do

- no new recording window;
- no second microphone;
- no post-outcome audio;
- no large audio-model fine-tuning;
- no intent labels;
- no affect labels;
- no source-attribution claim;
- no assumption that public generic classes are feline action ground truth;
- no health, pain or welfare inference.

This keeps A2 falsifiable: it either adds useful passive context information on real held-out episodes, or it does not.
