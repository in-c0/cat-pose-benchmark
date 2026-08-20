# S0A deterministic procedural-proxy handshake

Status: software-only reference implementation for #54 / first slice of #7.

This directory freezes the **annotation contract** that a later Unity exporter must match. It does not use a cat asset, real animal media, a trained pose model, or physical measurement.

## Why this exists

The V1 benchmark needs a reproducible way to prove that engine/runtime truth can be exported with explicit coordinates, timing, visibility, contact state, derivatives, provenance and uncertainty before any real collection starts.

S0A therefore uses project-authored analytic proxy geometry. The result is **X1 synthetic exact** evidence: exact inside this generator, but not evidence that a monocular system is accurate on real cats.

## Frozen conventions

- World: Unity-compatible axes, `+X` right, `+Y` up, `+Z` forward.
- World/camera units: metres.
- Camera: identity orientation, declared position and pinhole intrinsics.
- Image: top-left origin, `+u` right, `+v` down.
- Time: fixed 10 Hz (`dt = 0.1 s`), integer frame indices, nanosecond timestamps.
- Subject motion: analytic polynomial root motion with exact analytic velocity and acceleration.
- Visibility: image-frustum test plus deterministic line-segment/AABB occlusion.
- Contact: paw-centre height against a declared floor plane and zero-tolerance synthetic contact rule.
- Uncertainty: zero-radius `synthetic_exact` confidence regions; this is simulator certainty, not real-world uncertainty.
- Evidence tier: `X1` for every exported observation.

## Generate the canonical fixture

```bash
python -m synthetic.s0_proxy --output synthetic/fixtures/s0_proxy_v0.json
```

Validate an existing fixture without rewriting it:

```bash
python -m synthetic.s0_proxy \
  --output synthetic/fixtures/s0_proxy_v0.json \
  --validate-only
```

The generator computes `payload_sha256` over the canonical JSON payload excluding the digest field itself. The unit suite also pins the expected digest and compares a fresh generator run with the committed fixture.

## What the fixture contains

The five-frame sequence includes:

- procedural surface landmarks in world and image coordinates;
- a world/image tail centreline;
- analytic subject-root velocity and acceleration;
- four paw/floor contact observations;
- a moving box occluder that blocks the left ear only on frames 2–3;
- camera intrinsics/extrinsics and dynamic scene-object transforms;
- explicit source IDs, lineage, visibility, evidence tier, quality and uncertainty for every observation.

All individual observations validate against `schemas/observation.schema.json`.

## M1 boundary

S0A deliberately proves the new V1→M1 boundary in the negative direction.

The fixture is `X1` synthetic exact. A structurally valid V1 pose package built from it **must be rejected** by `fusion.v1_pose_package.validate_pose_package`, because M1's prospective-real visual comparator accepts only G2/G3/S1/S2 evidence.

Passing S0A therefore does **not** make an episode M1-ready and does not create any pose-accuracy result.

## Unity handoff

The next S0 layer should make a minimal Unity scene emit this same contract. The Unity exporter must reproduce:

1. coordinate and image conventions;
2. fixed timestep and timestamp mapping;
3. surface landmark and tail topology;
4. camera projection;
5. collider/contact truth;
6. line-of-sight visibility/occlusion;
7. temporal derivatives;
8. X1 provenance and source lineage.

A round-trip comparator should then fail on any runtime/export mismatch rather than tolerating silent convention drift.

## Claims boundary

This directory contains no real cat data, no animal experiment, no behavioural inference, no intent translation, no external asset, and no claim that synthetic correctness transfers to real-world pose accuracy.
