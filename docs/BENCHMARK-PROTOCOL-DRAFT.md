# Real-environment benchmark protocol — DRAFT v0.1

**Status:** specification work may proceed; collection remains blocked by the open
decisions listed at the end of this document.

## Purpose

Evaluate whether a monocular RGB system can recover feline surface pose, face, ears,
tail, contact, and scene-relative motion with calibrated uncertainty in real conditions.

The benchmark does not require every frame to have one complete exact skeleton. It uses
multiple evidence sources, and every observation retains its provenance and uncertainty.
See [GROUND-TRUTH-PROVENANCE.md](GROUND-TRUTH-PROVENANCE.md).

## Data tiers

### Tier A — CatPose Portal geometric gold

A compact capture volume using one physical camera and calibrated mirrors to create
simultaneous virtual views. The initial design should aim for:

- one direct view;
- at least two reflected views with useful triangulation baselines;
- a calibration object visible in each view;
- a known metric reference;
- global-shutter or sufficiently short exposure for fast motion;
- voluntary movement through or within the capture area.

The portal establishes reference geometry for visible surface landmarks and curves. A
transparent floor or mirror may expose paws from below.

### Tier B — contact gold

A transparent or instrumented support surface may independently measure:

- paw location;
- contact start and end;
- stance duration;
- take-off and landing;
- support-surface transitions.

The first pilot can use visual underside contact before adding force or pressure sensing.
Contact hardware must not materially alter natural movement.

### Tier C — real-home challenge set

Ordinary monocular videos recorded in natural environments. These represent the product
domain and may have incomplete reference labels.

This tier evaluates:

- generalisation from the portal to homes;
- occlusion and re-detection;
- camera movement;
- long-horizon temporal stability;
- uncertainty and abstention;
- scene-relative reasoning where a map is available.

### Tier D — synthetic and reconstructed support data

Unity rendering, personalised cat models, scene reconstruction, constrained fitting, and
pseudo-labels may be used for training or ablation. Their source tier must remain visible,
and they cannot be the sole reference for real-world accuracy claims.

## Observable target set

The final topology remains open, but v0 should prioritise variables that are both
behaviourally relevant and externally observable.

### Face and head

- nose;
- eye corners or eye aperture representation;
- muzzle or mouth boundary where resolvable;
- ear bases, tips, and orientation-supporting boundary points;
- head orientation.

### Body and limbs

- visible shoulder/scapular surface landmarks;
- visible hip/pelvic surface landmarks;
- elbows, carpi, paws, stifles, hocks where externally resolvable;
- body centreline or silhouette representation;
- paw-contact regions.

### Tail

The tail should be represented as a centreline curve with:

- tail base anchor;
- ordered samples or spline control points;
- local curvature;
- tip location where visible;
- per-sample visibility and uncertainty.

A three-point tail is retained only as a compatibility export, not the canonical format.

### Latent anatomy

Hidden joint centres may be provided as optional estimates with distributions. They are
not required for the first gold benchmark and must not displace visible surface targets.

## Minimal capture experiment

The first experiment must validate the measurement system before collecting a dataset.

### Stage 0 — rigid-object validation

Use a rigid calibration object with known fiducials moving through the intended capture
volume.

Measure:

- virtual-camera calibration repeatability;
- triangulation error across the usable volume;
- sensitivity to mirror-plane error;
- temporal alignment within the single recorded frame;
- reconstruction error by depth and view combination;
- failure near mirror boundaries and grazing angles.

Do not involve an animal until this experiment produces a documented uncertainty model.

### Stage 1 — articulated non-animal validation

Use a deformable or articulated object with known control points, such as a rigged model,
segmented tail analogue, or articulated test target.

Evaluate:

- fast curve motion;
- self-occlusion;
- motion blur;
- point identity through crossing or overlap;
- derivative recovery.

### Stage 2 — one voluntary feline pilot

Record one short, non-coercive sequence involving simple natural actions, for example:

- walking through the portal;
- standing and turning;
- sitting;
- following a toy;
- tail movement while otherwise stationary.

Outputs:

- calibrated views;
- visible landmarks;
- tail curve;
- visibility states;
- per-observation covariance or bounded uncertainty;
- a Unity inspection scene;
- documented failures.

No behaviour or health labels are required for this pilot.

## Real-environment stratification

A full factorial design is not realistic for v0. Use a predeclared fractional design
covering primary effects and selected high-risk interactions.

### Fur and morphology

- short, light or high-contrast coat;
- short, dark solid coat;
- patterned coat;
- long-haired coat;
- hairless or minimally fur-obscured upper-bound case;
- at least one substantially different facial/body morphology when available.

Avoid treating breed labels as precise morphology. Record observable coat and body
features directly.

### Motion

