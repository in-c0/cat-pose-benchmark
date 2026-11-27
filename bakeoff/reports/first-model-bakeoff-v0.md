# First feline model bake-off — Phase 0 decision

Status: **Phase 0 complete**

Decision: **NO-GO on training a new generic feline pose backbone or generic monocular 3D
lifter now.**

Three existing animal-pose paths were executed automatically on licence-approved real cat
video. They already cover gross feline 2D pose and generic monocular 3D well enough that
a new general-purpose backbone would duplicate existing capability before addressing the
parts that are actually feline-specific.

## Compared systems

| Capability | RTMPose Animal | SuperAnimal-Quadruped | FMPose3D Animals |
|---|---|---|---|
| role | fast generic 2D baseline | richer 2D research baseline | monocular 2D+3D research baseline |
| smoke input | 8 samples over 3.5 s | 8 frames / first 2 s @ 4 fps | 4 frames / first 1 s @ 4 fps |
| native points | 17 | 39 | 26 raw |
| thresholded 2D coverage* | 98.53% | 76.60% | 91.00% |
| eyes + nose represented | yes | yes | yes |
| all four paws represented | yes | yes | yes |
| explicit feline ear tips | **no** | **yes** | no — generic ear points only |
| ear-tip threshold stability | n/a | 4/8 each ear | n/a by semantic contract |
| tail base | yes | yes | yes |
| tail tip | no | yes | yes |
| tail mid / >=3-point curve | **no** | **no** | **no** |
| 3D | no | no | **yes, model-derived** |
| world-space/global trajectory | no | no | **no** |
| calibrated multimodal uncertainty | no | no | method can generate hypotheses, not yet a CatPose world-space uncertainty contract |
| product-use status | checkpoint lineage review required | research-only weights | research-only/unknown downloaded assets |

\* These coverage numbers are **not head-to-head accuracy scores**. The clips, sampling
and native topologies differ, and no dense independent reference labels were used.

## What is already solved enough not to reinvent first

### Generic 2D cat body pose

RTMPose produced a useful 17-point pose on the real cat smoke clip with 98.53%
thresholded point/frame coverage. SuperAnimal also represented the body, paws and face.
A new backbone whose principal claim is simply "detect cat joints" is therefore a weak
research contribution and a poor use of implementation time.

### Richer quadruped endpoint topology

SuperAnimal already includes explicit ear endpoints and a tail endpoint. Its ear-tip
confidence varied substantially in the smoke sequence, so fine feline detail is not
proven solved—but the problem has shifted from *invent an ontology/backbone* to *make
fine feline geometry precise and temporally stable*.

### Generic monocular animal 3D

FMPose3D returned 3D for all four smoke frames. Those coordinates remain model-derived
and model-native, and some nominal limb lengths varied considerably. Still, the existence
of a functioning cat-capable 2D→3D path makes "build a generic monocular cat 3D lifter"
another weak primary novelty target.

## Residual gap worth building

### A. Feline detail geometry

The strongest common structural gap across all three systems is a **continuous tail
representation**.

- RTMPose: tail root only.
- SuperAnimal: tail base + tail tip.
- FMPose3D: tail root + tail tip.
- none provide >=3 feline tail points / centreline / spline.

Ear geometry is the second gap:

- RTMPose has no ear-tip topology;
- SuperAnimal has ear tips but only 4/8 threshold coverage per ear in the first smoke;
- FMPose uses generic ear points whose semantics should not be silently promoted to ear
  tips.

The smallest justified model contribution is therefore likely a **feline detail head**:

```text
shared animal features
  → ear base + ear tip + ear-plane/orientation outputs
  → dense tail centreline / spline control points
  → optional fine paw/face outputs if measured gaps justify them
```

This can sit on top of an existing or independently retrained generic animal backbone.

### B. GEM-like temporal/world-space feline motion

None of the tested animal systems supplies the full product/research target:

```text
monocular cat video
→ temporally coherent feline geometry
→ occlusion recovery
→ camera-motion disentanglement
→ global/world-space trajectory
→ uncertainty
→ contact / motion events
```

This is where NVIDIA GEM-X is architecturally relevant despite being human-specific.
Rather than reuse its human topology/body weights, CatPose can adapt the **problem
decomposition**: local pose + temporal motion + camera/global trajectory, using an animal
front end and feline-specific detail representation.

## Phase-0 architecture recommendation

```text
fast animal 2D backbone
    │
    ├── generic body / paws / face
    │
    └── feline detail head
          ├── ear geometry/orientation
          └── tail spline / centreline
                │
                ▼
      animal 3D hypothesis layer
                │
                ▼
       temporal feline model
          ├── occlusion recovery
          ├── anatomical consistency
          └── calibrated uncertainty
                │
                ▼
      camera / scene motion layer
                │
                ▼
       world-space trajectory
          + contacts/events
```

For research experiments, SuperAnimal/FMPose3D can remain isolated baselines/teachers
subject to Issue #9. A commercial runtime should use weights whose code, dataset and
checkpoint lineage are independently cleared.

## Phase-0 decision rules

### NO-GO now

- new generic feline 2D backbone;
- new generic monocular feline 3D lifter;
- personal physical capture rig;
- claims of metric/world-space real-cat 3D from these smoke outputs.

### GO now

1. define and test a feline-specific ear + tail representation;
2. benchmark whether a small detail head can close those gaps over a frozen/replaceable
   animal feature extractor;
3. prototype a temporal/world-space layer inspired by GEM-X's decomposition;
4. keep uncertainty and evidence provenance explicit;
5. expand the real-video benchmark only enough to falsify the above choices, rather than
   collecting a large dataset by default.

## Important experimental limitations

- These are smoke tests on one source video, with different sampling windows.
- Threshold coverage is not landmark accuracy.
- Free-motion second differences are reported as motion curvature, not jitter.
- DeepLabCut wall-time measurements currently include setup; RTMPose timing is scoped
  differently, so runtime values are not ranked here.
- FMPose3D coordinates are model-native reconstruction, not independent metric truth.
- Research-only checkpoint outputs are not automatically permitted product-training
  labels.

## Evidence

- RTMPose report: `rtmpose-commons-cat-plays-v0.md`
- SuperAnimal report: `superanimal-commons-cat-plays-v0.md`
- FMPose3D report: `fmpose3d-commons-cat-plays-v0.md`
- licensing gate: Issue #9
- experiment tracker: Issue #8
