# Real-environment benchmark protocol — DRAFT

**Status: DRAFT, nothing decided.** Owner named the axes (fur, motion, lighting,
indoor/outdoor); this expands them into a stratification design so the research-direction
pass has something concrete to cut. Every number below is a placeholder.

---

## What this set is for

An **evaluation-only** benchmark of real cats in real conditions. It is never trained
on. Its single purpose is to measure whether a synthetic-trained model survives contact
with reality.

This inversion — synthetic train, real test — is the methodological claim. If the
benchmark is easy, it proves nothing. **The benchmark should be hard on purpose.**

## Why an eval-only real set is the actual contribution

Existing animal-pose sets are training corpora that happen to have test splits drawn
from the same distribution. None isolates *why* a model fails. A stratified benchmark
lets a result read "89% overall, 41% on long-haired cats in low light" — which is a
finding, not a leaderboard number. That is publishable in a way that another training
set is not, and it is useful to every other group in the field regardless of whether
they adopt the skeleton.

---

## Stratification axes

### A. Fur — the axis most likely to break ear keypoints

| Level | Description | Why it matters |
|---|---|---|
| A1 | Short-haired, solid dark (black, dark grey) | Ear contour vanishes against body; near-zero internal contrast |
| A2 | Short-haired, solid light | Baseline easy case |
| A3 | Short-haired, high-contrast patterned (tabby, tuxedo, calico) | Pattern edges act as false keypoint evidence |
| A4 | Long-haired (Persian, Maine Coon, Ragdoll) | **Ear geometry physically occluded by fur**; tail silhouette diffuse |
| A5 | Brachycephalic (Persian, Exotic, British Shorthair) | Facial landmark topology genuinely differs — cephalic type is a known accuracy factor |
| A6 | Hairless (Sphynx) | Inverse case: ear geometry maximally visible. Useful upper bound |

**A1 and A4 are the hypothesised failure modes.** If the benchmark contains only
photogenic tabbies it will not be measuring anything.

### B. Motion — the axis most likely to break tail keypoints

| Level | Description |
|---|---|
| B1 | Static (sitting, loafing, sleeping) |
| B2 | Slow (walking, stretching, grooming) |
| B3 | Fast (running, jumping, play-pouncing) |
| B4 | **Tail-isolated motion** — body still, tail flicking/swishing |

B4 is the important one and is easy to omit by accident. Tail-tip motion at consumer
frame rates produces motion blur across the exact pixels the keypoint sits on. **OPEN:**
does the benchmark record shutter speed / frame rate per clip so this is measurable
rather than anecdotal?

### C. Lighting

| Level | Description |
|---|---|
| C1 | Daylight, indirect |
| C2 | Daylight, harsh/direct (blown highlights, hard shadow) |
| C3 | Artificial, warm domestic (evening living room — the modal real use case) |
| C4 | Low light / dusk (where phone cameras drop frame rate and raise ISO noise) |
| C5 | Mixed / backlit (silhouetted cat — contour-only information) |

### D. Environment

| Level | Description |
|---|---|
| D1 | Indoor, uncluttered |
| D2 | Indoor, cluttered (furniture occlusion, competing textures) |
| D3 | Outdoor, natural (grass, foliage — high-frequency background) |
| D4 | Outdoor, urban |
| D5 | Multi-cat in frame (identity assignment, keypoint attribution across instances) |

### E. Camera — free to vary, must be recorded

Distance, angle (frontal / profile / above / below / rear), device class, resolution,
frame rate. Rear-view is worth deliberate inclusion: it is the angle where tail is most
visible and face is entirely absent, and it will be common in real usage.

---

## Open sizing question

**OPEN.** Full-factorial across A×B×C×D is 6×4×5×5 = 600 cells and is not achievable
solo. Realistic options:

- **Fractional factorial** — cover main effects plus the interactions hypothesised to
  matter (A1×C4 dark cat in low light, A4×B4 long-haired tail motion, A1×D3 dark cat on
  grass).
- **Tiered** — a small dense core across A×B, with C and D sampled.

Either way the design must be fixed **before** collection, and the uncovered cells must
be stated in the datasheet as known coverage gaps. Silent truncation is what makes a
benchmark misleading.

---

## Sourcing — OPEN and licence-critical

The benchmark is worthless if it cannot be redistributed. Options, none decided:

1. **Self-shot** — fully clean, fully controlled, slow, and biased toward whatever cats
   are reachable.
2. **Solicited contributions** with an explicit contributor licence agreement — scales,
   but needs a real CLA and a real consent record per contributor. Cat owners are the
   rights-holders in their own footage.
3. **Shelter / rescue partnership** — breed and coat diversity in volume, plus a
   natural distribution story. Needs an institutional agreement and likely an ethics
   conversation even for observational filming.
4. **Existing permissively-licensed footage** — CC BY sources. Cheap, but licence
   provenance must be verified per clip, and CC BY-SA would make the benchmark viral.

**Hard rule regardless:** no scraping, no CC BY-NC, no "found on the internet". See
[LICENSING-POLICY.md](LICENSING-POLICY.md).

---

## Annotation of the benchmark set

Note the asymmetry: **training data is synthetic and free to label, but the benchmark is
real and must be hand-annotated.** This is the one place manual annotation is
unavoidable — and it is affordable precisely because an eval set is small.

**OPEN:** annotation protocol, inter-annotator agreement target, and whether a second
annotator is feasible solo. A benchmark with no reported IAA is weak; a benchmark with
a single annotator and honest disclosure is acceptable for a v1 release.

---

## Metrics — OPEN

Standard candidates: PCK / PCK@0.2, OKS-based AP (needs per-keypoint sigmas, which do
not exist for a novel cat skeleton and would have to be estimated), per-keypoint recall.

**Requirement regardless of choice:** results must be reportable **per stratum**, not
just in aggregate. A single headline number defeats the purpose of building a stratified
benchmark.
