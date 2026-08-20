# cat-pose-benchmark

**An open benchmark and capture methodology for temporally stable feline pose, facial,
ear, tail, contact, and scene-relative motion in real environments.**

> The repository name is provisional. The consumer cat brand and its products should
> remain separate from this research artefact.

---

## Status: research direction v0.2 + Stage 0 design

Created 2026-08-03. Visual benchmark direction revised 2026-08-04. Programme hierarchy revised 2026-08-21.

The project is no longer based on the assumption that a real benchmark must be either
fully hand-labelled or represented by one supposedly perfect source of truth. Its core
methodological position is now:

> **Each frame contains partially observable truths from different measurement sources,
> each with its own provenance and time-varying uncertainty.**

The Stage 0 rigid-target experiment is specified and its nominal mirror layouts have
been compared by a reproducible geometry-conditioning simulation. No animal collection
has started.

No outbound licence is set yet. Until the decisions in
[docs/OPEN-DECISIONS.md](docs/OPEN-DECISIONS.md) are resolved, the repository remains
all rights reserved. A licence must be added before any data, weights, or reusable code
are released.

## Programme context

This repository is **one research thread**, not the complete cat-intent programme.

The broader programme treats feline intent/state as a latent variable that may be
inferred from multiple evidence channels: visual motion, vocal and non-vocal audio,
objects and environment, human input and cat response, temporal routines, social and
proxemic context, individual history, physiology, and intervention outcomes.

See:

- [Feline intent research programme](docs/FELINE-INTENT-RESEARCH.md)
- [Beyond pose: what could a cat-intent system actually rely on?](posts/2026-08-21-beyond-pose.md)
- [Latent states before labels: when the confound detector catches us](posts/2026-08-21-latent-states-before-labels.md)

Within that programme, this repository is **V1 — Pose & motion benchmark**. Its job is to
make visual evidence measurable, temporally stable, provenance-aware and calibrated so
it can later be compared with or fused with other modalities.

## This thread's research objective

Build an open, licence-clean benchmark that can answer:

> Can an ordinary monocular RGB system recover feline surface pose and motion with
> calibrated uncertainty, using independent geometric and contact measurements only for
> a compact gold-standard subset?

The eventual app or puck should operate from one ordinary camera. More specialised
capture equipment exists only to establish whether the monocular system is correct.

## What counts as ground truth

The benchmark does **not** pretend that every anatomical joint is directly visible.
Annotations are separated into:

1. **Surface observations** — visible landmarks, contours, face points, ear geometry,
   and tail centreline.
2. **Contact observations** — paw location, support surface, take-off, landing, stance,
   and other independently measured contact events.
3. **Latent anatomical estimates** — joint centres or hidden geometry inferred through
   anatomical and temporal models. These are estimates, never silently promoted to
   direct truth.
4. **Scene-relative observations** — camera pose, surfaces, obstacles, object relations,
   and world-space trajectory.
5. **Temporal measurements** — displacement, velocity, acceleration, curvature change,
   blink timing, ear flicks, tail motion, gait phase, and recovery after occlusion.

Every observation records its source, quality tier, visibility, uncertainty, and
lineage. See [docs/GROUND-TRUTH-PROVENANCE.md](docs/GROUND-TRUTH-PROVENANCE.md).

## Proposed capture strategy

### 1. CatPose Portal — compact gold subset

A low-cost open capture appliance using one physical camera and calibrated mirrors to
produce simultaneous virtual views. A transparent or instrumented surface can add
independent paw-contact evidence.

This avoids multi-device synchronisation while preserving true simultaneous geometry
for fast ear, face, paw, and tail motion.

The first validation step is deliberately animal-free. See
[docs/STAGE-0-PORTAL-GEOMETRY.md](docs/STAGE-0-PORTAL-GEOMETRY.md).

### 2. Monocular real-home set — deployment benchmark

Ordinary owner-shot video under the conditions that break models: occlusion, motion
blur, dark and long fur, clutter, low light, changing viewpoint, multi-cat scenes, and
partial exits from frame.

A scene-mapping system may provide camera trajectory and static-world geometry, but
model-derived feline pose remains labelled as estimated supervision unless independently
validated.

### 3. Synthetic and reconstructed data — supplementary training only

Unity-generated data, personalised digital twins, and model-generated labels may support
pretraining, ablations, and rare-case coverage. They do not independently validate the
same assumptions used to generate them.

## Initial benchmark tracks

- Temporally stable 2D surface landmarks
- Ear articulation and facial landmark tracking
- Tail centreline and curvature tracking
- Calibrated 3D surface reconstruction on the gold subset
- Paw contact, gait events, take-off, and landing
- Occlusion recovery and long-horizon drift
- Scene-relative position and support-surface reasoning
- Confidence and uncertainty calibration
- Edge deployment accuracy, latency, memory, power, and thermal behaviour

## Product and programme boundary

This benchmark does not decode intent and does not claim literal semantic translation.
It produces calibrated visual measurements that may become evidence for downstream
multimodal state inference.

A future human-facing system should report probabilistic interpretations and uncertainty,
and its intent claims should be validated by predictive outcomes, intervention tests,
strong unimodal baselines, multimodal ablations, and individual-specific evaluation.

Pain, health, welfare, or diagnostic inference is a separate research and validation
programme. This repository produces measurement infrastructure, not veterinary claims.

## First public milestone

**CatPose Benchmark Protocol v0.1** should ship before model-building begins. It must
include:

- observable/latent ontology;
- keypoint and curve topology;
- provenance and uncertainty schema;
- minimal CatPose Portal experiment;
- real-home challenge taxonomy;
- metrics and acceptance gates;
- consent and redistribution requirements;
- one small demonstration sequence and Unity inspection view.

## Repository map

```text
docs/
  FELINE-INTENT-RESEARCH.md          umbrella multimodal programme and research threads
  RESEARCH-CHARTER.md               V1 visual benchmark question, hypotheses, and gates
  GROUND-TRUTH-PROVENANCE.md        observation tiers, uncertainty, and anti-circularity
  BENCHMARK-PROTOCOL-DRAFT.md       capture tiers, evaluation tracks, and v0 experiment
  STAGE-0-PORTAL-GEOMETRY.md        rigid-target mirror-layout experiment and gates
  KEYPOINT-TOPOLOGY-DRAFT.md        proposed landmarks and compatibility constraints
  PRIOR-ART-AND-LICENCE-SURVEY.md   existing resources and licence status
  LICENSING-POLICY.md               contamination and release constraints
  OPEN-DECISIONS.md                 unresolved choices that block collection

posts/
  2026-08-21-beyond-pose.md                  broader multimodal framing
  2026-08-21-latent-states-before-labels.md  L1 confound-detection methodology note

schemas/
  observation.schema.json           machine-readable observation/provenance draft

stage0/
  layouts.json                      nominal mirror planes and camera assumptions
  geometry_sim.py                   virtual-camera conditioning and covariance simulation
  geometry-conditioning-report.json generated nominal comparison; not measured evidence
  test_geometry_sim.py              reflection and triangulation invariants
```
