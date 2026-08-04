# Stage 0 — rigid-target portal validation

Stage 0 answers one question before any feline recording:

> Can one physical camera plus planar mirrors provide stable enough simultaneous
> geometry to support a small gold-standard benchmark subset?

This directory contains a deliberately bounded **finite-aperture geometry simulation**.
It uses exact planar-reflection projection matrices, including reflected-image parity,
and rejects samples whose reflected rays miss the finite mirror rectangle or physical
sensor.

It still does not model lens distortion, mirror flatness, mounting flex, animal
occlusion, correspondence mistakes, rolling shutter, or image-processing bias. Those
remain physical measurements in
[`docs/STAGE-0-PORTAL-GEOMETRY.md`](../docs/STAGE-0-PORTAL-GEOMETRY.md).

## Run

```bash
python -m pip install numpy
python stage0/geometry_sim.py \
  --config stage0/layouts.json \
  --output stage0/geometry-conditioning-report.json
```

## Test

```bash
python -m unittest stage0.test_geometry_sim
```

The generated report compares:

- direct view plus each single reflection;
- direct view plus both reflections;
- finite-mirror and sensor coverage;
- reflected image-region bounds;
- nominal virtual-camera baselines;
- propagated 3D covariance from configurable image-point noise;
- median and 95th-percentile uncertainty across the commonly visible sample volume.

The current candidates are:

- **A — symmetric lateral:** 92.0% three-view common coverage, 0.813 mm nominal p95
  radial standard deviation, and 1.530 p95 anisotropy;
- **B — lateral pitched:** 95.2% common coverage, 0.826 mm nominal p95 radial standard
  deviation, and 1.511 p95 anisotropy.

These values are conditional on 0.35-pixel independent observation noise and ideal
planes. Layout A is marginally better on nominal p95 radial uncertainty; Layout B is
marginally better on coverage and isotropy. Neither is selected until physical
calibration measures mirror quality, rigidity, distortion, usable image detail, and
repeatability.

The generated JSON is a reproducible design artefact, not measured evidence. Regenerate
it whenever geometry or assumptions change; CI verifies byte-for-byte agreement.
