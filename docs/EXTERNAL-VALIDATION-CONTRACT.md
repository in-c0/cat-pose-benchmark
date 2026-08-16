# External validation contract

**Status:** interface draft v0.1  
**Principle:** the CatPose project supplies software and protocol; an independent partner
operates all specialised physical equipment.

## Purpose

Allow a laboratory, research group, data provider, shelter, clinic, or commercial test
service to contribute independent validation without coupling the benchmark to one
specific apparatus.

The contract supports synchronized multi-camera systems, Vicon or optical motion
capture, calibrated RGB-D, pressure walkways, mirror-based systems, or another traceable
measurement method.

## Partner responsibilities

The validation partner is responsible for:

- ethics, animal-welfare, facility, and operator approvals;
- safe operation of all equipment;
- calibration, synchronization, and environmental records;
- participant and media consent;
- data custody and access controls;
- physical target, animal, and scene preparation;
- raw measurements and uncertainty evidence;
- disclosure of exclusions, failures, and post-processing.

The project lead is not expected to attend, construct, operate, or calibrate the setup.

## Project responsibilities

The CatPose project supplies:

- target variable and topology specification;
- evidence-tier and provenance schemas;
- sequence and calibration manifest schemas;
- automated file-integrity and completeness checks;
- coordinate and unit conversion tests;
- import adapters;
- blinded holdout partition rules;
- evaluation code and reports;
- optional encrypted upload or hosted evaluation tooling.

## Measurement-neutral requirements

Every accepted sequence must provide:

1. a declared world coordinate system and metric unit;
2. camera intrinsics/extrinsics for relevant views;
3. synchronization method and measured timing uncertainty;
4. landmark or surface definitions matching the benchmark ontology;
5. per-observation visibility and uncertainty;
6. calibration version and timestamp;
7. raw-to-derived lineage;
8. independent holdout observations not used for fitting;
9. sequence-level rights, consent, and permitted-use records;
10. a list of frames or variables excluded from evaluation and the reason.

## Accepted evidence classes

### G1 — simultaneous calibrated imaging

Examples: synchronized multi-camera RGB or global-shutter catadioptric imaging.

Minimum evidence:

- synchronization uncertainty;
- reprojection residuals;
- calibration-repeatability report;
- view coverage and triangulation conditioning;
- independent holdout points or surfaces.

### G2 — motion capture

Examples: Vicon or another optical tracking system.

Minimum evidence:

- marker topology and attachment method;
- marker-to-surface or marker-to-anatomy interpretation;
- missing-marker handling;
- system calibration and residuals;
- statement of any behavioural or appearance alteration.

Markers are not automatically treated as anatomical joint centres.

### G3 — calibrated depth or surface measurement

Examples: RGB-D arrays, structured light, photogrammetry, or traceable surface scanning.

Minimum evidence:

- metric depth accuracy and operating range;
- failure modes on fur, tails, reflective surfaces, and motion;
- camera/depth alignment;
- temporal alignment;
- independent scale verification.

### G4 — contact measurement

Examples: pressure walkway, force plate, transparent floor, or instrumented support
surface.

Minimum evidence:

- spatial and temporal resolution;
- calibration procedure;
- paw identity or assignment method;
- effect of the surface on natural movement;
- alignment with visual frames.

### G5 — clinical or anatomical reference

Examples: existing ethically justified XROMM, CT-linked motion, or another anatomical
measurement.

Minimum evidence:

- independent ethical justification;
- anatomical model and registration method;
- uncertainty and accuracy evidence;
- strict separation from any consumer or medical claim not supported by the data.

## Required output package

```text
sequence_id/
  sequence-manifest.json
  calibration-manifest.json
  rights-manifest.json
  observations.jsonl
  uncertainty.jsonl
  exclusions.json
  checksums.sha256
  optional-media/
  optional-private-raw-reference/
```

The exact schemas will evolve, but identifiers, units, coordinate frames, timestamps,
visibility, evidence class, and provenance are mandatory.

## Hidden evaluation modes

A partner may choose one of four modes:

1. **Public release:** media and labels are released under approved terms.
2. **Private labels:** public or approved media is evaluated against labels held by the
   project or partner.
3. **Remote evaluator:** predictions are uploaded to a partner-hosted service and only
   aggregate results are returned.
4. **Escrow evaluation:** encrypted data is processed in a controlled environment under
   an agreed publication protocol.

The benchmark must report which mode generated each result.

## Anti-circularity

External gold cannot be created solely from the same model family being evaluated.
Model-assisted processing is permitted only when:

- independent measurements constrain or validate the result;
- the generating model and checkpoint are disclosed;
- holdout observations remain unused during fitting;
- evaluation can isolate independently measured variables.

## Acceptance checks

Before a sequence enters Tier G:

- manifests validate;
- checksums match;
- units and coordinate transforms pass invariant tests;
- synchronization and calibration uncertainty are present;
- holdout partition is intact;
- rights and consent permit the intended evaluation;
- the partner confirms that no prohibited or unsafe procedure was performed for the
  benchmark;
- the project documents which claims the evidence can and cannot support.

## Publication rule

Tier G results must be reported separately from Tier S, R2, and R3. A benchmark may not
combine them into one score that obscures evidence strength.

Until Tier G exists, the project may publish synthetic exact, real observable, temporal,
calibration, and synthetic-to-real results, but must not claim externally verified
real-world metric 3D accuracy, clinical validity, or diagnostic performance.
