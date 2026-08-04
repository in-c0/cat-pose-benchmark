# Research charter

**Status:** direction v0.2, approved for software-first implementation  
**Date:** 2026-08-04

## Programme objective

Create an open, reproducible visual-intelligence benchmark for domestic cats that
measures pose, face, ears, tail, contact, and scene-relative motion over time while
representing uncertainty honestly.

The programme is intentionally structured so the lead developer performs no bespoke
physical capture, rig construction, calibration-lab work, or hardware fabrication.
Physical activity is limited to ordinary user testing of an eventual app or manufactured
product.

The benchmark supports three connected outcomes:

1. a credible open research contribution;
2. a monocular consumer application with playful, non-medical outputs;
3. an edge-deployed camera product and real-time Unity visualisation demonstrating the
   full data-to-device workflow.

## Central research question

> Can an ordinary monocular RGB system recover temporally stable feline surface pose and
> motion with calibrated uncertainty, learning from exact simulation and observable real
> video, and later passing an independently operated hidden-gold evaluation?

The product system is monocular. Any specialised physical measurement is performed by an
external partner under a published protocol and is not a prerequisite for the first
public benchmark release.

## Methodological thesis

Ground truth is not one complete skeleton attached to every frame.

A real cat is only partially observable. Different sources measure different variables,
and reliability changes with viewpoint, motion, fur, lighting, and occlusion. The
benchmark stores a graph of observations with provenance and uncertainty rather than
flattening all labels into equally certain points.

The evidence hierarchy is:

- **Tier S:** exact synthetic state generated in Unity;
- **Tier R2:** observable facts verified in real video;
- **Tier R3:** model-derived reconstruction with explicit uncertainty;
- **Tier G:** independent external measurements, optionally hidden.

No tier may be presented as stronger evidence than its acquisition method supports.

## Hypotheses

### H1 — procedural exact data can expose controlled failure modes

A Unity-based feline scene generator can provide exact pose, tail, face, contact, scene,
visibility, and temporal labels across controlled variations that are difficult to
collect systematically in real homes.

### H2 — observable real-video truth is scientifically useful without complete 3D

Visible landmarks, silhouettes, ear boundaries, tail curves, contact evidence, and
tracking events can support credible real-domain evaluation without inventing hidden
joint centres or metric depth.

### H3 — temporal metrics expose failures hidden by frame accuracy

Models with similar per-frame scores will differ materially in jitter, drift, occlusion
recovery, derivative accuracy, gait timing, and confidence calibration. These temporal
properties are necessary for downstream behavioural measurement.

### H4 — uncertainty-aware synthetic-to-real transfer can be evaluated before gold 3D

Tier S provides exact controlled error, while Tier R2 provides real-domain observable
error. Agreement between these evaluations, combined with calibrated abstention, can
support useful progress before Tier G exists.

### H5 — external gold is a late acceptance gate, not an implementation dependency

An independent laboratory can later operate synchronized cameras, Vicon, calibrated
RGB-D, pressure systems, mirrors, or another traceable apparatus using a capture-neutral
contract. The project can publish, train, benchmark, and ship an entertainment product
before that evaluation, but cannot claim externally verified metric 3D accuracy.

### H6 — software-defined edge implementation demonstrates hardware workflow

Quantisation, operator partitioning, HLS or RTL, simulation, cocotb/Verilator
verification, synthesis, timing, area, and power estimation can demonstrate a credible
hardware-aware workflow without personal fabrication. Physical silicon or board tests
may be performed later by a partner or product vendor.

## Observation ontology

### Direct visual surface observations

Examples: eye corners, nose, muzzle boundary, ear tips and bases, visible paw centres,
body contour, tail centreline, and visible contact patch.

### Independent contact observations

Examples: paw-contact location and time, stance interval, take-off, landing, and support
surface. In v0 these may be exact synthetic labels or observable real-video events.
Externally instrumented contact is optional Tier G evidence.

### Scene observations

Examples: camera trajectory, floor plane, furniture surfaces, obstacle geometry,
world-space trajectory, and object-relative relations.

### Latent anatomical estimates

