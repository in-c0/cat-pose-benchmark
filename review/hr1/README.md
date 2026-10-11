# HR1 — independent human review of the prospective holdouts

Status: **package built and pre-registered 2026-10-11; no human labels yet.** Reviewers: none recruited. Nothing in this directory is a human measurement until `submissions/` contains at least two locked Stage A files.

Reviewers should read [REVIEWER-GUIDE.md](REVIEWER-GUIDE.md), not this file. This file is the protocol and the analysis plan, written before any label exists so that the analysis cannot be chosen after seeing the answers.

## Why this gate exists

Every number in technical notes 01–06 was produced against labels written by a model (`claude-809c44f2`). The audit of 2026-10-11 ([AUDIT-2026-10-11.md](AUDIT-2026-10-11.md)) found that:

- no human verdict exists anywhere in the repository, and the one volunteer who offered (issue #79, 2026-09-13) was never answered;
- the existing human templates judge six superseded methods on the development clips, not v3 and not the holdouts;
- on the prospective holdouts, the headline precision (0.69–0.71) depends on overrides the same model annotator made after seeing the method output. Scored as frozen, before those overrides, both holdouts pooled give v3 a precision of 0.57 and a recall of 0.65;
- the holdouts contain six cats with a visible tail. With so few cats, a clip-level 95 % interval on pooled precision runs from roughly 0.1 to 0.9.

HR1 asks two narrow questions, on the only data no decision was taken on:

1. Do independent people agree with each other, and with the model annotator, about whether a tail is visible in each frame?
2. Using the human answers only, what are v1's and v3's precision and recall on unseen video?

It does not measure curve accuracy in pixels, body pose, behaviour, or anything about what a cat feels or intends.

## Data

The 12 clips of holdout #1 and holdout #2 (456 frames at 4 fps, the first ten seconds of each), chosen by the precommitted metadata-only protocol in `review/holdout/`. Frame manifests with a SHA-256 per frame are committed in `package/frames/`. The development clips are excluded: every method choice was made on them.

## Design

**Stage A, blind.** Contact sheets of raw frames with nothing drawn on them (`package/stage_a/sheets/`), in temporal order. Per frame, one of `visible`, `partial`, `not_visible`, `cannot_tell`, for any cat's tail. These are the same distinctions the model truth makes (`review/truth/README.md`), except that the model's identity-confidence field is folded into `cannot_tell`.

**Stage B, method-blind.** One image per distinct reported tail curve from v1 or v3 on the holdout frames. Where both methods report the same curve on a frame it is shown once. Every curve is drawn in one colour (the method overlays colour propagated masks differently, which would reveal the bridge), items are shuffled across clips with seed 20261011, and ids carry no clip or method information. Fifteen items are shown a second time to measure each reviewer's self-consistency. Per item, one of `on_tail`, `not_on_tail`, `cannot_tell`. As built: 160 distinct curves (153 reported identically by v1 and v3, 7 reported only by v3's bridges) plus 15 repeats, 175 images.

**Withholding.** The Stage B images and the key are built now but kept out of the repository (`review/work/hr1/stage_b/`, git-ignored). Their SHA-256 digests are committed in `package/stage_b_commitment.json`, so the item set cannot change after Stage A answers exist. Stage B, the key and the template are published only after every reviewer has locked Stage A. This matters because the only published overlays of holdout frames are the eight columns of note 05's Figure 3 (*Taiwan*, *Larry*, *Déjeuner*, all holdout #1); nothing from holdout #2 has been shown with model output on it. The reviewer guide asks reviewers not to open the notes.

**Locking.** A reviewer locks a stage by posting the SHA-256 of their CSV on issue #79. Files are uploaded only after all reviewers have locked that stage. The intake check refuses a file whose digest does not match the posted one.

## Reviewers

At least two. A reviewer must not be the repository owner, anyone who has seen the holdout overlays or the files under `review/truth/`, or an AI system. Experience with cats is the qualification; annotation experience helps. Each reviewer states on submission which project files they had seen beforehand, and that statement is reported next to their numbers. A reviewer who had seen holdout overlays is still scored and is flagged, not dropped.

## Analysis plan (fixed 2026-10-11)

Implemented in `score.py`; the tests in `test_hr1.py` check each rule on synthetic data.

