# UNSW equipment and facility request

## Purpose

Request short-term access or a referral for the animal-free Stage 0 validation of an
open feline pose benchmark. The experiment uses only a printed rigid calibration target;
no animals, people, clinical samples, or medical claims are involved at this stage.

## Request text

> Hello,
>
> I am a UNSW Master of IT (AI) student developing an open-source benchmark and capture
> methodology for temporally stable feline pose estimation. Before any animal footage is
> considered, I am validating the measurement geometry using an asymmetric rigid
> calibration target.
>
> I am looking for short-term access, a loan, or a referral for some combination of:
>
> - a colour global-shutter USB3 machine-vision camera around 1920 × 1200 at 60 fps or
>   above, such as a Basler ace/ace 2 or Teledyne FLIR Blackfly S;
> - a matched C-mount lens giving roughly 80° horizontal field of view—approximately
>   4 mm for a 1/2.3-inch sensor or 6–7 mm for a 1/1.2-inch sensor;
> - two planar first-surface mirrors and stable adjustable mounts;
> - digital calipers and a method for measuring mirror plane/angle and target geometry;
> - flicker-controlled diffuse lighting and safe bench space;
> - alternatively, access to a synchronized multi-camera or Vicon system for independent
>   3D validation.
>
> The first session would record only a printed rigid ChArUco target. I have a
> pre-registered protocol, capture metadata schema, geometry simulation, holdout-point
> evaluation, and Unity visualization ready. Raw data and results will distinguish
> measured evidence from simulation and pseudo-labels.
>
> The intended initial access is approximately half a day for equipment inspection,
> field-of-view testing, calibration, and a repeated static target sweep. I can adapt the
> setup to equipment already available and follow all facility inductions and safety
> requirements.
>
> Could you advise whether your facility has relevant equipment, or direct me to the
> appropriate UNSW technical contact?
>
> Thank you,
> Ji

## Information to attach

- repository: `in-c0/cat-pose-benchmark`;
- Stage 0 protocol: `docs/STAGE-0-PORTAL-GEOMETRY.md`;
- hardware feasibility decision: `docs/STAGE-0-HARDWARE-FEASIBILITY.md`;
- target and capture contract: draft PR #5;
- explicit statement: no animal recording in Stage 0.

## Contact order

1. **UNSW Human Movement Laboratories** — ask about synchronized Vicon or markerless
   validation and appropriate collaboration pathway.
2. **UNSW Optics and Radiometry Laboratory** — ask about optical calibration expertise,
   first-surface mirrors, plane measurement, or referral.
3. **SAGE Laboratory** — ask about close-range photogrammetry, dimensional survey, and
   target measurement.
4. **UNSW Making / MCIC / Engineering Makerspaces** — ask for target fabrication,
   printing, mounts, workbench space, calipers, and safe mirror supports.
5. **Making Centre Resource Centre** — request consumer camera and lighting only for the
   non-metric Stage 0M mock-up.

## Acceptance rule

Do not interpret a generic camera loan as a reference-rig solution. Record exact camera,
sensor, shutter, lens, mirror dimensions, mounting method, timestamps, and raw-output
capability before accepting the equipment for Stage 0R.
