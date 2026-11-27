# Licensing policy

The only part of this repo that is **not** open for research-direction revision. The
contamination rules below hold regardless of which direction the project takes, because
violating them is not recoverable — a poisoned model cannot be un-poisoned, and the
whole premise of the project is producing something commercially usable.

---

## 1. Inbound: what may not enter this project

**Prohibited as training data, teacher models, pseudo-labellers, pre-training, or
fine-tuning bases:**

| Source | Licence | Status |
|---|---|---|
| CatFLW (2,079 imgs, 48 landmarks) | CC BY-NC 4.0 | **Prohibited** — non-commercial |
| SuperAnimal-Quadruped / Quadruped-80K | modified MIT, models research-only | **Prohibited** |
| SMAL / SMALR (MPI) | non-commercial research licence | **Prohibited** |
| Animal-Pose (Cao et al.) | **no stated licence**; images from mixed internet sources | **Prohibited** — unclearable |
| Feighelstein cat pain datasets | unreleased, request-based, clinical ethics | **Prohibited** |
| Any scraped or "found online" imagery | — | **Prohibited** |

### The distillation rule

**Using a non-commercially-licensed model to label data produces a derivative work
bound by that model's licence.** This includes:

- running SuperAnimal to generate pseudo-labels, even if the images are your own;
- training on CatFLW then fine-tuning on clean data ("washing" the weights);
- using an NC-trained model to filter, rank, bootstrap, or QA a clean dataset;
- initialising from NC weights and training to convergence on clean data.

There is no sequence of these steps that produces a clean model. If it touched NC data,
it is NC. Treat weights with the same provenance discipline as data.

### Permitted with conditions

| Source | Licence | Condition |
|---|---|---|
| AP-10K | **ambiguous** — repo says CC-BY-4.0, MMPose zoo lists non-commercial | **Do not use until resolved in writing with the authors.** Record the reply in this repo. |
| APT-36K | MIT (per repo) | Permitted. Verify the LICENSE file at the commit actually used and pin it. |
| Oxford-IIIT Pet | CC BY-SA 4.0 | Permitted, but **ShareAlike is viral on derivatives** — using it may force the outbound dataset to CC BY-SA. Decide before use, not after. |
| Rigged 3D cat assets | per-asset commercial licence | Permitted **only** with explicit commercial/redistribution terms. Verify per asset, keep receipts and licence text in the repo. |
| Unity Perception | Unity package licence | Permitted. Note Unity Editor licensing tier applies separately to revenue thresholds. |
| MMPose / RTMPose | Apache-2.0 (code) | Code permitted. **Weights inherit their training data's licence** — train from scratch or from clean weights only. |
| Ultralytics YOLO | AGPL-3.0 | **Avoid.** Commercial use needs a paid Enterprise licence at undisclosed cost, and AGPL would otherwise force the entire product open. |

---

## 2. Rigged asset provenance

Every 3D asset used to generate training data must have, recorded in-repo before use:

- source and URL, purchase/download date, price paid;
- the exact licence text as supplied (not a link — vendors change terms);
- explicit confirmation that **derivative rendered imagery may be redistributed**, since
  the generated dataset is the intended public artefact;
- confirmation that **model weights trained on renders of the asset** are unencumbered.

The second and third points are where asset-store licences most often fail. Many permit
use *in a game* while saying nothing about redistributing renders as a dataset. **When a
licence is silent, treat it as prohibited and ask the vendor in writing.**

---

## 3. Outbound: what this project publishes — OPEN

Three artefacts, three separate decisions. None made.

### 3a. Code — **OPEN**
Apache-2.0 (patent grant, permissive) or MIT (simpler). Apache-2.0 is the stronger
default for anything with a commercial product downstream.

### 3b. Synthetic dataset — **OPEN**
CC BY 4.0 is the natural choice if the goal is adoption. Note the tension the owner
should decide deliberately: **CC BY 4.0 lets competitors use it commercially too.** That
is the price of the "contribute and lead" position, and it is probably worth paying —
the reputational asset is authorship, not exclusivity. CC BY-NC would defeat the entire
premise of the project by reproducing the exact gap it was created to close.

### 3c. Real benchmark set — **OPEN and hardest**
Constrained by contributor consent. If footage is solicited, the CLA must grant
redistribution rights compatible with whatever licence is chosen here — decided
*before* collection begins, because it cannot be retrofitted onto contributors after
the fact.

### 3d. Model weights — **OPEN**
Weights trained purely on clean synthetic data can be released under any chosen licence.
This is a genuine strategic asset: a permissively-licensed cat pose model would be the
first of its kind, and it is a stronger contribution than the dataset alone.

---

## 4. Record-keeping

- `provenance/` — asset licences, purchase records, correspondence. **OPEN:** create
  when first asset is acquired.
- Licence enquiry replies (AP-10K authors, asset vendors) are committed to the repo as
  received, verbatim.
- Every dataset release ships a datasheet stating sources, licences, coverage gaps, and
  known biases.
