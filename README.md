# cat-pose-benchmark

**An open, software-first benchmark for temporally stable feline pose, face, ears, tail,
contact, and scene-relative motion in real environments.**

> The repository name is provisional. The consumer cat brand and its products remain
> separate from this research artefact.

---

## Status: research direction v0.2 — software-first

Created 2026-08-03. Direction revised 2026-08-04.

The programme is designed so its lead developer performs **no bespoke physical capture,
rig construction, calibration-lab work, or hardware fabrication**. Physical activity is
limited to ordinary user testing of an eventual app or manufactured product.

The methodological position remains:

> **Each frame contains partially observable truths from different sources, each with
> its own provenance and time-varying uncertainty.**

Synthetic exact labels, observable real-video labels, model-derived reconstructions, and
independent external measurements are distinct evidence tiers. They are never silently
flattened into one supposedly perfect skeleton.

No animal collection has started. No outbound licence is set yet. Until the decisions in
[docs/OPEN-DECISIONS.md](docs/OPEN-DECISIONS.md) are resolved, the repository remains
all rights reserved.

---

## Research objective

Build an open, licence-clean benchmark that can answer:

> Can an ordinary monocular RGB system recover temporally stable feline surface pose and
> motion with calibrated uncertainty, learning from exact simulation and observable real
> video, and later passing an independently operated hidden-gold evaluation?

The product system is monocular. Specialised measurement equipment is optional external
evaluation infrastructure, not something the project lead must construct or operate.

## Evidence tiers

### Tier S — synthetic exact

Unity-generated scenes provide exact:

- articulated feline pose and surface coordinates;
- ear, face, and tail-spline state;
- displacement, velocity, acceleration, and angular motion;
- paw contact and support surfaces;
- camera and scene geometry;
- visibility, occlusion, lighting, motion blur, and sensor conditions.

Synthetic labels validate algorithms and controlled failure modes. They do not, by
themselves, prove real-cat accuracy.

### Tier R2 — real observable

Consented or licence-clean real video is annotated only for externally observable facts:

- visible facial and body landmarks;
- ear boundaries and orientation cues;
- tail centreline and visibility;
- silhouettes and contact evidence;
- timing, track continuity, occlusion, and re-detection.

This tier supports real-domain 2D and temporal evaluation without fictional hidden 3D
truth.

### Tier R3 — reconstructed

Monocular or remotely contributed multi-view footage may produce articulated 3D, scene,
and contact estimates through geometry, learned priors, and temporal constraints. Every
such value remains labelled as model-derived with explicit uncertainty and lineage.

### Tier G — external hidden gold

A laboratory, data partner, or independent contributor may later operate synchronized
cameras, Vicon, pressure walkways, calibrated RGB-D, mirrors, or another traceable system.
The project supplies protocols, schemas, QA software, and evaluation tooling; the partner
supplies measurements.

Tier G may remain private behind an evaluation server. The public project does not block
on it and must not claim externally verified metric 3D accuracy until it exists.

## What counts as ground truth

The benchmark does **not** pretend that every anatomical joint is directly visible.
Annotations are separated into:

1. **Surface observations** — visible landmarks, contours, face points, ear geometry,
   and tail centreline.
2. **Contact observations** — paw location, support surface, take-off, landing, and
   stance where independently observable or measured.
3. **Latent anatomical estimates** — hidden joint centres inferred through anatomical
   and temporal models; always distributions or estimates.
4. **Scene-relative observations** — camera pose, surfaces, obstacles, spatial
   relations, and world-space trajectory.
5. **Temporal measurements** — displacement, velocity, acceleration, curvature change,
   blink timing, ear flicks, gait phase, and recovery after occlusion.

Every observation records source, tier, visibility, uncertainty, and lineage. See
[docs/GROUND-TRUTH-PROVENANCE.md](docs/GROUND-TRUTH-PROVENANCE.md).

## Software-first execution path

### 1. CatSynth4D — Unity exact-data generator

