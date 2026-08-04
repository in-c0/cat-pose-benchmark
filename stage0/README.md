# Stage 0 — rigid-target portal validation

Stage 0 answers one question before any feline recording:

> Can one physical camera plus planar mirrors provide stable enough simultaneous
> geometry to support a small gold-standard benchmark subset?

This directory contains an intentionally limited **geometry-conditioning simulation**.
It compares physical and virtual camera centres under assumed pixel noise. It does not
model mirror boundaries, reflected-image parity, lens distortion, occlusion, material
quality, or the fraction of sensor pixels occupied by each reflected view. Those are
measured in the physical experiment specified in
[`docs/STAGE-0-PORTAL-GEOMETRY.md`](../docs/STAGE-0-PORTAL-GEOMETRY.md).

## Run

```bash
python -m pip install numpy
python stage0/geometry_sim.py \
  --config stage0/layouts.json \
  --output stage0/geometry-conditioning-report.json
```

The generated report compares:

- direct view plus each single reflection;
- direct view plus both reflections;
- nominal virtual-camera baselines;
- propagated 3D covariance from configurable image-point noise;
- median and 95th-percentile uncertainty across a sampled capture volume.

The generated JSON report is an experiment artefact and should be regenerated whenever
the candidate geometry changes. Do not treat its values as physical calibration results.
