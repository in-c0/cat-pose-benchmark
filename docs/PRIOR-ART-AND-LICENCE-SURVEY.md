# Cat pose & behaviour: prior art and licence survey

**Compiled 2026-08-03.** A survey of what public cat-behaviour datasets, models and
literature actually exist, and — the part that turns out to matter most — what their
licences permit.

Every licence below was checked at source. Where a licence is ambiguous or unstated,
that is recorded as ambiguous rather than resolved by assumption.

---

## Summary

1. **Every public keypoint dataset annotating cat ears or tail is unusable
   commercially** — non-commercial, research-only, or with no stated licence at all.
2. **Every commercially-usable animal-pose dataset omits ears entirely** and reduces the
   tail to a single root point.
3. **No public cat behaviour / ethogram video dataset exists** at any licence.
4. The literature supports **pain scoring and coarse affect classification**, not
   semantic intent decoding.

The intersection of (1) and (2) is the gap this project exists to close.

---

## 1. Datasets

### 1a. Cat-specific

| Dataset | Content | Licence | Commercial? |
|---|---|---|---|
| [CatFLW](https://github.com/martvelge/CatFLW) ([arXiv 2305.04232](https://arxiv.org/abs/2305.04232), [Kaggle](https://www.kaggle.com/datasets/georgemartvel/catflw)) | 2,079 cat face images, **48 facial landmarks** + bbox | **CC BY-NC 4.0** | **No** |
| Cat Pain Dataset (Feighelstein et al.; [Sci Rep 2022](https://www.nature.com/articles/s41598-022-13348-1), [Front Vet Sci 2024](https://pmc.ncbi.nlm.nih.gov/articles/PMC11663861/)) | 464 images / 26 domestic shorthairs, clinical | Not released; "available by the authors, without undue reservation" | **No** — request-based, clinical ethics |
| [Oxford-IIIT Pet](https://www.robots.ox.ac.uk/~vgg/data/pets/) | 37 breeds (12 cat), ~200/class, breed + head ROI + trimap | **CC BY-SA 4.0** | **Yes**, ShareAlike viral — **no pose labels** |
| [W&B catz](https://github.com/wandb/catz) | 6,421 six-frame sequences, 96×96, GIPHY-sourced | No dataset licence; third-party sources | **No** |

CatFLW's 48 landmarks derive from Finka et al. 2019, chosen for their relation to facial
musculature and to [CatFACS](https://eprints.lincoln.ac.uk/id/eprint/25941/) action
units. It is the best cat-specific annotation in existence — and it is non-commercial.

### 1b. General animal pose (cat-inclusive)

| Dataset | Content | Cat | Ears / tail | Licence |
|---|---|---|---|---|
| [AP-10K](https://github.com/AlexTheBad/AP-10K) ([arXiv 2108.12617](https://arxiv.org/abs/2108.12617)) | 10,015 imgs, 13,028 instances, 23 families / 54 species, 17 kpts | Felidae | **No ears. 1 tail (root).** | **Ambiguous** — repo says `CC-BY-4.0`; [MMPose zoo](https://mmpose.readthedocs.io/en/latest/dataset_zoo/2d_animal_keypoint.html) lists non-commercial. Unresolved. |
| [APT-36K](https://github.com/pandorgan/APT-36K) | 2,400 clips × 15 frames = 36,000, 30 species, tracking IDs, 17 kpts | unverified | **No ears. 1 tail.** | **MIT** |
| [Animal-Pose](https://sites.google.com/view/animal-pose/) (Cao et al., ICCV 2019) | 4,000+ imgs, 6,000+ instances, 5 categories | **Yes** | **2 earbases + tailbase** | **None stated**; images "from different sources, including Internet". Unclearable. |
| [SuperAnimal-Quadruped](https://huggingface.co/mwmathis/DeepLabCutModelZoo-SuperAnimal-Quadruped) / [Quadruped-80K](https://zenodo.org/records/14016777) | HRNet-w32, 80K quadruped images | broad | richer skeleton | Modified MIT; **models research-only** |
| [DLC multi-animal](https://www.nature.com/articles/s41592-022-01443-0) | 8 categories, video, 20 kpts | **Yes** | **2 ears + 3 tail (base→tip)** | Research context |
| [SMAL / SMALR](https://smal.is.tue.mpg.de/) | 3D articulated animal shape model | big cats | 3D mesh | **Non-commercial research licence** |

**The pattern is exact and inverse: ear/tail annotation ⇄ non-commercial licence.**

### 1c. The dataset that does not exist

There is no public cat behaviour / ethogram video dataset. Nearest analogues:
[DeepEthogram](https://elifesciences.org/articles/63377) (a pipeline, validated on mice
and flies), Animal Kingdom (multi-species, wildlife-weighted), and
[catAction](https://dl.acm.org/doi/10.1145/3702336.3702341) (ACI 2024, kitten
aggression postures — small, narrow).

---

## 2. What the literature supports

### Supported

- **Pain (facial).** The [Feline Grimace Scale](https://www.nature.com/articles/s41598-019-55693-8)
  is well validated: 5 action units (ear position, orbital tightening, muzzle tension,
  whiskers change, head position), inter-rater ICC 0.89, ρ = 0.86 vs UNESP-Botucatu,
  Cronbach's α = 0.89.
- **Automated pain, modest accuracy.** [Feighelstein et al. 2022](https://www.nature.com/articles/s41598-022-13348-1):
  ResNet50 and landmark/CatFACS-geometry both **>72%**.
  [Martvel et al. 2024](https://pmc.ncbi.nlm.nih.gov/articles/PMC11663861/): **66%**
  pain fully-automated vs **73%** with manual landmarks; breed recognition **48%**
  automated. Also [video-based landmark dynamics](https://www.nature.com/articles/s41598-024-78406-2)
  and a [smartphone-applicable FGS model](https://www.nature.com/articles/s41598-023-49031-2).
- **Pose/landmark extraction as a measurement layer.** Mature.

### Not supported

- **Semantic intent decoding.** No peer-reviewed work maps cat visual behaviour to
  meaning. [Scott & Florkiewicz 2024](https://www.nature.com/articles/s41598-024-79216-2)
  catalogued **276 distinct facial signals** in domestic cats, with no established
  semantic mapping.
- **Reliable emotion ground truth.** [Human recognition of feline stress states from
  video](https://www.nature.com/articles/s41598-026-44812-x) varies by observer
  characteristics — the labels themselves are noisy.

**Consequence for any product built on this:** "translation" implies semantic decoding
and is not supportable. Scoring, classification, and change-detection are.

---

## 3. Prior art in products

- **[Official FGS app](https://www.felinegrimacescale.com/)** — free, from the team that
  validated the scale, 550k+ downloads.
- **[Tably](https://www.sylvester.ai/) (Sylvester.ai)** — FGS-based cat photo → mood/pain
  assessment, shipping since 2021, with a veterinary-clinic channel.
- **MeowTalk** — audio, not visual. Claimed ~90% in lab, ~65–75% field, **no
  peer-reviewed validation**; developers concede it "isn't meant to be an exact science."

This is a research community rather than an incumbent moat. A licence-clean open
keypoint dataset with ear and tail topology — which none of them has — is a
contribution to it, not a competitor.

---

## 4. Synthetic data as the resolution

The licence deadlock has a way out that does not involve manual annotation.

- [Unity Perception](https://github.com/Unity-Technologies/com.unity.perception)
  ([paper](https://arxiv.org/pdf/2107.04259)) generates labelled synthetic datasets with
  **keypoint ground truth**, pose/animation randomisation and domain randomisation.
- Ground truth is **exact by construction**, and **keypoint topology is arbitrary** —
  ear tips, ear bases, tail base→tip come free, because the rig defines them.
- Animal precedent: [ZebraPose](https://arxiv.org/pdf/2408.10831) (zebra pose from
  **only** synthetic data), [Prior-Aware Synthetic Data](https://arxiv.org/pdf/2208.13944),
  [Of Mice and Pose](https://arxiv.org/pdf/2307.13361). Domain randomisation measures at
  roughly **2×** the effect of ordinary augmentation.

**The residual risk is the sim-to-real gap, and it is unproven for cats specifically:**
fur occludes ear geometry, tails motion-blur at consumer frame rates, and coat and
deformation variance is far wider than zebra stripe patterns. That is exactly what the
real-environment benchmark is designed to measure.

---

## 5. Model licensing

| Option | Licence | Note |
|---|---|---|
| Ultralytics YOLO(v8/11)-pose | **AGPL-3.0** | Commercial use requires a paid [Enterprise licence](https://www.ultralytics.com/license), cost undisclosed. AGPL otherwise forces the whole product open. |
| MMPose / RTMPose | Apache-2.0 (code) | Code clean; **weights inherit their training data's licence**. |
| MediaPipe / ML Kit | Apache-2.0 | No animal-pose model available. |
| SuperAnimal | modified MIT | **Models research-only.** |

No commercially-licensed cat pose model exists off the shelf. See
[LICENSING-POLICY.md](LICENSING-POLICY.md) for the contamination rules that follow.

---

## 6. On-device deployment

Real-time on-device inference is not the bottleneck.
[react-native-vision-camera](https://react-native-vision-camera.com/docs/guides/frame-processors)
v5 frame processors with
[react-native-executorch](https://docs.swmansion.com/react-native-executorch/docs/next/hooks/computer-vision/visioncamera-integration)
(`runOnFrame`) handle frames natively in 2–5ms with 30–60 FPS inference; ExecuTorch is
on a stable 1.x line. `react-native-fast-tflite` is the TFLite equivalent.

The bottleneck is upstream: there is no model to deploy.
