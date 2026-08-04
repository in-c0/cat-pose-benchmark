# Stage 0 hardware feasibility decision

**Decision date:** 2026-08-04

## Inventory received

- no owned global-shutter camera, lens, first-surface mirror, ordinary mirror, or
  dimensional measurement tool was identified;
- one tripod is available;
- an HP OfficeJet Pro 9010-series printer is available;
- the available workspace is a small bedroom;
- the maximum Stage 0 cash budget is AUD 300;
- borrowing from UNSW or another laboratory is possible;
- capture computers are a Windows i9-9900K/RTX 2080 system and an M1 Mac Studio with
  32 GB RAM;
- a current Unity editor is installed.

The machine-readable inventory and calculations are in
`stage0/hardware_candidates.json` and `stage0/hardware-feasibility-report.json`.

# Decision

## Reject purchasing the reference rig

A representative Australian purchase path already exceeds the entire budget before
cables, mounts, lighting, target construction, or cat-sized mirrors:

| Item used to establish a lower bound | Current example price |
|---|---:|
| Teledyne FLIR BFS-U3-23S3C-C camera body | AUD 673.60 |
| 4 mm C-mount machine-vision lens | AUD 377.00 |
| Two 254 x 254 mm first-surface mirrors | AUD 572.80 |
| **Minimum example total** | **AUD 1,623.40** |

The cited 254 mm mirrors are also far smaller than the nominal 1.0 x 0.9 m mirror planes
in `stage0/layouts.json`. The example total is therefore a lower bound, not a complete
portal quotation.

Sources checked on 2026-08-04:

- Teledyne FLIR camera: https://www.edmundoptics.com.au/p/bfs-u3-23s3c-c-usb3-blackflyreg-s-color-camera/41347/
- 4 mm C-mount lens: https://www.edmundoptics.com.au/p/4mm-uc-series-fixed-focal-length-lens/2966/
- 254 x 254 mm first-surface mirror: https://www.edmundoptics.com.au/p/254-x-254mm-4-6lambda-mirror/6997/

The purchase example is about 5.41 times the complete Stage 0 budget. A purchased
reference portal is rejected.

# Borrowable optical candidates

These are equipment-request classes, not purchase recommendations.

## Candidate A — 1/2.3-inch sensor plus 4 mm lens

Example cameras:

- Basler a2A1920-160ucBAS;
- Teledyne FLIR BFS-U3-23S3C-C.

Both use the Sony IMX392 class: 1920 x 1200, 3.45 µm pixels, global shutter, C-mount,
and approximately 160 fps over USB 3.

Official specifications:

- https://docs.baslerweb.com/a2a1920-160ucbas
- https://softwareservices.flir.com/BFS-U3-23S3/latest/Model/spec.html

With a nominal 4 mm lens:

- horizontal field of view: 79.25 degrees;
- vertical field of view: 54.72 degrees;
- span at 0.9 m: 1.49 x 0.93 m;
- span at 1.0 m: 1.66 x 1.04 m;
- span at 1.2 m: 1.99 x 1.24 m.

Strengths:

- compact and common machine-vision sensor class;
- high frame rate;
- less expensive lens class than a large sensor;
- sufficient nominal field of view for the simulated portal.

Risks:

- 4 mm is a wide lens, so distortion must be calibrated rather than ignored;
- each direct/reflected region receives only part of the 1920 x 1200 sensor;
- small pixels require strong, flicker-controlled lighting for short exposure.

## Candidate B — 1/1.2-inch sensor plus approximately 6.5 mm lens

Example camera:

- Basler acA1920-155uc.

The camera provides 1920 x 1200 default resolution, 5.86 µm pixels, global shutter,
C-mount, 164 fps, and USB 3.

Official specification:

- https://docs.baslerweb.com/aca1920-155uc

With a nominal 6.5 mm lens:

- horizontal field of view: 81.75 degrees;
- vertical field of view: 56.82 degrees;
- span at 0.9 m: 1.56 x 0.97 m;
- span at 1.0 m: 1.73 x 1.08 m;
- span at 1.2 m: 2.08 x 1.30 m.

Strengths:

- larger pixels and sensor area provide a better starting point for short-exposure
  imaging;
- a longer focal length obtains a comparable field of view;
- high frame rate and mature USB3 machine-vision tooling.

Risks:

- a suitable lens must cover the 1/1.2-inch image circle;
- the camera and lens class is generally more expensive;
- borrowing camera and lens as a matched pair is important.

## Data-rate requirement

At 1920 x 1200 Bayer8:

- 60 fps: 138.24 MB/s and 8.2944 GB/minute;
- 160 fps: 368.64 MB/s and 22.1184 GB/minute;
- 100 frames: 230.4 MB.

