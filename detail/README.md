# Feline detail experiment

Issue: #11

Phase-0 model bake-off showed that a new generic feline pose backbone is not justified.
Existing animal models already recover gross body pose, paws, face points and generic
monocular 3D. The shared residual is **feline detail**:

- explicit ear geometry/orientation;
- continuous tail geometry rather than root/tip endpoints.

This workstream tests the smallest module that can close those gaps while keeping the
generic animal backbone replaceable.

## Observation-first representation

### Ear

Each visible ear is represented by three surface landmarks:

1. `base_medial`;
2. `base_lateral`;
3. `tip`.

Those three points define an observed image-space triangle. Derived quantities such as
base centre, ear axis and in-plane angle are computed from the points; they are not stored
as independent ground truth.

A later 3D extension may estimate an ear plane, but 2D video does not directly observe a
unique 3D plane under occlusion. Keep 3D orientation model-derived unless independently
measured.

### Tail

The tail is represented as an **ordered centreline from base to tip**:

```text
base → p1 → p2 → ... → tip
```

Each sample carries:

- normalized arc parameter `u` in `[0,1]`;
- image coordinates;
- visibility state;
- confidence/provenance.

The curve can contain any number of samples. Evaluation resamples ordered curves by arc
length, so models are not forced to emit the same number of control points.

This is surface/centreline evidence, not a claim about internal vertebral joint centres.

## Minimal baselines

1. existing animal keypoints for body context;
2. SuperAnimal ear/tail endpoints as a **research-only comparison**;
3. segmentation-mask → skeleton → longest base-to-tip path as a non-learned tail
   centreline baseline;
4. only after those baselines, a small learned feline detail head.

## Metrics

### Ear

- normalized point error for the three visible landmarks;
- base-centre error;
- ear-axis angular error;
- visibility/coverage;
- left/right identity swaps over time.

### Tail

- ordered resampled curve error normalized by image diagonal;
- maximum resampled curve error;
- base/tip endpoint error;
- visible-arc coverage;
- topology failure (missing base/tip or disconnected curve);
- temporal consistency only on an explicitly motion-controlled slice.

## Scientific boundary

- Threshold coverage is not landmark accuracy.
- A teacher's pseudo-label is not independent ground truth.
- SuperAnimal/FMPose outputs remain isolated research evidence under Issue #9.
- Occluded tail geometry may be predicted with uncertainty, but must not be relabeled as
  directly observed truth.

## First implementation slice

```text
feline-detail JSON contract
→ pure-Python ear/curve metrics
→ deterministic synthetic fixtures
→ mask-skeleton tail baseline
→ licence-clean real-video sparse labels
→ learned detail head only if the baseline gap persists
```
