# RTMPose Animal — `commons-cat-plays` smoke result

Status: **real-model smoke passed**

This is the first model result in Issue #8. It is deliberately small and answers
whether the generic RTMPose Animal path executes on an ordinary cat video and what its
native topology can or cannot express. It is **not** an accuracy benchmark.

## Input

- clip: `commons-cat-plays`
- source: Wikimedia Commons `Cat_Plays.webm`
- recorded licence: CC-BY-SA-4.0
- materialized SHA-256:
  `3258309e1d573fda6595fee0c02e3f055931a06c01bac24d986a5aff28297b32`
- sampled frames: 8
- source-frame stride: 15
- evaluated timestamps: 0.0 through 3.5 s at 0.5 s spacing
- confidence threshold: 0.2

See `bakeoff/clips/commons-cat-plays.json` for provenance.

## Runtime environment

GitHub-hosted Ubuntu CPU runner:

- Python 3.10.20
- NumPy 1.26.4
- OpenCV 4.10.0
- PyTorch 2.0.1+cpu
- MMCV 2.1.0
- MMEngine 0.10.7
- MMDetection 3.2.0
- MMPose 1.3.2

The workflow downloaded the published OpenMMLab RTMPose AP-10K checkpoint and RTMDet-m
COCO detector at runtime, then validated and evaluated the canonical prediction output.

## Result

### Native 2D coverage

- native topology: 17 AP-10K keypoints
- thresholded keypoint coverage: **98.53%**
- all mapped face points present across the sampled sequence: eyes + nose
- all four required paw semantics occur in the output
- only two threshold failures occurred:
  - first sampled frame `left_front_paw`: score ≈ **0.177**
  - first sampled frame `left_shoulder`: score ≈ **0.154**
- every later sampled frame cleared 0.2 for all 17 points

This establishes that the generic model can produce a dense gross-body cat pose on this
clip. It does **not** establish anatomical accuracy because these frames have no
independent reference labels.

### Feline-specific topology gap

| Requirement | Coverage | Structural result |
|---|---:|---|
| face: eyes + nose | 100% | represented |
| four paws | 100% | represented |
| ear tips | 0% | absent from AP-10K topology |
| tail base/mid/tip | 33.3% | tail base only |
| usable tail curve | no | 1 tail point; benchmark requires at least 3 |

The ear/tail failure is therefore not merely low confidence on this clip. **RTMPose's
native AP-10K output cannot represent the requested feline ear tips or continuous tail
shape at all.**

### Motion statistic

The eight samples produced mean normalized 2D second difference ≈ **0.0992**, with 80%
of available triplets above the provisional 0.03 threshold.

This value must **not** be described as jitter. The cat is moving and the smoke run uses
0.5 s sampling, so the statistic mixes real articulation/acceleration, camera effects,
sampling and estimator noise. The evaluator now names it `motion_curvature` and permits
jitter interpretation only on a pre-declared quasi-static or otherwise
motion-controlled slice.

### Runtime

- mean inference: **722.5 ms/frame**
- p95 inference: **736.0 ms/frame**
- effective throughput: **1.38 fps**

This is CPU smoke-test throughput only. It is not a real-time deployment conclusion;
GPU/ONNX/TensorRT performance must be measured separately.

### 3D

None. This baseline is 2D only.

## Evidence-backed conclusion

For this cat clip, RTMPose is already sufficient to make **generic 2D cat-body pose** a
weak novelty target. The first unambiguous feline-specific gaps are:

1. ear-tip / ear-orientation detail;
2. tail tip and, more importantly, continuous tail geometry;
3. temporal/world-space motion, which this framewise 2D baseline does not provide.

The next comparison must test whether SuperAnimal-Quadruped already closes (1) and part
of (2), and whether FMPose3D already closes generic monocular 3D. Only the residual gap
after those baselines should motivate a new CatPose model.

## Reproducibility

Successful GitHub Actions run: `31889985893`

Artifact: `rtmpose-real-cat-smoke`, ID `9248307016`

Artifact digest:
`sha256:90f41d6ef131a8d575fa2626b013e2e27658777538fbb779763c5b8912b33c60`
