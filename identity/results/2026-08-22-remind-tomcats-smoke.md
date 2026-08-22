# ID1.1 REMIND feline smoke — Tomcats conflict

**Date:** 2026-08-22  
**Status:** integration smoke PASS; quantitative feline ReID performance **not evaluated**  
**Issue:** #70  
**PR:** #71

## Purpose

Execute the frozen upstream REMIND baseline on real feline video without changing its ReID algorithm or feature backbone.

This is a non-quantitative integration smoke. The source clip does not carry independent persistent physical-cat identity masks, so this run must not be reported as IDF1, tracking accuracy, or broad feline ReID performance.

## Frozen components

- REMIND: `cvar-vision-dl/remind-reid-tracker@f88ea1d5d81da0a8ed28b206df6d4dab48327342`
- DINOv3-S: upstream REMIND default `facebook/dinov3-vits16-pretrain-lvd1689m`
- detector: Ultralytics `yolo11n-seg.pt`, COCO cat class 15
- source: Wikimedia Commons `Tomcats conflict.webm`, CC0-1.0
- sampling: 1 fps, first 15 processed samples
- runtime: GitHub-hosted Linux runner, Python 3.10.21, CPU

Source/model hashes from the successful artifact:

- Tomcats source SHA-256: `79ea8a60c5aee25438ee70c2fff192ba953e89d29219c3d6ce5ed8e10e2078cf`
- YOLO weights SHA-256: `55ed65c56c91713d23e8402371c6c49a6fd84f257f7dce452e8d70e41dcbe152`
- successful artifact SHA-256: `a3593615189dafb47754eea16d264bdf39b7d601e5546ea30781c4d46d4bbfed`
- Actions run: `32535415030`, rerun job `96948692151`

## Integration blockers found on the way

### 1. Upstream runtime dependency omission

The pinned REMIND revision imports `pandas` through its association/debug path, while its `environment.yml` does not declare pandas.

The smoke runner supplies `pandas` as an environment dependency only. No REMIND source file or association algorithm was modified.

### 2. Gated DINOv3 access

Without an authenticated Hugging Face token with accepted DINOv3 access, model initialisation failed with a 401 gated-repository error for `facebook/dinov3-vits16-pretrain-lvd1689m`.

After repository secret `HF_TOKEN` was configured under an account with DINOv3 access, the exact same pinned smoke completed successfully. The successful provenance packet records `hf_token_present=true` without exposing the token.

## Successful run

REMIND processed all 15 requested samples.

Runtime summary:

- processed frames: **15**
- total wall time reported by REMIND: **8.4753 s**
- average reported throughput: **1.7698 fps** on CPU
- total detector observations: **21**
- identities created: **2**, both on the first sample
- subsequent matches: **19**
- ambiguous decisions: **0**
- provisional decisions: **0**
- new identities after frame 0: **0**

Detector availability by sampled frame:

- 2 detected cats: **7/15** frames
- 1 detected cat: **7/15** frames
- 0 detected cats: **1/15** frames

Identity observation counts:

- ID 0: **7** observations at t = 0, 1, 2, 5, 7, 9, 11 s
- ID 1: **14** observations at t = 0–11 s except none missing before 12 s, then t = 13, 14 s after a complete detector gap at t = 12 s

## Visual QA

All 15 rendered samples were reviewed after execution.

Observed engineering behaviour:

- ID 0 stays attached to the left brown/tabby cat whenever YOLO supplies that cat as a detection;
- ID 1 stays attached to the right grey cat whenever YOLO supplies that cat as a detection;
- no visible identity swap occurs on samples where both cats are detected;
- the detector produces no cats at t = 12 s even though both physical cats are visibly present;
- when the right grey cat is detected again at t = 13 s, REMIND restores **ID 1** rather than creating a third identity;
- the left cat is not available to the association layer at t = 13–14 s because YOLO does not detect it.

This is sufficient to establish that persistent REMIND identity state executes coherently on real feline video, including one short complete detector gap. It is **not** sufficient to estimate feline identity accuracy.

## Main finding

For this smoke, the immediate limitation is the **proposal/detection layer**, not an observed REMIND identity-memory collapse.

Generic YOLO11n segmentation misses the left cat on 8/15 samples and misses both cats on one sample. REMIND cannot associate an animal that the detector does not propose.

This makes a quantitative DAVIS-style experiment especially important: using independently annotated per-frame instance masks will let ID1 measure REMIND's association/re-identification quality separately from detector recall.

## Relationship to the legacy baseline

The older frozen RGB-histogram identity experiment on this same CC0 clip used SuperAnimal candidate proposals and visually retained the target on 45/45 sampled frames. That result remains an engineering comparator only; its deterministic target definition and post-run visual review are not independent persistent identity ground truth.

The two experiments therefore expose different components:

- legacy pipeline: stronger proposal availability on this easy clip + simple explicit appearance assignment;
- REMIND smoke: generic YOLO proposal bottleneck + persistent DINOv3 memory/association operating successfully when detections are available.

They should not be compared as headline accuracy numbers.

## Claims boundary

Supported:

`REMIND @ frozen commit can execute end-to-end on real feline video and preserve two coherent persistent IDs across the observed detections in this 15-sample smoke.`

Not supported:

- feline IDF1 or tracking accuracy;
- robustness to look-alike cats;
- long disappearance/re-entry;
- crossing/close-contact identity accuracy;
- population-level feline ReID performance;
- intent, affect, translation, health, or welfare inference.

## Next empirical gate

Build or obtain a provenance-valid feline sequence with independently verified persistent physical-cat identity and DAVIS-compatible instance masks, assign ID1 stress strata before scoring, then run the pinned REMIND quantitative evaluator and pass `summary_global.csv` through `identity.remind_adapter` unchanged.
