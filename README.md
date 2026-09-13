# cat-pose-benchmark

**An open benchmark and capture methodology for temporally stable feline pose, facial,
ear, tail, contact, and scene-relative motion in real environments.**

> The repository name is provisional. The consumer cat brand and its products should
> remain separate from this research artefact.

---

## Status: research direction v0.2 + Stage 0 design + model bake-off

Created 2026-08-03. Visual benchmark direction revised 2026-08-04. Scope narrowed back to the
pose benchmark on 2026-09-11.

The project is no longer based on the assumption that a real benchmark must be either
fully hand-labelled or represented by one supposedly perfect source of truth. Its core
methodological position is now:

> **Each frame contains partially observable truths from different measurement sources,
> each with its own provenance and time-varying uncertainty.**

The Stage 0 rigid-target experiment is specified and its nominal mirror layouts have
been compared by a reproducible geometry-conditioning simulation. No animal collection
has started.

No outbound licence is set yet. Until the decisions in
[docs/OPEN-DECISIONS.md](docs/OPEN-DECISIONS.md) are resolved, the repository remains
all rights reserved. A licence must be added before any data, weights, or reusable code
are released.

## Help review frames (no setup needed)

The quickest way to help right now is to look at model output on real cat video and say
whether it is on the cat. It takes about 30–45 minutes, needs no code, and gives this
project its first numbers from a person rather than from one model checking another.

1. **Look at the sheets.** Four images, one per clip and method. Each tile is one frame with
   the model's output drawn on it; the banner shows the frame index.
   - [Cat Plays — body](review/results/2026-09-13-commons-v0/sheets/commons-cat-plays--body.jpg)
   - [Cat Plays — tail](review/results/2026-09-13-commons-v0/sheets/commons-cat-plays--tail.jpg)
   - [Jumping — body](review/results/2026-09-13-commons-v0/sheets/commons-cat-jumping-backwards--body.jpg)
   - [Jumping — tail](review/results/2026-09-13-commons-v0/sheets/commons-cat-jumping-backwards--tail.jpg)
2. **Get the template.** Download
   [`TEMPLATE.csv`](review/results/2026-09-13-commons-v0/reviews/TEMPLATE.csv) and rename it
   to `<your-github-handle>.csv`. One row per frame and body part, 285 rows.
3. **Fill the `verdict` column** with `ok`, `wrong` or `not_visible`, following the rubric in
   [review/README.md](review/README.md). Skip rows you are unsure about rather than guessing;
   blank rows are ignored. `condition` and `note` are optional.
4. **Send it back.** Either open a pull request adding your file to
   `review/results/2026-09-13-commons-v0/reviews/`, or attach the CSV to
   [the review call issue](https://github.com/in-c0/cat-pose-benchmark/issues/79) if you
   would rather not deal with git. Both are fine.

Every reviewer's verdicts are kept as a separate file. With two or more reviewers the scorer
reports agreement and lists every disagreement, so you do not need to match anyone else.

If you want to run the models on your own cat video instead, see
[CONTRIBUTING.md](CONTRIBUTING.md).

## Scope note

For a few weeks in August 2026 this repository grew into a multimodal "feline intent
programme" (vocalisation acoustics, environmental audio, household context capture,
intervention pilots, fusion ablations, latent-state discovery). None of it needed a pose
benchmark to exist and none of it produced a positive result, so on 2026-09-11 it was
carved out. That work is preserved unchanged on the `programme/multimodal-intent` branch
and at tag `programme-v0-2026-08-25`; `main` is the pose benchmark only.

## Research objective

Build an open, licence-clean benchmark that can answer:

> Can an ordinary monocular RGB system recover feline surface pose and motion with
> calibrated uncertainty, using independent geometric and contact measurements only for
> a compact gold-standard subset?

The eventual app or puck should operate from one ordinary camera. More specialised
capture equipment exists only to establish whether the monocular system is correct.

## What counts as ground truth

The benchmark does **not** pretend that every anatomical joint is directly visible.
Annotations are separated into:

1. **Surface observations** — visible landmarks, contours, face points, ear geometry,
   and tail centreline.
2. **Contact observations** — paw location, support surface, take-off, landing, stance,
   and other independently measured contact events.
3. **Latent anatomical estimates** — joint centres or hidden geometry inferred through
   anatomical and temporal models. These are estimates, never silently promoted to
   direct truth.
4. **Scene-relative observations** — camera pose, surfaces, obstacles, object relations,
   and world-space trajectory.