Use the Windows workstation as the first capture host because both candidate classes are
USB3 machine-vision cameras and the machine is the most direct deployment environment.
The exact USB controller, SSD destination, free space, and sustained write rate remain
to be measured.

# Revised Stage 0 pathway

The original one-camera mirror hypothesis remains worth testing, but the physical plan
must be split.

## Stage 0M — compact engineering mock-up

Purpose:

- prove direct/reflected image layout;
- validate parity conventions;
- exercise target detection and Unity integration;
- discover support occlusion and gross field-of-view failures.

Allowed equipment:

- existing phone or consumer camera;
- borrowed or inexpensive ordinary mirrors;
- printed target;
- tripod and temporary mounts.

Evidence status:

- `engineering_preview_only`;
- no metric 3D claim;
- rear-surface mirror ghosting and rolling shutter are expected limitations.

The mock-up should use a reduced capture volume and rigid target. It is not a scaled
claim about full-cat accuracy.

## Stage 0R — compact reference optical validation

Purpose:

- establish the optical/calibration noise floor with independent holdout points;
- compare ordinary and first-surface mirror behaviour;
- validate empirical uncertainty and teardown/reassembly stability.

Required borrowed equipment:

- one candidate global-shutter camera and matched lens;
- two first-surface mirrors large enough for the compact target volume;
- calipers and an angle/plane measurement method;
- stable mounts and flicker-controlled lighting.

The target may be smaller than the final cat portal, but all dimensional truth must be
independently measured.

## Stage 0F — full feline-volume validation

Only proceed when a laboratory can provide:

- a safe capture space;
- sufficiently large first-surface mirrors and rigid mounts; or
- an independent synchronized multi-camera/Vicon reference system.

If large stable first-surface optics cannot be borrowed, the mirror portal stops at a
validated compact calibration instrument. The gold feline subset then uses synchronized
multi-camera or motion-capture equipment. The consumer model remains monocular.

# Workspace gate

The current nominal geometry places the physical camera 1.2 m behind the portal origin
and extends the capture volume to 0.65 m in front, producing a camera-to-far-volume span
of 1.85 m before safety and operator clearance.

Before building the nominal rig, measure a clear indoor rectangle. The initial gate is:

```text
minimum clear length: 2.10 m
minimum clear width:  1.00 m
minimum clear height: 1.20 m
```

Failure to meet this gate does not block Stage 0M; it blocks the current full-size layout
inside the bedroom.

# Printing and dimensional measurement

Each current ChArUco face is 175 x 245 mm and fits on A4 paper. The OfficeJet may be used
only when:

- all print-driver scaling and fit-to-page options are disabled;
- the output is printed at 100 percent;
- dimensions are measured at several locations;
- a panel is rejected when either check dimension differs by more than 0.20 mm.

A ruler is insufficient for the registered 0.20 mm threshold. Borrow or purchase a
reasonable digital caliper before the target can be treated as a reference object.
UNSW Making also lists a large photographic printer and fabrication facilities, but
printed dimensions still require independent verification.

# Budget allocation

Do not spend the AUD 300 on the camera, lens, or reference mirrors.

Reserve it approximately as follows after borrowing is confirmed:

- up to AUD 50: dimensional measurement tools if they cannot be borrowed;
- up to AUD 80: rigid target panels and printing;
- up to AUD 80: clamps, brackets, edge protection, and temporary frame materials;
- up to AUD 40: diffuse/flicker-controlled lighting consumables;
- at least AUD 50: contingency.

No category is authorised until the matching borrowed optical equipment and workspace
are confirmed.

# UNSW pathways to try

The most relevant public UNSW facilities are:

- Human Movement Laboratories: Vicon and markerless motion capture;
- Optics and Radiometry Laboratory: optical testing and calibration expertise;
- SAGE Laboratory: close-range photogrammetry and spatial measurement;
- UNSW Making/MCIC: fabrication, 3D printing, laser cutting, workbenches, and printing;
- Making Centre Resource Centre: camera and lighting loans for the non-metric mock-up.

Public facility pages do not establish that a specific Basler/FLIR camera or large
first-surface mirror is available. An equipment request must ask for capabilities and
exact inventory rather than assuming availability.

# Current next actions

1. Obtain clear bedroom dimensions.
2. Confirm Windows USB3 controller and capture-drive free space/write rate.
3. Ask UNSW/labs for either candidate camera class, matched lens, first-surface mirrors,
   dimensional tools, and safe bench space.
4. Build Stage 0M only after identifying ordinary mirror dimensions.
5. Generate a configuration-specific geometry and BOM after the actual borrowed parts
   are known.