- static or near-static;
- slow locomotion and grooming;
- fast locomotion, jumping, or play;
- isolated tail movement;
- rapid ear/head movement;
- transitions between motion regimes.

### Lighting and capture

- indirect daylight;
- warm domestic artificial light;
- low light and sensor noise;
- mixed or backlit scene;
- different image scales and viewpoints;
- handheld camera movement;
- ordinary consumer frame rates and exposure behaviour.

### Environment and occlusion

- uncluttered indoor;
- cluttered indoor;
- soft furnishings and similar-coloured backgrounds;
- partial furniture occlusion;
- full temporary occlusion;
- frame exit and re-entry;
- more than one cat or another moving subject.

Each sequence must record which strata are present. Uncovered strata remain explicit
coverage gaps.

## Tasks

### T1 — 2D surface landmark estimation

Evaluate visible landmarks and prediction uncertainty in image coordinates.

### T2 — temporal tracking

Evaluate identity stability, jitter, drift, occlusion survival, re-detection, and
trajectory continuity.

### T3 — face, eye, and ear dynamics

Evaluate orientation, aperture or blink events, ear motion, and temporal derivative
quality where image scale permits.

### T4 — tail curve tracking

Evaluate centreline distance, curve topology, curvature, tip motion, and recovery after
self-occlusion.

### T5 — 3D surface reconstruction on gold sequences

Evaluate metric surface landmarks and curves against simultaneous-view observations.
Depth uncertainty must be reported separately from lateral uncertainty.

### T6 — contact and gait events

Evaluate paw assignment, contact location, stance interval, take-off, landing, and
support-surface association.

### T7 — scene-relative reasoning

Evaluate cat trajectory and relations such as on, under, inside, behind, approaching,
and retreating where sufficient scene evidence exists.

### T8 — calibrated confidence

Evaluate whether declared confidence or uncertainty predicts realised error and whether
the system abstains appropriately.

### T9 — deployment efficiency

Report accuracy together with sustained latency, frame rate, memory, model size, power,
and thermal behaviour on declared hardware.

## Metrics

### Spatial accuracy

- 2D point error normalised by a declared body or head scale;
- PCK or OKS-compatible exports for comparison;
- 3D point error for gold observations;
- tail-curve distance and curvature error;
- camera and scene error where applicable.

### Temporal accuracy

- positional jitter during true low-motion intervals;
- velocity and acceleration error;
- temporal event onset and duration error;
- track survival through occlusion;
- accumulated drift;
- re-detection delay;
- identity switches;
- foot sliding during contact.

### Calibration

- confidence-region coverage;
- expected calibration error;
- negative log likelihood or proper scoring rule where distributions are available;
- risk–coverage curve;
- error by visibility and evidence tier.

### Stratified reporting

All primary results must be reported by relevant fur, motion, lighting, viewpoint,
occlusion, and environment strata. A single aggregate score is insufficient.

## Annotation and review

Manual work should target semantic identification, ambiguity resolution, and quality
control—not frame-by-frame recreation of measurements that geometry can provide.

The protocol must define:

- annotator instructions;
- distinction between visible surface landmarks and inferred anatomy;
- how uncertainty or ambiguity is entered;
- blinded review where feasible;
- inter-annotator or repeated-annotation analysis;
- adjudication and post-hoc correction logs.

## Sourcing, consent, and redistribution

Allowed sources for released real media:

1. self-recorded footage with explicit release terms;
2. solicited owner contributions under a sequence-level agreement;
3. institutional or shelter collaboration with documented authority and approvals;
4. individually verified permissive sources only when their exact terms allow the
   intended redistribution and downstream use.

No scraping, assumed permission, CC BY-NC, research-only, or licence-ambiguous source may
enter a released dataset or production dependency.

Each sequence needs machine-readable records for:

- media owner and contributor;
- people or private information present;
- consent and withdrawal process;
- redistribution rights;
- commercial and research use permissions;
- licence version;
- capture device and protocol version.

## v0.1 release contents

Protocol v0.1 is complete when the repository contains:

- frozen pilot landmark/curve ontology;
- observation and provenance schema;
- portal geometry and calibration specification;
- rigid-object validation report;
- one articulated-object test;
- one voluntary feline pilot;
- minimal Unity viewer;
- baseline evaluation script;
- documented uncertainty and limitations;
- consent/licensing templates suitable for review.

## Open decisions blocking collection

- final pilot landmark and tail-curve topology;
- portal mirror layout, dimensions, materials, and camera specification;
- whether v0 uses visual underside contact only or an instrumented surface;
- numerical geometry and calibration acceptance thresholds;
- minimum image rate and shutter requirements;
- outbound licences and contributor terms;
- ethics and animal-welfare review requirements for the intended capture protocol;
- first monocular baseline and its licence suitability;
- smallest useful real-home challenge sample after the portal pilot.