5. **Temporal measurements** — displacement, velocity, acceleration, curvature change,
   blink timing, ear flicks, tail motion, gait phase, and recovery after occlusion.

Every observation records its source, quality tier, visibility, uncertainty, and
lineage. See [docs/GROUND-TRUTH-PROVENANCE.md](docs/GROUND-TRUTH-PROVENANCE.md).

## Proposed capture strategy

### 1. CatPose Portal — compact gold subset

A low-cost open capture appliance using one physical camera and calibrated mirrors to
produce simultaneous virtual views. A transparent or instrumented surface can add
independent paw-contact evidence.

This avoids multi-device synchronisation while preserving true simultaneous geometry
for fast ear, face, paw, and tail motion.

The first validation step is deliberately animal-free. See
[docs/STAGE-0-PORTAL-GEOMETRY.md](docs/STAGE-0-PORTAL-GEOMETRY.md).

### 2. Monocular real-home set — deployment benchmark

Ordinary owner-shot video under the conditions that break models: occlusion, motion
blur, dark and long fur, clutter, low light, changing viewpoint, multi-cat scenes, and
partial exits from frame.

A scene-mapping system may provide camera trajectory and static-world geometry, but
model-derived feline pose remains labelled as estimated supervision unless independently
validated.

### 3. Synthetic and reconstructed data — supplementary training only

Unity-generated data, personalised digital twins, and model-generated labels may support
pretraining, ablations, and rare-case coverage. They do not independently validate the
same assumptions used to generate them.

## Initial benchmark tracks

- Temporally stable 2D surface landmarks
- Ear articulation and facial landmark tracking
- Tail centreline and curvature tracking
- Calibrated 3D surface reconstruction on the gold subset
- Paw contact, gait events, take-off, and landing
- Occlusion recovery and long-horizon drift
- Scene-relative position and support-surface reasoning
- Confidence and uncertainty calibration
- Edge deployment accuracy, latency, memory, power, and thermal behaviour

## What this is not

This benchmark does not decode intent and does not claim literal semantic translation.
It produces calibrated visual measurements. What anyone infers from those measurements is
a separate question with its own validation burden.

Pain, health, welfare, or diagnostic inference is a separate research and validation
programme. This repository produces measurement infrastructure, not veterinary claims.

## First public milestone

**CatPose Benchmark Protocol v0.1** should ship before model-building begins. It must
include:

- observable/latent ontology;
- keypoint and curve topology;
- provenance and uncertainty schema;
- minimal CatPose Portal experiment;
- real-home challenge taxonomy;
- metrics and acceptance gates;
- consent and redistribution requirements;
- one small demonstration sequence and Unity inspection view.

## Repository map

```text
docs/
  RESEARCH-CHARTER.md               benchmark question, hypotheses, and gates
  GROUND-TRUTH-PROVENANCE.md        observation tiers, uncertainty, and anti-circularity
  BENCHMARK-PROTOCOL-DRAFT.md       capture tiers, evaluation tracks, and v0 experiment
  STAGE-0-PORTAL-GEOMETRY.md        rigid-target mirror-layout experiment and gates
  KEYPOINT-TOPOLOGY-DRAFT.md        proposed landmarks and compatibility constraints
  ID1-PERSISTENT-IDENTITY.md        persistent same-cat identity across time (REMIND baseline)
  ID1-YOUTUBE-VIS-ADAPTER.md        frozen YouTube-VIS feline subset for identity evaluation
  PRIOR-ART-AND-LICENCE-SURVEY.md   existing resources and licence status
  LICENSING-POLICY.md               contamination and release constraints
  OPEN-DECISIONS.md                 unresolved choices that block collection

schemas/
  observation.schema.json           machine-readable observation/provenance draft

stage0/                             mirror-portal geometry conditioning simulation (#1)
synthetic/                          S0A procedural-proxy annotation contract + S0B Unity round-trip (#7, #54)
bakeoff/                            fair test of existing animal pose models on real cat clips (#8)
detail/                             feline detail head: SAM2 ear geometry and tail centreline (#11)
temporal/                           whole-animal tracking and identity assignment across frames (#12)
identity/                           ID1 persistent identity: REMIND baseline, DINOv3 pin, YouTube-VIS adapter
review/                             human frame review: overlays, contact sheets, verdict rubric and scorer

Each experiment directory has its own README and a reports/ or results/ folder with
what was actually run.
```
