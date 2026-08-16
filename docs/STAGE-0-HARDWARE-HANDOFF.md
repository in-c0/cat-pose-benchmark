# Stage 0 hardware handoff — archived from critical path

**Status:** optional external-validation reference only.

The CatPose programme no longer requires the lead developer to purchase, construct,
calibrate, or operate this apparatus. Physical involvement is limited to ordinary use
of a finished application or externally manufactured product.

This document is retained because a laboratory or independent partner may later choose
to validate a mirror-based reference system. It must not be interpreted as a user task
list or prerequisite for Protocol v0.1.

## Current programme decision

The critical path is:

```text
Unity synthetic exact data
→ real-video observable benchmark
→ monocular baseline and uncertainty
→ playful application
→ software-defined edge/RTL workflow
→ optional external hidden-gold validation
```

A partner-operated portal is one possible Tier G measurement class. Synchronized
multi-camera, Vicon, calibrated RGB-D, pressure systems, or another traceable method are
equally acceptable under `EXTERNAL-VALIDATION-CONTRACT.md`.

## Why this design study remains useful

The repository can simulate candidate mirror geometry, generate a rigid target, validate
capture manifests, and visualise nominal geometry. Those artefacts may help a partner
assess:

- mirror flatness, ghosting, flex, and mounting repeatability;
- reflected sensor area through a selected lens;
- point-detection precision;
- calibration drift;
- shutter-related motion error;
- physical holdout-point reconstruction error.

Simulation and nominal geometry are design aids, not measured evidence.

## Partner-operated reference-rig requirements

A partner choosing this route would normally need:

- one colour global-shutter machine-vision camera;
- fixed manual-focus lens with documented mount and focal length;
- uncompressed or minimally processed frame access;
- two first-surface planar mirrors;
- stiff, safe mirror mounts;
- independently measured non-coplanar target;
- diffuse flicker-controlled lighting;
- raw capture and timestamp export;
- ethics, animal-welfare, facility, and operator approvals.

The project lead supplies schemas, calibration software, QA, coordinate tests, and
evaluation integration. The partner owns all physical operation and safety.

## Evidence boundary

Ordinary mirrors and rolling-shutter consumer cameras may support an engineering preview,
but cannot establish metric reference truth without an independently justified error
model.

Nominal target coordinates are construction coordinates only until the assembled target
is independently measured.

## Partner validation sequence

If an external partner selects this method:

1. select camera, lens, mirror dimensions, and capture volume from measured field of view;
2. verify target dimensions independently;
3. capture intrinsic and mirror-plane calibration sequences;
4. repeat after teardown and reassembly;
5. capture a pre-registered rigid-target volume sweep;
6. estimate holdout error, repeatability, and covariance;
7. compare against decision bands without tuning on feline model results;
8. provide a Tier G package conforming to the external-validation contract.

## Stop conditions

The partner route stops or revises when:

- safe and mechanically stable mounting is unavailable;
- useful simultaneous view coverage is impractically small;
- target dimensions, raw timestamps, or calibration metadata cannot be verified;
- reference labels depend primarily on the model being tested;
- measurement uncertainty is too large for the intended temporal variables;
- the procedure materially changes natural feline movement;
- rights, consent, ethics, or data-custody requirements are unresolved.

No action is required from the project lead under this document.