Examples: shoulder, hip, knee, or vertebral centres hidden beneath fur. These retain an
inference source and uncertainty distribution. They are not direct truth unless validated
by independent anatomical measurement.

### Temporal derived observations

Examples: velocity, acceleration, angular velocity, blink duration, ear-flick timing,
tail-curvature change, gait phase, freeze duration, and occlusion recovery time.
Derivatives inherit and amplify source uncertainty.

## Primary contributions

The first research release should contribute:

1. an open Unity generator for exact feline pose, tail, face, contact, visibility, and
   scene labels;
2. an observation and provenance schema distinguishing synthetic exact state, observable
   real evidence, reconstructed estimates, and external gold;
3. a real-video temporal benchmark emphasizing ears, face, tail, occlusion, tracking,
   and uncertainty;
4. metrics for jitter, drift, derivative quality, curve topology, calibration, and
   synthetic-to-real transfer;
5. an open Unity inspection tool for geometry, uncertainty, sequences, and model
   comparison;
6. a capture-neutral external-validation contract and hidden-evaluation adapter.

## Non-goals for v0

- Literal translation of feline vocalisation or intent
- Pain, illness, welfare, or diagnostic claims
- A universal feline ethogram classifier
- Personal construction or operation of a calibration portal
- Full-room metric 4D reconstruction as a prerequisite
- A custom consumer enclosure before the software pipeline works
- Claiming synthetic or model-generated labels as independent real-world truth
- Recovering exact internal skeletal anatomy from ordinary RGB alone

## Benchmark acceptance gates

The public v0 release must demonstrate:

1. **Synthetic exactness:** exported labels reproduce Unity state within declared numeric
   tolerance.
2. **Observable real validity:** real-video labels are restricted to externally
   observable variables with documented reviewer agreement.
3. **Temporal validity:** timing is sufficient to score trajectories and events, not just
   static position.
4. **Uncertainty validity:** lower declared certainty predicts higher realised error on
   Tier S and observable Tier R2 labels.
5. **Anti-circularity:** a model is not evaluated solely against labels generated by the
   same model family.
6. **Stratified reporting:** results are reported by fur, motion, lighting, viewpoint,
   occlusion, and environment strata.
7. **Licence cleanliness:** every released real sequence has machine-readable ownership,
   consent, redistribution, and permitted-use records.
8. **Reproducibility:** another developer can generate the synthetic set and run the
   benchmark from the released software.

Tier G adds a later gate for externally verified metric 3D and contact performance.

## Stop conditions

Pause or revise a track if:

- synthetic randomisation produces visually implausible or physically invalid motion;
- synthetic labels cannot be reproduced deterministically;
- real-video sources lack sufficient rights for the intended release;
- the keypoint or curve ontology proves ambiguous between reviewers;
- pseudo-labels become the only evidence for a claimed result;
- uncertainty does not correlate with realised error;
- external partners require a protocol that materially changes the benchmark target;
- physical work is being shifted back onto the project lead rather than handled by a
  partner or product supplier.

## Initial execution sequence

1. Freeze the observable-versus-latent ontology.
2. Extend the observation/provenance schema with Tier S, R2, R3, and G.
3. Build the smallest deterministic Unity synthetic sequence and exact annotation
   exporter.
4. Add unit tests that render-state and exported labels agree.
5. Define the real-video sourcing, consent, and observable-review protocol.
6. Add one licence-clean real sequence with sparse visible labels and uncertainty.
7. Implement temporal, curve, occlusion, and calibration metrics.
8. Compare one monocular baseline across Tier S and Tier R2.
9. Publish Protocol v0.1 and CatSynth4D demonstration assets.
10. Seek an external Tier G partner after the public software benchmark is useful.

## Product relationship

The translator app, puck, and future analyser are downstream demonstrations of the same
visual-intelligence stack. They must not weaken the benchmark’s scientific claims.
Entertainment outputs remain explicitly playful; health-related outputs require a
separate evidence, ethics, and regulatory programme.

The project lead may install and use-test a finished or externally manufactured product,
but does not need to fabricate, solder, machine, mount, calibrate, or operate bespoke
research hardware.
