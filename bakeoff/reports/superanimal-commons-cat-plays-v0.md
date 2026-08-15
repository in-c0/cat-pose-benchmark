# SuperAnimal-Quadruped — `commons-cat-plays` smoke result

Status: **real-model research smoke passed**

This is a research-only comparison in Issue #8. It asks whether a richer existing
quadruped ontology already closes RTMPose's feline ear/tail endpoint gap. It does not
establish independent landmark accuracy and must not be treated as a product-runtime
licence decision.

## Input

- source clip: `commons-cat-plays` / Wikimedia Commons `Cat_Plays.webm`
- recorded licence: CC-BY-SA-4.0
- source SHA-256:
  `3258309e1d573fda6595fee0c02e3f055931a06c01bac24d986a5aff28297b32`
- smoke clip: first 2 s resampled to 4 fps
- frames: 8
- confidence threshold: 0.2

## Runtime environment

GitHub-hosted Ubuntu CPU runner:

- Python 3.11.15
- DeepLabCut 3.0.1
- NumPy 1.26.4
- pandas 2.3.3
- PyTorch 2.4.1+cpu
- TorchVision 0.19.1+cpu

The adapter used DeepLabCut's current `video_inference_superanimal` API with
`superanimal_quadruped`, `hrnet_w32`, Faster R-CNN detector, no video adaptation and one
maximum individual.

## Result

### Native 2D topology and thresholded coverage

- native output points: **39**
- overall point/frame coverage at score >=0.2: **76.60%**
- face requirement (eyes + nose): topology 100%; all three clear threshold on **8/8**
  frames
- paw requirement: topology 100%
  - left-front: 8/8
  - right-front: 7/8
  - left-hind: 8/8
  - right-hind: 8/8
- ear-tip requirement: topology 100%, but each ear tip clears threshold on only **4/8**
  frames
- tail:
  - tail base: 6/8
  - tail tip: 7/8
  - tail mid: **absent from ontology**
- benchmark tail-curve requirement: **failed** (2 available tail points; requires >=3)

The distinction between *ontology coverage* and *framewise confidence coverage* matters:
SuperAnimal can represent the ear tips and tail tip that RTMPose cannot, but this short
clip does not show those fine points as uniformly stable detections.

### Example fine-detail scores

Ear-tip confidence is strongly frame-dependent. Examples:

- frame 0: left ≈0.045, right ≈0.149
- frame 1: left ≈0.557, right ≈0.768
- frame 5: left ≈0.532, right ≈0.040
- frame 7: left ≈0.032, right ≈0.083

Tail endpoint confidence is better but still variable:

- tail base: threshold coverage 75%
- tail tip: threshold coverage 87.5%

No claim is made that high-confidence points are geometrically correct because this
smoke clip has no independent landmark reference labels.

### Motion statistic

Mean normalized motion curvature ≈ **0.06636**; 72.31% of available triplets exceed the
provisional 0.03 curvature threshold.

This is not a jitter measurement. The clip contains real animal motion; the statistic
mixes articulation, camera/sampling effects and estimator noise.

### Runtime

The adapter recorded approximately **8.55 s/frame amortized** on this CPU run. This is
**not comparable to RTMPose's per-frame timing**: DeepLabCut's public video API was timed
around the whole call and therefore includes model/setup overhead. It is retained only as
workflow-cost evidence until a common timing scope is implemented.

### 3D

None. SuperAnimal-Quadruped here is the 2D research baseline.

## Comparative interpretation after two models

RTMPose and SuperAnimal jointly narrow the likely CatPose gap:

| Capability | RTMPose Animal | SuperAnimal-Quadruped |
|---|---|---|
| gross body / paws | yes | yes |
| eyes + nose | yes | yes |
| ear tips in ontology | no | yes |
| tail base | yes | yes |
| tail tip | no | yes |
| >=3-point tail curve | no | no |
| monocular 3D | no | no |
| world-space temporal motion | no | no |

Therefore a new *generic* feline 2D backbone remains poorly justified. A continuous tail
representation remains a structural gap, while feline ear detail appears to be a
**stability/precision question** rather than a complete absence of existing topology.

FMPose3D is the next discriminator: it tests how much generic monocular animal 3D is
already available before CatPose adds a temporal/world-space layer.

## Reproducibility

Successful GitHub Actions run: `31890416926`

Artifact: `superanimal-real-cat-smoke`, ID `9248421061`

Artifact digest:
`sha256:7052e66b8c266681f5c2db619e4974e0790af07ac6750271eeec8f1775061ceb`