Build procedural feline scenes with controllable morphology, animation, camera motion,
lighting, clutter, occlusion, sensor degradation, and exact annotation export.

### 2. CatPose-Wild — real-video temporal benchmark

Build a licence-clean challenge set for visible surfaces, face, ears, tail, temporal
stability, occlusion recovery, and confidence calibration.

### 3. Uncertainty-calibrated monocular reconstruction

Train and evaluate articulated 3D and scene-relative models using Tier S for exact
controlled evaluation and Tier R2 for real-domain observable evaluation. Tier R3 outputs
remain estimates.

### 4. External validation interface

Publish a capture-neutral contract that any qualified laboratory can implement. External
results plug into the same observation schema and hidden evaluation service.

### 5. Product demonstrations

Ship a playful monocular translator app, then an edge-deployed puck or AR analyser. The
lead developer may test these as a user but does not fabricate prototypes or operate a
measurement rig.

## Initial benchmark tracks

- Temporally stable 2D surface landmarks
- Ear articulation and facial landmark tracking
- Tail centreline, topology, and curvature tracking
- Occlusion recovery and long-horizon drift
- Scene-relative position and support-surface reasoning
- Synthetic exact 3D pose, contact, and derivative recovery
- Confidence and uncertainty calibration
- Synthetic-to-real transfer
- Edge deployment accuracy, latency, memory, power estimates, and thermal constraints
- External hidden-gold metric 3D when a partner dataset becomes available

## Product boundary

The first consumer “translator” may use measured motion to create playful,
clearly-labelled entertainment outputs. It must not imply literal semantic translation.

Pain, health, welfare, or diagnostic inference is a separate research and validation
programme. This repository produces measurement infrastructure, not veterinary claims.

## First public milestone

**CatPose Benchmark Protocol v0.1** should ship before a broad model-training effort. It
must include:

- observable/latent ontology;
- keypoint and curve topology;
- provenance and uncertainty schema;
- synthetic scene and annotation contract;
- real-video challenge taxonomy;
- temporal, calibration, and transfer metrics;
- consent and redistribution requirements;
- one Unity-generated demonstration sequence and inspection view;
- one real-video observable demonstration sequence;
- external-validation interface specification.

## Repository map

```text
docs/
  RESEARCH-CHARTER.md                 locked question, hypotheses, and gates
  SOFTWARE-FIRST-ROADMAP.md           zero-owner-physical-work execution plan
  EXTERNAL-VALIDATION-CONTRACT.md     partner-operated hidden-gold interface
  GROUND-TRUTH-PROVENANCE.md          observation tiers and anti-circularity
  BENCHMARK-PROTOCOL-DRAFT.md         data tiers, tasks, metrics, and release gate
  KEYPOINT-TOPOLOGY-DRAFT.md          proposed landmarks and curve topology
  PRIOR-ART-AND-LICENCE-SURVEY.md     existing resources and licence status
  LICENSING-POLICY.md                 contamination and release constraints
  OPEN-DECISIONS.md                   unresolved choices

schemas/
  observation.schema.json             observation/provenance draft
  stage0-capture-manifest.schema.json optional external-rig manifest

stage0/
  layouts.json                        archived/optional portal geometry assumptions
  geometry_sim.py                     virtual-camera simulation
  hardware_feasibility.py             evidence for rejecting owner-purchased rig

unity-viewer/
  Assets/Scripts/Stage0Viewer.cs      current geometry inspection prototype

synthetic/                             next primary implementation area
real_video/                            observable-label benchmark pipeline
baselines/                             pose, tracking, reconstruction, calibration
evaluation/                            metrics and hidden-gold adapter
edge/                                  quantisation and deployment evaluation
hardware/                              simulated RTL/HLS and verification workflow
```

The former portal work is retained as an optional external-validation design study. It is
not on the critical path and creates no requirement for the project lead to purchase,
build, calibrate, or operate physical apparatus.
