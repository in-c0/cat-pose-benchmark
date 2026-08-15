# FMPose3D Animals — `commons-cat-plays` smoke result

Status: **real-model 2D+3D research smoke passed**

This test asks whether generic monocular animal 3D lifting already runs on ordinary cat
video before CatPose invests in a new feline 3D backbone. It does. The result remains
model-derived reconstruction evidence, not independent metric ground truth.

## Input

- source clip: `commons-cat-plays` / Wikimedia Commons `Cat_Plays.webm`
- recorded source licence: CC-BY-SA-4.0
- source SHA-256:
  `3258309e1d573fda6595fee0c02e3f055931a06c01bac24d986a5aff28297b32`
- smoke clip: first 1 s resampled to 4 fps
- frames: 4
- confidence threshold: 0.2

## Runtime environment

GitHub-hosted Ubuntu CPU runner:

- Python 3.11
- DeepLabCut 3.0.1
- FMPose3D installed through `deeplabcut[fmpose3d]`
- PyTorch 2.4.1+cpu
- CUDA unavailable

The adapter used DeepLabCut's current `video_inference_superanimal` entrypoint with
`model_name="fmpose3d_animals"`, `fmpose_return_3d=True`, one individual and CPU
execution.

## Result

### 2D

- raw FMPose animal topology: 26 points/frame
- threshold-visible native point count reported by the evaluator: 25
- overall 2D point/frame coverage at score >=0.2: **91%**
- eyes: 4/4 each
- nose: 3/4; scores approximately 0.130, 0.320, 0.317, 0.298
- all four paws: 4/4 each
- tail base: 4/4
- tail tip: 4/4
- tail mid: absent
- tail requirement coverage: **66.7%**
- benchmark tail-curve requirement: **failed** (2 tail endpoints, requires >=3)

FMPose's generic `left_ear` / `right_ear` points are intentionally **not** mapped to
CatPose `left_ear_tip` / `right_ear_tip`. Their threshold coverage in this smoke clip was:

- generic left ear: 3/4 (frame 0 ≈0.156; later ≈0.722, 0.232, 0.743)
- generic right ear: 4/4 (≈0.257, 0.503, 0.533, 0.667)

Therefore CatPose ear-tip ontology coverage remains 0% for this adapter. This is a
semantic boundary, not a claim that the FMPose ear points are useless.

### 3D

All **4/4 frames** contained 3D output for the animal topology. The adapter preserves the
coordinate frame as `model_native`; it does not relabel these values as camera-space,
world-space or metric gold.

No diagnostic depth ordering flips were observed across the four frames for:

- left vs right eyes;
- left vs right front paws;
- left vs right hind paws.

However, several nominal limb-edge lengths varied materially over these four frames.
Coefficient of variation examples:

| Edge | CV |
|---|---:|
| left elbow → left front paw | 0.175 |
| left hip → left hind knee | 0.175 |
| left hind knee → left hock | 0.189 |
| right elbow → right front paw | 0.203 |
| right shoulder → right elbow | **0.342** |
| right hip → right hind knee | **0.496** |
| right hock → right hind paw | 0.094 |

This is a plausibility warning, not an accuracy verdict. Four frames, model-native scale,
occlusion and reconstruction ambiguity are insufficient to diagnose the source of the
variation. It does establish that the smoke output should not be treated as a rigidly
stable anatomical reconstruction without additional temporal/body constraints.

### Motion statistic

Mean normalized 2D motion curvature ≈ **0.04698**; provisional curvature-spike rate
≈ **0.8049** across 41 available samples.

This is not called jitter: the statistic mixes true feline motion, sampling, camera
motion and estimator noise.

### Runtime

Approximate whole-call amortized CPU time: **8961 ms/frame** (~0.112 fps).

This timing includes DeepLabCut/FMPose setup and is **not directly comparable** with the
RTMPose adapter's per-frame post-initialization timing. A common timing scope is required
before throughput ranking.

## Evidence-backed conclusion

Generic monocular animal 3D lifting already exists and executes successfully on cat
video. Therefore **a new generic feline 3D lifter is not justified as CatPose's primary
novelty target at this stage**.

The remaining structural gaps are clearer:

1. continuous tail geometry rather than root/tip only;
2. feline-specific ear landmarks/orientation rather than generic ear points;
3. temporal anatomical consistency and occlusion recovery;
4. camera-motion disentanglement and world-space trajectory;
5. calibrated multiple-hypothesis uncertainty;
6. scene/contact events such as paws on surfaces, takeoff and landing.

## Reproducibility

Successful GitHub Actions run: `31890429115`

Artifact: `fmpose3d-real-cat-smoke`, ID `9248417588`

Artifact digest:
`sha256:59ac042525f142494e97b69882d37371249d287b7a66c38069cbc5f677946592`
