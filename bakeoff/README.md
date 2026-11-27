# Feline model bake-off

Issue: #8

This experiment answers one question before CatPose trains another pose network:

> **What feline-specific capability is still missing after current animal pose models are
> given a fair test?**

The bake-off is deliberately model-neutral. Every adapter converts native model output
into one prediction contract, then common metrics measure coverage, motion consistency,
3D plausibility, and feline-specific topology gaps.

## Baselines

| ID | Role | Dimensionality | Current commercial status |
|---|---|---:|---|
| `rtmpose_animal` | Fast generic animal baseline | 2D | `unknown` pending packaged-checkpoint pretraining review |
| `superanimal_quadruped` | Broad quadruped research baseline | 2D | `research_only` for provided SuperAnimal weights |
| `fmpose3d_animal` | Monocular animal lifting baseline | 2D -> 3D | `research_only_or_unknown` pending all downloaded weight licences |
| `gem_x_reference` | Architecture reference only | human 2D -> 3D | not a feline baseline |

See `models.json` and Issue #9. Code licence and checkpoint licence are tracked
separately. A permissive library does not make every downloaded weight or training source
commercially reusable.

## Evaluation slices

A useful first set is small: 2–4 clips per slice, enough to expose systematic failure
before scaling.

1. lateral walk / trot;
2. frontal and rear locomotion;
3. sit, lie, stand, turn;
4. jump up / jump down;
5. self-occlusion and furniture occlusion;
6. moving-camera footage;
7. close face / ear motion;
8. fast or high-curvature tail motion.

No owner-operated capture is required. `clip-manifest.schema.json` permits owned,
redistributable, link-only, or synthetic inputs. Link-only clips must never be committed
as copied media.

## Canonical prediction contract

Each model emits one JSON document per clip conforming to
`prediction.schema.json`.

Important design choices:

- preserve both `native_name` and optional `canonical_name`;
- never pretend a missing feline landmark exists;
- 2D coordinates are pixels in the source frame;
- 3D coordinates must name their coordinate frame;
- model confidence remains model confidence, not benchmark uncertainty;
- adapter metadata records model/version/checkpoint and licence status;
- per-frame inference time is recorded independently of video decoding where the native API permits it.

## Metrics implemented in v0

`evaluate.py` computes metrics that do not require a dense human-labelled ground-truth
set:

- keypoint coverage above a confidence threshold;
- per-keypoint dropout count and recovery length;
- normalized 2D **motion curvature** (second difference);
- motion-curvature spike rate;
- 3D bone-length coefficient of variation when skeleton edges are declared;
- depth sign/ordering flips for declared diagnostic pairs;
- topology coverage for feline requirements such as paws, ears and tail.

Motion curvature is **not called jitter on unconstrained video**. It contains real animal
acceleration/articulation, camera motion, sampling effects and estimator noise. It may be
used as a jitter proxy only on a pre-declared quasi-static or otherwise motion-controlled
slice.

These are **failure-discovery metrics**, not a substitute for accuracy against independent
reference labels. Sparse observable labels can be added later for normalized 2D error and
confidence calibration.

## First real-model result

`bakeoff/reports/rtmpose-commons-cat-plays-v0.md` records the first zero-touch real-cat
smoke test. RTMPose Animal produced 17-point gross-body pose on eight sampled cat frames
with 98.53% thresholded coverage, but its AP-10K topology structurally lacks feline ear
tips and provides only a tail root—so it cannot represent the requested tail curve.

That result is evidence against making **generic 2D cat pose** the primary CatPose
novelty target. It is not yet evidence about SuperAnimal's richer topology or FMPose3D's
monocular 3D capability.

## Dry run

The mock adapter makes deterministic synthetic predictions so CI can test the full
contract without downloading any model weights:

```bash
python -m bakeoff.adapters.mock \
  --clip bakeoff/fixtures/mock-clip.json \
  --output /tmp/mock-prediction.json

python -m bakeoff.evaluate \
  /tmp/mock-prediction.json \
  --requirements bakeoff/feline-requirements.json
```

## Decision rule

Do **not** build a new general feline pose estimator merely because one baseline is
imperfect.

Escalate in this order:

1. native model + correct preprocessing;
2. topology mapping and temporal filtering;
3. video adaptation / lightweight fine-tuning where licence permits;
4. feline-specific output head for ears / paws / tail;
5. temporal/world-space reconstruction layer;
6. only then consider training a new general backbone.

The likely novel target is not generic cat pose. It is **real-time world-space feline
motion from monocular video**, with ears/tail/paws, occlusion recovery, moving-camera
handling, and calibrated uncertainty.
