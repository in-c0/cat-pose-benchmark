# Real-environment benchmark protocol — DRAFT v0.2

**Status:** software implementation may proceed. No owner-operated physical capture is
required for v0.1.

## Purpose

Evaluate whether a monocular RGB system can recover feline surface pose, face, ears,
tail, contact evidence, and scene-relative motion with calibrated uncertainty in real
conditions.

The benchmark does not require every frame to have one complete exact skeleton. It uses
multiple evidence sources, and every observation retains its provenance and uncertainty.
See [GROUND-TRUTH-PROVENANCE.md](GROUND-TRUTH-PROVENANCE.md).

## Physical-work policy

The lead developer does not construct, fabricate, calibrate, or operate a bespoke
capture rig and does not personally collect research footage as a prerequisite.

Permitted physical involvement is limited to ordinary use-testing of an app or an
externally manufactured product.

Any specialised measurement is supplied by:

- a remote contributor following a guided protocol;
- an institutional or laboratory partner;
- an existing licence-clean dataset;
- a product manufacturer or test service.

## Data tiers

### Tier S — synthetic exact

Unity-generated scenes provide exact state and annotations for:

- feline articulated pose and surface landmarks;
- eye, muzzle, ear, and head state;
- tail centreline, spline controls, curvature, and topology;
- paw contact, support surfaces, and locomotion events;
- camera intrinsics, extrinsics, trajectory, and scene geometry;
- visibility, occlusion, clutter, lighting, motion blur, and sensor degradation;
- displacement, velocity, acceleration, and angular derivatives.

Tier S is the primary exact-data source for v0.1. It supports controlled evaluation,
pretraining, ablation, stress testing, and deterministic regression tests. It does not
independently prove real-cat metric accuracy.

### Tier R2 — real observable

Licence-clean or consented ordinary monocular video with labels restricted to facts that
can be externally observed and reviewed:

- visible surface landmarks;
- eye aperture or blink events where resolvable;
- ear boundary and orientation cues;
- silhouette and body centreline;
- visible paw centres and contact evidence;
- tail centreline and visibility;
- track continuity, occlusion, exit, re-entry, and event timing.

Tier R2 is the primary real-domain benchmark for v0.1. Hidden joints and metric depth are
not treated as known.

### Tier R3 — reconstructed estimates

Monocular or remotely contributed multi-view footage may produce:

- articulated 3D pose;
- personalised feline shape;
- scene maps and world trajectories;
- inferred contact;
- latent joint distributions.

These are model-derived observations. They retain the generating method, checkpoint,
constraints, uncertainty, and lineage. They may be used for training or analysis but may
not serve as the sole evidence for the same model family’s accuracy.

### Tier G — external hidden gold

A laboratory or independent data partner may later operate synchronized cameras, Vicon,
calibrated RGB-D, pressure walkways, a mirror portal, or another traceable system.

The project supplies:

- target ontology and schemas;
- capture-neutral protocol;
- automated QA;
- calibration and file manifests;
- encrypted or private upload tooling;
- hidden evaluation adapter.

The partner supplies and operates the physical apparatus. Tier G may remain private and
serve only through an evaluation API. It is not a blocker for v0.1, but externally
verified real-world metric 3D claims are blocked until it exists.

## Observable target set

The final topology remains open, but v0 prioritises variables that are both behaviourally
relevant and externally observable.

### Face and head

- nose;
- eye corners or eye-aperture representation;
- muzzle or mouth boundary where resolvable;
- ear bases, tips, and orientation-supporting boundary points;
- head orientation cues.

### Body and limbs

- visible shoulder/scapular and hip/pelvic surface landmarks;
- elbows, carpi, paws, stifles, and hocks only where externally resolvable;
- body centreline and silhouette representation;
- visible paw-contact regions.

### Tail

The canonical tail representation is a centreline curve with:

- tail-base anchor;
- ordered samples or spline control points;
- local curvature;
- tip location where visible;
- per-sample visibility and uncertainty.

A three-point tail is retained only as a compatibility export.

### Latent anatomy

