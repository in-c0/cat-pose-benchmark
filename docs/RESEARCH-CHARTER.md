# Research charter

**Status:** direction v0.1, approved for specification work  
**Date:** 2026-08-04

## Programme objective

Create an open, reproducible visual-intelligence benchmark for domestic cats that
measures pose, face, ears, tail, contact, and scene-relative motion over time, while
representing uncertainty honestly.

The benchmark is intended to support three connected outcomes:

1. a credible open research contribution;
2. a monocular consumer application with playful, non-medical outputs;
3. an edge-deployed camera product and real-time Unity visualisation demonstrating the
   full data-to-device workflow.

## Central research question

> Can an ordinary monocular RGB system recover temporally stable feline surface pose and
> motion with calibrated uncertainty, when evaluated against a compact set of
> independently measured geometric and contact observations?

The product system is monocular. Specialised capture is used only to establish reliable
reference measurements.

## Methodological thesis

Ground truth is not one complete skeleton attached to every frame.

A real cat is only partially observable. Different sources measure different variables,
and their reliability changes with viewpoint, motion, fur, lighting, and occlusion.
Therefore, the benchmark will store a graph of observations with provenance and
uncertainty rather than flattening all labels into equally certain points.

## Hypotheses

### H1 — simultaneous virtual views can establish a useful geometric gold subset

A calibrated mirror-based capture portal using one physical camera can recover visible
surface landmarks and curves with sufficient precision to evaluate monocular methods,
without multi-device synchronisation.

### H2 — surface and contact truth are more defensible than hidden joint truth

Directly visible landmarks, silhouettes, tail curves, and paw contacts can be measured
more reliably than anatomical joint centres hidden beneath fur. Models evaluated on
latent joints must therefore be scored against distributions or uncertainty regions,
not fictional exact coordinates.

### H3 — temporal metrics expose failures hidden by frame accuracy

Models with similar per-frame landmark scores will differ materially in jitter, drift,
occlusion recovery, derivative accuracy, gait timing, and confidence calibration.
These temporal properties are necessary for downstream behavioural measurement.

### H4 — world and contact constraints improve monocular reconstruction

Static-scene geometry, support surfaces, contact events, non-penetration, and
identity-specific proportions will reduce monocular ambiguity without turning
model-derived labels into independent ground truth.

### H5 — uncertainty calibration is a first-class benchmark task

A useful system must become less confident when landmarks are small, blurred, hidden,
or geometrically ambiguous. Confidence quality should be evaluated independently from
mean pose accuracy.

## Observation ontology

### Direct visual surface observations

Examples: eye corners, nose, muzzle boundary, ear tips and bases, visible paw centres,
body contour, tail centreline, and visible contact patch.

### Independent contact observations

Examples: paw-contact location and time, stance interval, take-off, landing, and support
surface. These may be measured by an instrumented or transparent floor.

### Scene observations

Examples: camera trajectory, floor plane, furniture surfaces, obstacle geometry,
world-space cat trajectory, and object-relative relations.

### Latent anatomical estimates

Examples: shoulder, hip, knee, or vertebral centres hidden beneath fur. These must retain
an inference source and uncertainty distribution. They are not direct truth unless
validated by an independent anatomical measurement.

### Temporal derived observations

Examples: velocity, acceleration, angular velocity, blink duration, ear flick timing,
tail curvature change, gait phase, freeze duration, and occlusion recovery time.
Derivatives inherit and amplify source uncertainty.

## Primary contributions

The intended first paper should contribute:

1. an open capture protocol for simultaneous feline views using a compact catadioptric
   portal;
2. an observation and provenance schema that distinguishes measured surface/contact
   truth from inferred anatomy;
3. a real-environment temporal benchmark emphasizing ears, face, tail, contact,
   occlusion, and uncertainty;
4. metrics for jitter, drift, derivative accuracy, contact, and calibration;
5. an open Unity inspection tool for synchronized media, geometry, uncertainty, and
   model comparison.

## Non-goals for v0

- Literal translation of feline vocalisation or intent
- Pain, illness, welfare, or diagnostic claims
- A universal feline ethogram classifier
- Full-room metric 4D reconstruction as a prerequisite
- A custom consumer enclosure before the benchmark pipeline works
- Claiming model-generated pseudo-labels as independent ground truth
- Recovering exact internal skeletal anatomy from ordinary RGB alone

## Benchmark acceptance gates

The exact thresholds remain open until a pilot establishes realistic noise floors, but
v0 must define and freeze them before the main collection.

At minimum, the benchmark must demonstrate:

1. **Repeatability:** repeated calibration produces bounded geometric disagreement.
2. **Independent evidence:** gold evaluation labels do not originate solely from the
   model family being evaluated.
3. **Temporal validity:** reference timing is sufficient to score velocity and event
   onset, not just static position.
4. **Uncertainty validity:** lower declared certainty predicts higher realised error.
5. **Stratified reporting:** results are reported by fur, motion, lighting, viewpoint,
   occlusion, and environment strata.
6. **Licence cleanliness:** every released sequence has machine-readable consent,
   ownership, redistribution, and permitted-use records.
7. **Reproducibility:** a second operator can build or calibrate the capture setup from
   the released specification.

## Stop conditions

Pause collection and revise the design if any of the following occurs:

- mirror geometry cannot produce sufficiently separated simultaneous viewpoints;
- the capture portal materially changes natural feline movement for the target tasks;
- contact instrumentation alters gait or cannot be temporally aligned;
- uncertainty cannot be estimated independently from the evaluated model;
- consent or licensing terms do not permit the intended public benchmark release;
- the keypoint/curve ontology proves ambiguous between annotators before collection;
- the proposed gold measurements are no more reliable than ordinary manual labels.

## Initial execution sequence

1. Freeze the observable-versus-latent ontology.
2. Implement the observation/provenance schema.
3. Design the smallest mirror-based calibration experiment using a rigid object.
4. Validate camera and virtual-view geometry before involving an animal.
5. Record one voluntary cat passage or play sequence.
6. Produce surface landmarks, tail curve, visibility, covariance, and provenance.
7. Build a minimal Unity inspection scene.
8. Compare one monocular baseline against the measured subset.
9. Publish Protocol v0.1 with known limitations.

## Product relationship

The consumer translator, puck, and future analyser are downstream demonstrations of the
same visual-intelligence stack. They must not weaken the benchmark’s scientific claims.
Entertainment outputs should be explicitly playful; health-related outputs require a
separate evidence, ethics, and regulatory programme.