1. **Validity.** A file with a blank, unknown or duplicate label is rejected and returned to the reviewer. No label is inferred.
2. **Agreement, Stage A.** Labels collapse to positive (`visible`, `partial`), negative (`not_visible`) and `cannot_tell`. Report Krippendorff's alpha (nominal) across all reviewers, Cohen's kappa and raw agreement per pair, and the alpha on the four uncollapsed labels.
3. **Human truth.** A frame is positive or negative only if every reviewer gave that label. Any disagreement, and any `cannot_tell`, makes it `uncertain`, excluded from precision and recall and listed. Disagreements are never resolved toward a reviewer or toward the model.
4. **Agreement, Stage B.** As in 2, after removing the repeated items, which give self-consistency instead. An item is `on_tail` or `not_on_tail` only by unanimity; otherwise its assertion is excluded and listed.
5. **Scoring.** For each method and holdout, and both pooled: TP = positive frame, assertion unanimously `on_tail`; FPv = positive frame, assertion unanimously `not_on_tail`; FN = positive frame, no output; FPn = negative frame, any assertion judged `not_on_tail`; TN = negative frame, no output. An assertion judged `on_tail` on a frame Stage A called negative is a **conflict**, excluded and listed. Precision = TP / (TP + FPv + FPn), recall = TP / (TP + FPv + FN), the definitions in `review/score_truth.py`. Intervals are 95 % clip-level bootstrap, 10 000 resamples, seed 20261011.
6. **Comparison.** Each human number is set next to the model-truth number for the same set, scored as frozen and as adjudicated (`review/truth/methods/aggregate.json`). Every post-inference override on v1/v3 is reported as upheld, overturned or unresolved by the human consensus.

### Decision rules

- **R1 (labels usable).** Stage A alpha ≥ 0.80: reliable. Between 0.667 and 0.80: tentative, and numbers are reported with that word attached. Below 0.667: the task as specified does not produce reproducible labels. No precision or recall is reported, and the next step is to revise the label definitions, not the method. The same bands apply to Stage B.
- **R2 (model annotator).** If the kappa between human consensus and the model truth is ≥ 0.80 on frames both decided, the model truth may continue as a development proxy, labelled as such. Below 0.80, model-annotated truth is retired for any reported number, and notes 05/06 get a correction pointing here.
- **R3 (holdout claim).** The claim "precision on unseen ordinary video is about 0.70" (README, note 05) is **confirmed** if pooled human precision for v3 is within 0.05 of 0.70 and R1 holds. If human precision is closer to the as-frozen value (0.57) than to the adjudicated one (0.70), the adjudicated holdout numbers are withdrawn from the README. Otherwise the claim is reported as **not confirmed** with the human value.
- **R4 (bridge).** The note 05 claim that the v3 bridge's recall gain generalises stands only if human recall for v3 exceeds v1 on the pooled holdouts with no new false run. A tie is reported as a tie. Only 7 items differ between the two methods, so this is reported as counts out of 7, not as a rate.
- **R5 (next step).** If R1 holds, the next experiment is the oracle-ceiling measurement in note 06 §5, which needs human tail-curve truth on fresh clips. HR1 does not supply that truth; it decides whether the cheaper frame-level labels can be trusted while that truth is collected.

## Running the gate (owner checklist)

1. Point reviewers at the guide (issue #79). Record each posted Stage A digest in `submissions/locks.json` as it arrives.
2. When at least two reviewers have locked Stage A, publish Stage B. Rebuild it with `python -m review.hr1.build --skip-stage-a`, check that every digest matches `package/stage_b_commitment.json`, then copy `review/work/hr1/stage_b/items/`, `stage-b-TEMPLATE.csv` and `key.json` into `package/stage_b/` and `review/hr1/key.json`, copy `review/work/hr1/outputs/` to `review/hr1/outputs/`, and commit. If a digest does not match, stop and record why before publishing anything.
3. Ask for the Stage A files, and later the Stage B files, once every reviewer has locked that stage. Add them under `submissions/`.
4. Run `python -m review.hr1.score --output-md review/hr1/results.md --output-json review/hr1/results.json`, apply R1–R5 as written above, and record the outcome on the research ledger (issue #11).

Do not look at any reviewer's labels before step 4, and do not change this file's analysis plan after step 1. If a change turns out to be necessary, add it as a dated amendment below the original and report results both ways.

## What HR1 cannot tell you

- how far a curve is from the true tail centreline, only whether it lies on the tail;
- anything about the development clips, the body pose method or the ear geometry;
- population performance: twelve clips and six cats with a visible tail are a failure-mode census with wide intervals, not an accuracy estimate for cats in general;
- anything about emotion, intention or welfare.

## Reproducing

```bash
python -m review.sample_frames --clip <each holdout clip>      # frames must match package/frames/*.json
python -m review.run_body --device cuda --clip ...
python -m review.run_tail_grounded_v1 --device cuda --clip ...
python -m review.run_tail_grounded_v2 --device cuda --clip ...
python -m review.run_tail_grounded_v3 --device cuda --clip ...
python -m review.hr1.build                                     # sheets, template, outputs/, Stage B digests
python -m review.hr1.score --output-md review/hr1/results.md --output-json review/hr1/results.json
```

`outputs/` (published with Stage B, digests committed now) holds the per-frame status, box and reported curve of v1 and v3 on every holdout frame, exported from the reproduced runs, because the original `result.json` files were never committed.