Hidden joint centres may be provided as optional Tier R3 distributions. They are not
required for the first public benchmark and do not displace visible surface targets.

## Software-first implementation stages

### Stage S0 — deterministic Unity annotation proof

Create one rigged feline scene and export:

- camera parameters;
- 2D and 3D surface landmarks;
- tail spline;
- visibility and occlusion state;
- contact state;
- exact motion derivatives;
- scene objects and support surfaces.

Tests must verify that exported values match Unity state within declared numeric
tolerance.

### Stage S1 — procedural variation and challenge generation

Add controlled variation for:

- morphology and body proportions;
- short, long, patterned, dark, and light coats;
- ear and tail articulation;
- walking, sitting, turning, grooming, jumping, play, and rapid local motion;
- camera movement, focal length, distance, and image scale;
- domestic lighting, noise, blur, compression, clutter, and occlusion;
- one or more cats and distractor animals.

Invalid anatomy, surface penetration, foot sliding, and impossible motion must be detected
and excluded rather than hidden by rendering quality.

### Stage R0 — one real observable sequence

Add one sequence whose rights permit the intended benchmark use. Produce sparse visible
landmarks, tail curve, visibility states, temporal events, reviewer disagreement, and
uncertainty.

No hidden 3D, internal anatomy, behaviour, or health label is required.

### Stage R1 — observable challenge set

Expand the real set through licence-clean sources or remote contributors. Use active
review so humans resolve semantic identity and ambiguity rather than annotate every
frame manually.

### Stage M0 — monocular baseline

Evaluate one commercially usable baseline on:

- exact Tier S pose and derivatives;
- Tier R2 visible landmarks and curves;
- temporal stability and occlusion recovery;
- confidence calibration and abstention;
- synthetic-to-real degradation.

### Stage G0 — external validation integration

Only after the software benchmark is useful, integrate one independently operated hidden
gold sequence. The partner performs all physical work.

## Real-environment stratification

Use a predeclared fractional design covering primary effects and selected high-risk
interactions.

### Fur and morphology

- short, light or high-contrast coat;
- short, dark solid coat;
- patterned coat;
- long-haired coat;
- hairless or minimally obscured upper-bound case;
- substantially different facial/body morphologies.

Record observable morphology directly rather than treating breed as a precise proxy.

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
- ordinary consumer frame rates, exposure, and compression.

### Environment and occlusion

- uncluttered indoor;
- cluttered indoor;
- soft furnishings and similar-coloured backgrounds;
- partial and full temporary occlusion;
- frame exit and re-entry;
- more than one cat or another moving subject.

Each sequence records which strata are present. Uncovered strata remain explicit gaps.

## Tasks

### T1 — 2D surface landmark estimation

Evaluate visible landmarks and prediction uncertainty in image coordinates.

### T2 — temporal tracking

Evaluate identity stability, jitter, drift, occlusion survival, re-detection, and
trajectory continuity.

### T3 — face, eye, and ear dynamics

Evaluate orientation cues, aperture or blink events, ear motion, and temporal derivative
quality where image scale permits.

### T4 — tail curve tracking

Evaluate centreline distance, curve topology, curvature, tip motion, and recovery after
self-occlusion.

### T5 — synthetic exact 3D reconstruction

Evaluate metric landmarks, curves, contact, and derivatives against Tier S state.
Results must be clearly labelled synthetic.

### T6 — observable contact and gait events

Evaluate paw assignment, visible contact interval, take-off, landing, and support-surface
association. Instrumented real contact is a later Tier G extension.

### T7 — scene-relative reasoning

Evaluate trajectory and relations such as on, under, inside, behind, approaching, and
retreating where sufficient evidence exists.

### T8 — calibrated confidence

Evaluate whether confidence predicts realised error and whether the system abstains
appropriately under ambiguity.

### T9 — synthetic-to-real transfer

Measure the performance gap between controlled Tier S conditions and matching Tier R2
strata. Report where randomisation improves or damages real performance.

### T10 — deployment efficiency

Report accuracy with sustained latency, frame rate, memory, model size, estimated or
measured power, and declared hardware conditions.

