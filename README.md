# cat-pose-benchmark

**An open, licence-clean keypoint benchmark for domestic cats — annotated in real
environments, with ear and tail topology that no existing public dataset provides.**

> **Repo name is a placeholder.** The consumer brand is not named yet; this repo is the
> research artefact, and the two do not have to share a name.

---

## Status: SCAFFOLD — held pending research direction

Created 2026-08-03. **Nothing is being built yet.** Research direction is still being
defined; this repo exists to hold the decisions and the evidence in one place.

**No outbound licence is set yet** — that is
[an open decision](docs/OPEN-DECISIONS.md), and until it is made the default
(all rights reserved) applies. A licence will be added before any data or model is
released. If you want to use any of this in the meantime, please open an issue.

Every design choice below is marked **OPEN** and is deliberately undecided. See
[docs/OPEN-DECISIONS.md](docs/OPEN-DECISIONS.md).

---

## Why this exists

The feasibility review ([docs/PRIOR-ART-AND-LICENCE-SURVEY.md](docs/PRIOR-ART-AND-LICENCE-SURVEY.md)) found a
specific, verified gap:

- Every public keypoint dataset that annotates **cat ears or tail** is non-commercial
  (CatFLW, CC BY-NC), research-only (SuperAnimal), or has **no stated licence at all**
  (Animal-Pose).
- Every public dataset that is **commercially usable** (AP-10K, APT-36K) uses a
  17-keypoint skeleton with **no ear keypoints and a single tail-root point**.
- There is **no public cat behaviour/ethogram video dataset** at any licence.

Ear position and tail motion are the two signals feline behaviour actually depends on.
They are the exact signals nobody has published under a usable licence.

**That gap is the asset.** This repo aims to close it.

## The approach

Two halves, deliberately separated — this separation is the methodological core:

1. **Training data: synthetic.** Rigged 3D cat models rendered through
   [Unity Perception](https://github.com/Unity-Technologies/com.unity.perception) with
   pose and domain randomisation. Ground truth is exact by construction, keypoint
   topology is arbitrary (so ear tips, ear bases, tail base→mid→tip come free), and the
   licence is clean provided the source assets are commercially licensed.
2. **Benchmark data: real.** Real cats, in real environments, annotated as an
   **evaluation set only** — never trained on. Stratified across the axes that actually
   break models: fur, motion, lighting, and indoor/outdoor.

The benchmark half is what makes this scientifically honest. Synthetic-trained models
report flattering numbers on synthetic test sets; the entire question is whether they
survive real fur, real motion blur, and real living rooms. **The benchmark is the
contribution, not the by-product.**

Draft protocol: [docs/BENCHMARK-PROTOCOL-DRAFT.md](docs/BENCHMARK-PROTOCOL-DRAFT.md)
Draft skeleton: [docs/KEYPOINT-TOPOLOGY-DRAFT.md](docs/KEYPOINT-TOPOLOGY-DRAFT.md)

## What this repo is not

- **Not a medical or veterinary instrument.** No pain scoring, no welfare inference, no
  diagnostic output. Anything health-adjacent is a separate project with a separate
  ethics and review path.
- **Not a "translator".** No semantic intent decoding is claimed, because none is
  scientifically supported. See the survey §2.
- **Not the consumer app.** Products built on this benchmark live in their own repos.

## Licensing — the one hard rule

**No CC BY-NC or research-only data may touch this project**, including as a teacher
model, a pseudo-labeller, or for pre-training. Derivative-work rules follow the source
licence and would silently poison every downstream product.

Full policy, including the still-open choice of outbound licence:
[docs/LICENSING-POLICY.md](docs/LICENSING-POLICY.md)

## Layout

```
docs/
  PRIOR-ART-AND-LICENCE-SURVEY.md   what exists, what it permits, where the gap is
  OPEN-DECISIONS.md                 the hold list; what must be settled before building
  BENCHMARK-PROTOCOL-DRAFT.md       real-environment stratification axes
  KEYPOINT-TOPOLOGY-DRAFT.md        proposed skeleton + compatibility with existing sets
  LICENSING-POLICY.md               contamination rules + outbound licence decision
```
