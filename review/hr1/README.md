# HR1 — independent human review of the prospective holdouts

Status: **package built and pre-registered 2026-10-11; no human labels yet.** Reviewers: none confirmed. The one earlier volunteer (issue #79) offered to review 57 frames and has been asked whether they want to take on this larger review. Nothing in this directory is a human measurement until `submissions/` contains at least two locked Stage A files.

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

**Stage B, method-blind.** One image per distinct reported tail curve from v1 or v3 on the holdout frames. Where both methods report the same curve on a frame it is shown once. Every curve is drawn in one colour (the method overlays colour propagated masks differently, which would reveal the bridge), items are shuffled across clips by a secret salt (see Withholding), and ids carry no clip or method information. Fifteen items are shown a second time to measure each reviewer's self-consistency. Per item, one of `on_tail`, `not_on_tail`, `cannot_tell`. As built: 160 distinct curves (153 reported identically by v1 and v3, 7 reported only by v3's bridges) plus 15 repeats, 175 images.

**Withholding.** Everything is built now and kept out of the repository under `review/work/hr1/` (git-ignored). It is released in two steps:

| what | where it lives until release | released when |
|---|---|---|
| Stage B images and blank template | `review/work/hr1/stage_b/items/`, `stage-b-TEMPLATE.csv` | every reviewer has locked Stage A (at least two) |
| the key: which clip, frame and method each item came from, and which items are repeats | `review/work/hr1/stage_b/key.json` | every reviewer has locked Stage B |
| per-method outputs (status, box and curve of v1 and v3 on every holdout frame) | `review/work/hr1/outputs/` | every reviewer has locked Stage B |
| the manifest of digests, including the shuffle salt | `review/work/hr1/stage_b_manifest.json`, `SECRET-salt.txt` | every reviewer has locked Stage B |
| results | not computed | after the above |

The item order comes from a 256-bit random salt, not from a seed in the code. With a public seed, anyone who re-ran the public pipeline could rebuild the key from `build.py`; with the salt they cannot. The repository holds only `package/stage_b_commitment.json`: the item counts and `root_sha256`, the SHA-256 of the canonical manifest. Because the manifest contains the salt, the root says nothing about any item, but once the manifest is published anyone can check that no image, key entry or output changed after this commit (`python -m review.hr1.withholding --verify-release`). `review/hr1/withholding.py` checks the tracked tree against this table, and the tests run it in CI. When the private build is present, it also scans every tracked text file for the salt and for each item's curve key, so a value pasted into a note or CSV is caught.

The first build of this PR used the public seed 20261011 and committed one digest per image. It was replaced before merge: the items are the same 160 curves and 15 repeats, but the order was redrawn with the salt, so the old per-image digests no longer correspond to any item id. This matters because the only published overlays of holdout frames are the eight columns of note 05's Figure 3 (*Taiwan*, *Larry*, *Déjeuner*, all holdout #1); nothing from holdout #2 has been shown with model output on it. The reviewer guide asks reviewers not to open the notes.

**Locking.** A reviewer locks a stage by posting the SHA-256 of their CSV on issue #79. Files are uploaded only after all reviewers have locked that stage. The intake check refuses a file whose digest does not match the posted one.

**What the public repository still shows.** The withholding covers the new material. It cannot cover files published before HR1 existed. The model annotator's frame labels for the holdouts (`review/truth/holdout_frames.csv`, `holdout2_frames.csv`), its per-method verdicts on each holdout frame (`review/truth/methods/*+holdout*.csv`) and note 05's Figure 3 have been public since PRs #87–#89 and stay in the git history. A reviewer who matched a Stage B image to its frame by eye and then opened those files could see what the model annotator said about that frame and whether v1 also reported a curve there. The guide asks reviewers not to open them, and each reviewer states what they had seen. Nothing in the repository can enforce that, and results are reported with each reviewer's statement next to them.

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
2. When every reviewer (at least two) has locked Stage A, ask for the Stage A files and add them under `submissions/stage_a/`.
3. Release the Stage B **images and template only**: copy `review/work/hr1/stage_b/items/` and `stage-b-TEMPLATE.csv` into `package/stage_b/`, check each image against the private manifest, run `python -m review.hr1.withholding`, and commit. Do not copy `key.json`, `outputs/`, the manifest or the salt.
4. Record each posted Stage B digest in `locks.json`. When every reviewer who locked Stage A has also locked Stage B, ask for the Stage B files and add them under `submissions/stage_b/`.
5. Only now publish the key and the outputs: copy `review/work/hr1/stage_b/key.json` to `review/hr1/key.json`, `review/work/hr1/outputs/` to `review/hr1/outputs/`, and `review/work/hr1/stage_b_manifest.json` to `review/hr1/stage_b_manifest.json`. Run `python -m review.hr1.withholding --verify-release`. If it reports a mismatch, stop and record why before scoring.
6. Run `python -m review.hr1.score --output-md review/hr1/results.md --output-json review/hr1/results.json`, apply R1–R5 as written above, and record the outcome on the research ledger (issue #11).

Keep a private backup of `review/work/hr1/` (salt, manifest, key, outputs, items). If the salt is lost, the commitment cannot be checked and Stage B has to be rebuilt and committed again before release.

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
python -m review.hr1.build                                     # sheets, template; private outputs/, Stage B, manifest; root digest
python -m review.hr1.score --output-md review/hr1/results.md --output-json review/hr1/results.json
```

`outputs/` (published after every reviewer has locked Stage B; covered by the committed root now) holds the per-frame status, box and reported curve of v1 and v3 on every holdout frame, exported from the reproduced runs, because the original `result.json` files were never committed.