### T11 — external hidden-gold evaluation

When Tier G exists, report metric real-world 3D and contact performance separately from
all public-development tiers.

## Metrics

### Spatial accuracy

- 2D point error normalised by declared body or head scale;
- PCK or OKS-compatible exports;
- synthetic 3D point error;
- external-gold 3D point error when available;
- tail-curve distance, topology, and curvature error;
- scene and support-surface error where applicable.

### Temporal accuracy

- positional jitter during true low-motion intervals;
- velocity and acceleration error on Tier S or Tier G;
- event onset and duration error;
- track survival through occlusion;
- accumulated drift;
- re-detection delay;
- identity switches;
- foot sliding during declared contact.

### Calibration

- confidence-region coverage;
- expected calibration error;
- negative log likelihood or another proper scoring rule;
- risk–coverage curve;
- error by visibility, evidence tier, and image scale.

### Transfer

- exact-to-real observable performance delta;
- calibration degradation across domains;
- ranking stability across synthetic and real strata;
- benefit from self-supervised or unsupervised real-video adaptation.

### Stratified reporting

All primary results are reported by relevant fur, motion, lighting, viewpoint, occlusion,
and environment strata. One aggregate score is insufficient.

## Annotation and review

Manual work targets semantic identification, ambiguity resolution, and quality control,
not frame-by-frame recreation of model-generated measurements.

The protocol defines:

- visible-versus-inferred instructions;
- tail curve and occlusion conventions;
- uncertainty and ambiguity entry;
- sparse keyframe review plus temporal propagation;
- reviewer agreement and adjudication;
- post-hoc correction logs;
- prohibition on evaluating a model solely against its own pseudo-label family.

Review may be performed remotely by paid annotators, volunteers, feline experts, or
research partners. The project lead need not record or physically stage footage.

## Sourcing, consent, and redistribution

Allowed sources for released real media:

1. solicited remote owner contributions under sequence-level terms;
2. institutional, shelter, or research collaboration with documented authority;
3. individually verified permissive media whose exact terms allow redistribution and
   downstream research/commercial use;
4. purpose-created media supplied by a contractor or partner under assignment terms.

No assumed permission, licence ambiguity, research-only dependency, or non-commercial
restriction may enter a production dependency or commercially usable release.

Each sequence requires machine-readable records for:

- media owner and contributor;
- people and private information present;
- consent and withdrawal process;
- redistribution rights;
- research and commercial-use permissions;
- licence version;
- capture device and protocol version;
- evidence tier and annotation lineage.

## External validation contract

A Tier G partner must receive a capture-neutral specification rather than instructions
that assume a particular portal. The contract defines:

- required variables and tolerances;
- allowed measurement classes;
- calibration and synchronisation evidence;
- blinded holdout partition;
- raw-data custody and privacy;
- machine-readable import schema;
- evaluation-server behaviour;
- publication and attribution terms.

See [EXTERNAL-VALIDATION-CONTRACT.md](EXTERNAL-VALIDATION-CONTRACT.md).

## v0.1 release contents

Protocol v0.1 is complete when the repository contains:

- frozen pilot landmark and tail-curve ontology;
- observation and provenance schema with S/R2/R3/G tiers;
- deterministic Unity sequence and exact annotation exporter;
- synthetic challenge configuration and validation tests;
- one licence-clean real observable sequence;
- minimal Unity inspection viewer;
- baseline evaluation scripts;
- temporal, uncertainty, and transfer metrics;
- documented limitations and forbidden claims;
- consent and contributor templates;
- external hidden-gold interface specification.

A portal validation report, owner-built rig, instrumented floor, or personal feline
capture is not required for v0.1.

## Open decisions blocking public release

- final pilot landmark and tail-curve topology;
- source and licence of the first rigged feline asset and animations;
- Unity render pipeline and deterministic annotation-export format;
- minimum synthetic variation set;
- first real-video source and contributor terms;
- reviewer protocol and minimum agreement requirements;
- first monocular baseline and production licence suitability;
- outbound code, data, annotation, and asset licences;
- exact forbidden-claims language;
- external evaluation API and custody model.
