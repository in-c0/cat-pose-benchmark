# Stage 0 hardware handoff

**Status:** software preparation may continue, but measured Stage 0 evidence cannot begin
until the reference capture hardware is available and its exact metadata is recorded.

No animal recording is permitted during this handoff.

## Why a handoff is now required

The repository can simulate candidate mirror geometry, generate a rigid target, validate
capture manifests, and visualise nominal geometry without hardware. It cannot determine:

- real mirror flatness, ghosting, flex, and mounting repeatability;
- usable reflected sensor area through a selected lens;
- real point-detection precision;
- calibration drift after handling;
- rolling/global shutter motion error;
- physical holdout-point reconstruction error.

Those quantities are the independent evidence needed to decide whether the portal is a
valid ground-truth instrument.

## User action required before physical capture

Create one inventory response containing either exact model identifiers or `none` for:

1. available global-shutter cameras;
2. available lenses and mounts;
3. available first-surface mirrors and dimensions;
4. rigid panel or extrusion materials;
5. access to a dimensionally reliable printer or print service;
6. access to calipers, angle measurement, or a stronger dimensional measurement method;
7. a safe indoor construction/capture area of roughly 0.8 m x 1.3 m x 1.1 m;
8. maximum Stage 0 hardware budget in AUD;
9. whether borrowing university/lab equipment is realistic.

Do not purchase anything from the current nominal dimensions alone. The lens and mirror
sizes must be selected together after a field-of-view calculation and a low-cost mock-up.

## Reference-rig minimum

The preferred physical validation rig needs:

- one colour global-shutter machine-vision camera;
- fixed manual-focus lens with documented mount and focal length;
- uncompressed or minimally processed frame access;
- two first-surface planar mirrors;
- stiff mirror mounts whose pose can be measured and repeated;
- trihedral target generated from `stage0/target_spec.json`;
- independent dimensional measurements of the assembled target;
- diffuse flicker-controlled lighting;
- protective treatment for mirror edges;
- a computer capable of sustained lossless capture at the chosen resolution/frame rate.

The camera specification target remains at least 1920 x 1200 at 60 FPS with manual
exposure, gain, focus, and white balance. This is a reference instrument requirement,
not the eventual consumer-product camera requirement.

## Cheap optical mock-up before purchasing reference mirrors

A non-gold mock-up may use an existing camera and inexpensive mirrors solely to answer:

- can direct and two reflected regions fit on the sensor simultaneously;
- which layout gives useful views of the intended volume;
- where mirror supports obstruct rays;
- whether the physical frame dimensions are workable;
- how much reflected image resolution each view receives.

Mock-up footage is labelled `engineering_preview_only`. It cannot be reported as metric
ground truth because rear-surface mirrors, unknown lens calibration, and rolling shutter
can create systematic error.

## Acquisition gate

Only select or purchase reference components after the inventory is known and the repo
contains a computed field-of-view/BOM comparison for at least two feasible camera-lens
combinations.

## First physical session

Once the rig exists:

1. verify printed panel dimensions at multiple locations;
2. assemble and independently measure the target;
3. record camera, lens, mirror, mount, lighting, and environmental metadata;
4. capture intrinsic-calibration sequences before installing mirrors;
5. install Layout A and capture mirror-plane calibration sequences;
6. repeat after ordinary teardown/reassembly;
7. capture the pre-registered static volume sweep;
8. repeat for Layout B;
9. run the same reconstruction and uncertainty report for both layouts;
10. select, revise, or stop according to the frozen decision bands.

Every capture must have a manifest conforming to
`schemas/stage0-capture-manifest.schema.json` and raw-file hashes must be verified before
analysis.

## Explicit stop conditions

Stop physical work and document the failure when:

- a mirror or mount cannot be made safe and mechanically stable;
- a field-of-view mock-up cannot fit the required direct/reflected regions;
- target print dimensions cannot be verified;
- calibration metadata or raw timestamps cannot be exported;
- a proposed shortcut would make the reference labels depend on the model being tested;
- animal footage is proposed before the rigid-target gate is complete.
