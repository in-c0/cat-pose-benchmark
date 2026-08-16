# Stage 0 hardware feasibility decision — external validation only

**Decision date:** 2026-08-04  
**Current status:** retained as evidence for rejecting a lead-developer-owned rig.

## Programme decision

The CatPose programme will not require the lead developer to purchase, construct,
calibrate, or operate a reference rig. Physical activity is limited to ordinary user
testing of an eventual application or externally manufactured product.

This feasibility study remains useful for two reasons:

1. it documents why an owner-purchased mirror portal is not a rational use of the
   available AUD 300 budget;
2. it provides candidate optical classes for a laboratory that may later choose a
   mirror-based Tier G validation route.

It is not a shopping list or implementation prerequisite.

## Inventory that motivated the decision

- no owned global-shutter camera, matched lens, first-surface mirror, or dimensional
  measurement tool;
- one tripod;
- HP OfficeJet Pro 9010-series printer;
- small-bedroom workspace;
- maximum Stage 0 cash budget of AUD 300;
- potential access to UNSW or another laboratory;
- Windows i9-9900K/RTX 2080 and M1 Mac Studio computers;
- current Unity editor.

## Rejected purchase path

A representative Australian purchase path exceeded the entire budget before cables,
mounts, lighting, target construction, or cat-sized mirrors:

| Item used to establish a lower bound | Example price at review |
|---|---:|
| Teledyne FLIR BFS-U3-23S3C-C camera body | AUD 673.60 |
| 4 mm C-mount machine-vision lens | AUD 377.00 |
| Two 254 × 254 mm first-surface mirrors | AUD 572.80 |
| **Minimum example total** | **AUD 1,623.40** |

The example total was about 5.41 times the full budget, and the mirrors were still far
smaller than the original nominal portal planes. The owner-purchased reference route is
therefore rejected.

The underlying machine-readable assumptions and calculations remain in
`stage0/hardware_candidates.json` and `stage0/hardware-feasibility-report.json`.

## Optional partner camera classes

These are capability examples for an external validation partner, not purchase
recommendations.

### Candidate A — 1/2.3-inch sensor plus 4 mm lens

Examples:

- Basler a2A1920-160ucBAS;
- Teledyne FLIR BFS-U3-23S3C-C.

Nominal characteristics used in the feasibility model:

- 1920 × 1200;
- 3.45 µm pixels;
- global shutter;
- C-mount;
- approximately 160 FPS maximum;
- approximately 79.25° horizontal field of view with a 4 mm lens;
- approximately 1.66 m horizontal span at 1.0 m.

### Candidate B — 1/1.2-inch sensor plus approximately 6.5 mm lens

Example:

- Basler acA1920-155uc.

Nominal characteristics used in the model:

- 1920 × 1200;
- 5.86 µm pixels;
- global shutter;
- C-mount;
- approximately 164 FPS maximum;
- approximately 81.75° horizontal field of view with a 6.5 mm lens;
- approximately 1.73 m horizontal span at 1.0 m.

At 1920 × 1200 Bayer8, raw capture requires approximately:

- 138.24 MB/s at 60 FPS;
- 368.64 MB/s at 160 FPS.

These numbers establish partner infrastructure requirements only.

## Replaced pathway

The previous Stage 0M/0R/0F owner workflow is superseded by:

```text
Tier S Unity exact benchmark
→ Tier R2 real observable benchmark
→ Tier R3 uncertainty-aware reconstruction
→ optional Tier G partner-operated hidden gold
```

The partner may choose synchronized cameras, Vicon, calibrated RGB-D, a mirror portal,
pressure systems, or another traceable method. The project lead supplies software,
schemas, QA, and evaluation integration only.

## Budget decision

Do not allocate the AUD 300 budget to research camera bodies, machine-vision lenses,
mirrors, calibration targets, mounts, lighting, or measurement tools.

The budget may instead support software-first needs such as:

- licence-clean or commissioned feline assets;
- annotation or expert review;
- cloud compute;
- app distribution and testing;
- contractor time for a narrow dataset or hardware task;
- eventual finished-product user testing.

## Retained tools

The following files remain as optional partner or engineering utilities:

- `stage0/hardware_feasibility.py`;
- `stage0/hardware_candidates.json`;
- `stage0/hardware-feasibility-report.json`;
- `stage0/capture_host_probe.py`;
- portal geometry and Unity inspection files.

They are not on the software-first critical path.
