# V1 → M1 pose-package contract

Status: v0 contract frozen before prospective visual data or a deployable real-home V1 pose model exists.

## Why this exists

M1's `visual_pose` row is supposed to represent measured or explicitly estimated feline pose/motion evidence. A file being syntactically JSON is not enough.

The first M1 sensor-sidecar implementation deliberately rejected raw video masquerading as pose, but its initial JSON check was still too weak: an arbitrary object could be sealed as `visual_pose`. This contract closes that gap before real fusion data exist.

A pose package that passes this contract is **eligible evidence**, not validated truth. Pose accuracy, calibration, generalisation and incremental outcome-prediction value remain separate empirical questions.

## Canonical files

- package schema: `fusion/v1_pose_package.schema.json`
- semantic validator: `fusion/v1_pose_package.py`
- underlying observation/provenance schema: `schemas/observation.schema.json`
- provenance doctrine: `docs/GROUND-TRUTH-PROVENANCE.md`
- M1 sidecar integration: `fusion/m1_sensor_sidecar.py`

A prospective `visual_pose` reservation must use:

```text
fusion/v1_pose_package.schema.json
```

as its `schema_ref`.

## Package boundary

The package records:

- CT1 event and episode IDs;
- a V1 sequence ID and pseudonymous subject ID;
- the exact event-relative evidence window;
- producer kind, name and version;
- learned-model family and weights SHA-256 when a model produced the estimates;
- source-media record IDs and content hashes, without local filesystem paths;
- timestamped/frame-indexed samples;
- one or more provenance-bearing V1 observations per sample.

The package's evidence window must exactly equal the reserved M1 visual sidecar interval and remain inside the frozen first-experiment 0–5,000 ms sensor window.

## What counts as V1 evidence in M1 v0

Allowed observation classes are intentionally narrower than the complete benchmark ontology:

- `surface_landmark`;
- `surface_curve`;
- `latent_anatomy`;
- `derived_temporal`.

`scene_geometry` is excluded from the V-only comparator because location/object/environment information belongs in B0/CT1 and allowing it inside V would blur the ablation boundary. `contact_event` is also outside this first ordinary-camera visual package.

Allowed prospective evidence tiers:

- G2 — simultaneous geometry;
- G3 — human-verified visual;
- S1 — constrained estimate;
- S2 — model pseudo-label.

X1 synthetic-exact observations and U0 unlabelled media cannot satisfy real prospective V1 support. They remain useful elsewhere in V1 but do not make an M1 household episode visually complete.

## Required value and uncertainty

Every included observation must:

- validate against `schemas/observation.schema.json`;
- match the package subject, sequence and enclosing frame index;
- contain an actual `mean` estimate/value;
- carry uncertainty through `covariance` or `confidence_region`;
- retain visibility, evidence tier, quality, source IDs and lineage.

This is deliberately stricter than the current generic observation draft. M1 should not convert an unquantified pose guess into apparently precise fusion evidence merely because a detector emitted coordinates.

## Learned-model provenance

A `learned_model` producer must declare:

- producer name;
- producer version;
- model family;
- exact weights SHA-256.

A later model change therefore creates a different producer fingerprint. Results from two different weights files cannot silently share one V1 provenance identity.

## Two validation moments

### Seal time

The local pose package must already:

- satisfy package/schema semantics;
- match the reserved event and episode IDs;
- match the exact reserved evidence interval;
- contain valid V1 observations.

The sidecar seal stores only hashes and summarized metadata in the eventual derived #18 event. Raw/local paths remain local.

### Composition time

Before the sealed sidecar can enrich a finalized CT1 event, the package is revalidated against that actual CT1 record. In particular, package subject/event/episode identity must match the CT1 event.

This prevents a structurally valid pose file from another cat or episode being attached to the wrong household event.

## Seal metadata

A valid pose package contributes auditable summary metadata including:

- package version;
- event/episode/sequence/subject identifiers;
- evidence window;
- sample and observation counts;
- observation-class counts;
- evidence-tier counts;
- quality counts;
- producer identity and producer fingerprint;
- source-media count.

These are provenance summaries, not pose-performance metrics.

## What this contract does not prove

Passing the validator does **not** prove:

- landmark correctness;
- calibrated covariance;
- temporal stability;
- cross-cat generalisation;
- resistance to occlusion or lighting changes;
- that V1 adds information beyond CT1 or A1;
- feline intent or semantics.

Those claims require the V1 benchmark and M1 held-out ablations. The package contract exists only to ensure those future experiments start from traceable, non-empty, temporally valid visual evidence.
