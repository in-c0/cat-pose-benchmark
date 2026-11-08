# BH1: can observable cat behaviour be recognised from video on cats the model has never seen?

Status: **protocol frozen 2026-10-17, before any label exists.** No clip has been selected, no labeller recruited, nothing labelled, nothing scored. The frozen text is everything above the heading "Amendments"; `protocol_freeze.json` holds its SHA-256, and the tests fail if it changes. A later change goes below that heading, dated, and results are then reported both ways.

BH1 is a feasibility study that sits outside benchmark v0. `docs/OPEN-DECISIONS.md` rules out behaviour claims for benchmark v0, so nothing measured here becomes a benchmark number, and nothing in the benchmark depends on it. The question comes from the "Cat Translator" plan: before anything is built on the idea that a camera can tell what a cat is doing, check that a model can name plain, visible actions on cats it was not trained on. The background is in `_hub/reviews/2026-10-11-cat-translator-behaviour-feasibility.md` (owner's hub, outside this repository).

Three things are pending the owner's ruling (exception `2026-10-11-cat-pose-behaviour-feasibility-df26`): whether BH1 runs at all, who the two labellers are, and which clips may be used (CC BY-SA, and how many clips one uploader may contribute). This protocol is written so that none of those rulings changes the analysis. They change only which clips go in.

## 1. What BH1 asks, and what it does not

BH1 asks one question. Using labels written by at least two independent people, does a method recognise five observable behaviours on **cats it has never seen**, better than chance? It also asks how much worse the method does on unseen cats than on cats it has seen.

That second question is there because this project has already failed that way once. In the audio experiment of 2026-08, context classification held out one cat at a time and scored a log loss of 1.070 against a prior-only 1.066, and the sound clusters followed the individual cat (ARI 0.946) rather than the context (AMI 0.005). A model that learns "this cat tends to do that" can look accurate on cats it has seen and know nothing transferable.

BH1 does **not** label or measure emotion, intention, pain, welfare, health, or what a behaviour "means". There is no label for "happy", "anxious", "hunting", "wants attention" or anything similar, and the note column on the label sheet is never analysed. The classes describe what the body is doing, as someone would describe it with the sound off.

No model-generated behaviour label is used as truth, as a tie-breaker, or as a training target. Every truth label comes from a person.

## 2. Behaviour classes

Each 2-second segment gets one label for the **target cat** (section 3). There are five classes and `cannot_tell`.

| label | in one line |
|---|---|
| `walk` | moving across the ground by stepping |
| `sit_lie` | staying in place, not walking, grooming, jumping or playing |
| `groom` | cleaning or scratching its own body |
| `jump` | all four feet leaving the ground by the cat's own push |
| `play_other` | any other visible activity |
| `cannot_tell` | you cannot decide from what is shown |

### Definitions

**`walk`**: the cat moves its body from one place to another by stepping, at any speed. Walking, trotting, running, stalking low to the ground and climbing stairs all count. Turning on the spot with a step or two does not count; that is `sit_lie` if nothing else is going on.

**`sit_lie`**: the cat stays in one place. It may be sitting, lying, crouching, loafing, or standing still. It may move its head, ears, tail or eyes, blink, look around, or shift its weight without stepping away. Standing still is included here on purpose: the distinction this study cares about is moving versus staying, and "standing" is too brief and too hard to separate from "about to sit" to be its own class.

**`groom`**: the cat licks or nibbles its own fur, wipes its face with a paw it has licked, or scratches its own body with a hind foot. Being groomed by another cat, or licking another cat, is `play_other`.

**`jump`**: the cat pushes off so that all four feet leave the ground, including leaping up onto furniture, down from it, across a gap, or straight up at a toy. A fall or a slip is not a jump. A cat lifted by a person is not a jump.

**`play_other`**: anything visible that is not one of the four above. This includes playing with a toy, an object, a person's hand or another animal; pouncing without leaving the ground; eating; drinking; sniffing at something while stationary; kneading; scratching furniture; digging; being picked up, held or stroked; fighting. This class is deliberately broad, so it is not a measure of "play".

**`cannot_tell`**: use it when any of these is true:

- the target cat is visible for less than half of the segment;
- the picture is too dark, blurred, small or cut off to see what the body is doing;
- you are not sure which cat is the target;
- no single class covers more than half of the segment (see below);
- you have looked carefully and still cannot choose.

`cannot_tell` is a real answer and costs nothing. Guessing is worse than saying you cannot tell, because a guess becomes a disagreement and the segment is lost anyway.

### When more than one thing happens in a segment

1. **A jump wins.** If the take-off or the landing of a jump is inside the segment, the label is `jump`, even though a jump lasts well under a second.
2. **Otherwise, the longest activity wins if it covers more than half the segment.** A cat that walks for 1.5 s and sits for 0.5 s is `walk`.
3. **If nothing covers more than half**, the label is `cannot_tell`.

### Boundary cases, decided in advance

| what you see | label | why |
|---|---|---|
| Cat stands still, then takes one step to turn round | `sit_lie` | one or two steps on the spot are not moving across the ground |
| Cat creeps forward low to the ground | `walk` | stepping across the ground, whatever the posture |
| Cat licks a paw once, then looks around for the rest of the segment | `sit_lie` | grooming does not cover more than half |
| Cat scratches its neck with a hind foot | `groom` | scratching its own body is self-grooming here |
| Cat scratches a post or a sofa | `play_other` | not its own body |
| Cat swats at a toy without leaving the ground | `play_other` | |
| Cat leaps at a toy and lands inside the segment | `jump` | rule 1 |
| Cat is mid-air in the first frame and lands in the third | `jump` | the landing is inside the segment |
| Cat sits while a person strokes it | `play_other` | being handled is "other", even if the cat is still |
| Cat is carried by a person | `play_other` | |
| Cat eats or drinks | `play_other` | |
| Cat rolls over on its back, staying in place | `sit_lie` | changing posture in place, no stepping |
| Cat rolls on its back while batting at a hand | `play_other` | |
| Two cats; the target sits while the other plays | `sit_lie` | only the target counts |
| Target cat leaves the frame halfway | `cannot_tell` unless it was visible doing one thing for more than half | |
| Old film, cartoonish speed-up, or obvious editing within the segment | label what you see; mention it in the note | the footage filter (section 4) should have caught most of these |

## 3. Labelling unit

The unit is a **segment**: a fixed 2-second window of one clip, cut from 0 s, 2 s, 4 s and so on, up to the first 20 seconds. A trailing piece shorter than 2 s is dropped. Clips are at least 4 s long, so each clip gives between 2 and 10 segments. Cutting at fixed times, not at behaviour boundaries, keeps the unit independent of any judgement about the behaviour.

Each labeller receives, per clip:

- a **sheet**: one row per segment, eight frames per row at 4 frames per second, in time order, with nothing drawn on them. The header names the clip by an opaque id and describes the target cat in words, such as "the grey tabby on the left";
- a **silent 2-second video** of each segment, so movement can be seen as well as inferred.

The target cat is chosen by the identity checker (section 5), who writes the description that appears on the sheet. In a clip with one cat, the description is just its appearance.

## 4. Clip pool and selection

**Pool** (done; `pool/pool.json`, `pool/draw.json`). Every file in Wikimedia Commons `Category:Videos of cats` and its subcategories to depth 2, listed through the API on 2026-10-17 at 12:20 UTC. Subcategories were walked breadth-first, so a category reachable by two routes counts at its shallowest depth. This gave 38 categories and 498 files, 374 of them videos. No video was opened to build the pool.

**Eligibility** is the prospective holdout's rule, unchanged (`review/holdout/sample_pool.py`): video, at least 4 s long, at least 360 px high, not one of the four development clips, and title and description free of the frozen "not ordinary footage" keyword list. The licence rule is also the holdout's: CC0, CC BY or public domain. CC BY-SA clips are classified and recorded with their own eligibility verdict (`eligible_if_by_sa`), but the selection cannot take them unless the owner allows it, because share-alike would then bind the derived labels.

| | clips | uploaders | of which the largest uploader (Sporti) |
|---|---|---|---|
| eligible (CC0 / CC BY / PD) | 248 | 35 | 189 |
| eligible if CC BY-SA were allowed | 352 | 62 | 189 |

These counts differ slightly from the 2026-10-11 feasibility count (254 clips, 39 uploaders), which did not apply the development-clip and footage filters.

**Order.** Sort all 498 canonical titles and shuffle them with seed **20261017** (`pool/draw.json`, `shuffled_order`). This order is frozen and is the only order any selection may use.

**Selection rule.** Walk the frozen order and take each eligible clip, unless its uploader already has `cap` clips. The cap and the BY-SA switch are the owner's rulings, so no selection exists yet. What each candidate ruling would give:

| cap per uploader | without BY-SA | with BY-SA |
|---|---|---|
| 1 | 35 clips | 62 clips |
| 3 | 51 | 97 |
| 5 | 57 | 111 |
| 10 | 68 | 134 |
| 20 | 79 | 155 |
| none | 248 (189 from one uploader) | 352 |

Reaching 100 clips needs a cap of at least 41 without BY-SA (Sporti then supplies 41 of 100), or a cap of 4 with BY-SA (105 clips). Once ruled, `python -m behaviour.sample_pool select --cap <n> [--include-by-sa] --ruling <reference>` writes `pool/selection.json` from the frozen order with no refetch.

**Replacement.** A selected clip is replaced by the next eligible clip in the frozen order, under the same cap, only if the identity checker finds before packaging that it shows no real cat, is not real footage, cannot be decoded, or never shows the target cat clearly. A clip is never replaced for being boring, hard, ambiguous or unbalanced in behaviour. Every replacement is listed with its reason.

## 5. Cat identity

Different uploaders do not guarantee different cats, and one uploader may film several cats. Before labelling, one person, the **identity checker**, watches every selected clip on Commons and fills a private file, `work/identity.csv`, with:

- `cat_id`: the same value for clips that show the same individual;
- `n_cats_visible` and `target_description`, which choose the target cat for clips with more than one cat;
- `identity_confidence`: `sure`, `likely` or `unsure`;
- their name.

When the checker cannot tell whether two clips show the same cat, they give both clips the **same** `cat_id`. Merging makes the unseen-cat test stricter. Splitting would let one cat appear on both sides of a split.

The identity checker sees Commons titles, which often name the behaviour, so they may not also be a behaviour labeller. They do not need the analysis plan. They may be the owner, since `cat_id` is not a behaviour label. They may not be an AI system.

The identity file stays private until labelling is locked. Its digest is part of the committed manifest (section 6), so the cat grouping cannot be changed after anyone has seen a label. The scorer refuses to run while any `cat_id` is blank. `pool/pool.json` carries `cat_id: null` for every clip until the release, when the filled values are published.

## 6. Blinding, locking and withholding

Commons titles name behaviours ("Cat behaviour - self-grooming", "Cat jumping backwards"). A labeller who can see a clip's title has been told the answer. So labellers see clips only under opaque ids (`BH1-C001`, ...), in an order drawn from a private 256-bit salt rather than a public seed. With a public seed, anyone could rebuild the mapping from the public code.

This reuses the HR1 machinery (`review/hr1/README.md`, "Withholding" and "Locking"):

| what | where until release | released when |
|---|---|---|
| sheets and segment videos | `work/package/`, sent to labellers directly (too large for git); digests in `package/media.json` | at the start, to registered labellers |
| label template, opaque ids only | `package/label-TEMPLATE.csv` (committed) | at the start |
| the key: opaque id → Commons title, uploader, `cat_id`, target description | `work/key.json` | every registered labeller has locked |
| identity pass | `work/identity.csv` | every registered labeller has locked |
| manifest of digests, including the salt | `work/manifest.json`, `work/SECRET-salt.txt` | every registered labeller has locked |
| baseline predictions, results | not computed | after the above |

The repository holds `package/commitment.json` before release: counts and `root_sha256`, the SHA-256 of the canonical manifest. Because the manifest contains the salt, the root reveals nothing about the mapping. After release, `python -m behaviour.withholding --verify-release` shows that the key and template are the ones committed to.

**Labellers** are registered by handle in `submissions/labellers.json` before the package is sent. At least two. A labeller must not be the repository owner, the identity checker, anyone who has seen `work/`, or an AI system. They may be the same people as the HR1 reviewers. Each says on submission which project files and Commons pages they had seen, and that statement is reported next to their numbers.

**Locking.** A labeller locks by posting the SHA-256 of their completed CSV on the project's review issue before sending the file. `submissions/locks.json` records each posted digest, and the scorer refuses any file whose digest does not match. A correction is a new file, `labels-<handle>-r2.csv`, with its own posted digest. The latest revision is scored and both are kept.

`python -m behaviour.withholding` checks the tracked tree against the table above, and the tests run it in CI. When the private build exists locally, it also scans every tracked text file for the salt and for any opaque id written next to its Commons title.

Nothing can stop a determined labeller from finding a clip on Commons by its frames. The guide asks them not to search, and the statement above records what they saw.

## 7. Analysis plan

Implemented in `score.py` and `baselines.py`. The tests in `test_bh1.py` check each rule on synthetic data.

### 7.1 Validity

A file with a blank, unknown or duplicate label, a missing template row, or a row not in the template is rejected whole and returned to the labeller. No label is inferred.

### 7.2 Agreement

- Krippendorff's alpha (nominal) across all labellers, computed twice: over all six labels, and over the five classes with `cannot_tell` treated as missing. The **gate value is the lower of the two**. The first can be inflated by labellers agreeing on `cannot_tell`; the second by a labeller who answers `cannot_tell` whenever a segment is hard.
- Cohen's kappa and raw agreement for every pair.
- Per-class alpha, one class against the rest, `cannot_tell` as missing.
- Each labeller's `cannot_tell` rate.

### 7.3 Human truth

A segment's truth is a class only if every labeller gave that class. Any disagreement makes it `uncertain`. Unanimous `cannot_tell` stays `cannot_tell`. Both are excluded from training and testing and are listed. A disagreement is never resolved toward one labeller, a majority, or a model.

### 7.4 Methods and cross-validation

Two baselines, fixed now:

- **`majority`** predicts the most frequent class of the training folds. It is the "baseline" the Cat Translator plan asks for, and its gain is reported, but section 7.5 explains why decisions are not taken against it.
- **`motion_lr`** computes 22 motion-energy features per segment from frame differences of the 8 frames, downscaled to 64 px wide: energy statistics, moving-area fraction, the path of the motion centroid, and the share of motion in each cell of a 3 × 3 grid. It then fits standardised multinomial logistic regression with C = 1.0, balanced class weights and no tuning. It sees no pose, no detector and no model output.

`motion_lr` is the bar for any pose-based method. A pose method that does not beat it has not shown that pose adds anything beyond raw motion.

Every method is run in two regimes, each with five group folds (`sklearn.model_selection.GroupKFold`, fewer if there are fewer groups):

- **`clip_disjoint`**: folds grouped by clip. A test cat may appear in training through another of its clips. This is the "seen cat" regime.
- **`cat_disjoint`**: folds grouped by `cat_id`. Every test cat is unseen.

Only segments with a class as truth enter the folds. Predictions are out-of-fold, one per decided segment. A candidate method supplies `predictions/<method>--<regime>.csv` in the same format, using the same folds. It may be pretrained on outside data that contains no BH1 clip, and it may not be trained on any model-generated behaviour labels for BH1 clips.

### 7.5 Metrics

The **decision metric is balanced accuracy**, the mean recall over the classes present in the truth. A predictor whose output does not depend on the video has an expected balanced accuracy of 1/(number of classes present), 0.2 with all five, whatever mix of labels it outputs. That number is the **chance level**, and the decisions in section 8 are taken against it.

Two earlier drafts of this protocol decided against the majority baseline instead. Both failed on synthetic data before the freeze, and the tests that caught them stay in `test_bh1.py`:

- Macro-F1 gain over majority. On labels that were pure noise, `motion_lr` passed with a 95 % interval above zero, because a predictor that spreads its guesses across classes scores about twice the majority baseline's macro-F1 by chance.
- Balanced-accuracy gain over majority. Under grouped cross-validation the majority baseline falls **below** chance, because each fold's training majority is the class that fold's test data has least of. In the synthetic world where each cat has its own habit and its own way of moving, the baseline scored 0.03 against a chance level of 0.2, and `motion_lr` "beat" it with an interval above zero while being at chance itself.

The gain over the majority baseline is still reported, as the plan asks, with this caveat. Macro-F1 is reported as well, without being decided on.

Also reported for every method and regime: per-class precision, recall and F1; per-class **F1 excess over chance**, which is F1 minus 2pq/(p + q), the expected F1 of an uninformed predictor with the same prediction rate q for a class of prevalence p; and the fraction of `clip_disjoint` test segments whose cat appears in that fold's training data.

### 7.6 Intervals

All intervals are 95 % percentile intervals from a **cat-level bootstrap**: resample cats with replacement, take all of each drawn cat's decided segments, and recompute from the fixed out-of-fold predictions (no refit). There are 10 000 resamples with seed 20261017. The same resamples are used for every method and regime, so gains and drops are paired differences with their own intervals.

### 7.7 Abstention

Two kinds are reported. **Human:** the fraction of segments whose truth is `uncertain` or `cannot_tell`, and each labeller's `cannot_tell` rate. **Model:** `motion_lr` abstains when its top class probability is below 0.5. Coverage is the share of decided segments it answers. Balanced accuracy on answered segments is reported only when coverage is at least 0.5. All decisions in section 8 use forced-choice predictions.

### 7.8 Sensitivity, reported and not decided on

- Balanced accuracy with the largest uploader's clips removed (predictions as made, no refit).
- Results restricted to clips whose `identity_confidence` is `sure`.

## 8. Decision rules

Applied mechanically by `score.decide()`; nothing in it is tuned.

- **R0 (preconditions).** At least 2 locked labellers, at least 10 distinct `cat_id`s and at least 100 clips with at least one decided segment. If any fails, BH1 reports agreement and counts only, and every later rule reads "not assessed".
- **R1 (labels usable).** Gate alpha ≥ 0.80: reliable. Between 0.667 and 0.80: tentative, and every result carries that word. Below 0.667: the five classes as written do not give reproducible labels. No method result is reported, and the next step is to revise section 2, not a method. Classes whose per-class alpha is below 0.667 are listed, and their per-class results are marked as resting on unreliable labels.
- **R2 (recognition on unseen cats).** A method recognises observable behaviour on unseen cats if its `cat_disjoint` balanced accuracy minus the chance level (section 7.5) has a 95 % interval entirely above 0.
- **R3 (beyond motion).** A candidate method adds something beyond raw motion if its `cat_disjoint` balanced accuracy minus `motion_lr`'s has a 95 % interval entirely above 0.
- **R4 (seen to unseen).** A method is **identity-dependent** if its `clip_disjoint` minus `cat_disjoint` balanced accuracy is at least 0.10 and its interval lies entirely above 0. R4 is assessed only if at least half of the `clip_disjoint` test segments have their cat in training; otherwise the "seen" regime is not seen enough to compare, and that is reported.
- **R5 (per class).** A class is recognised on unseen cats if its `cat_disjoint` F1 excess over chance has a 95 % interval entirely above 0.
- **R6 (abstention).** If more than 40 % of segments end `uncertain` or `cannot_tell`, the result is flagged as resting on the easy segments only.

**Outcome**, for the assumption "visual movement supports behaviour classification across cats":

| condition | outcome |
|---|---|
| R0 fails | not run; counts reported |
| R0 holds, R1 unreliable | labels unreliable: revise the definitions |
| R1 holds, no method passes R2 | **kill at this scale**: nothing beats chance on unseen cats |
| a method passes R2 and is identity-dependent (R4) | **pivot**: recognition exists but leans on knowing the cat; per-cat calibration or behaviour tracking, not general recognition |
| a method passes R2 and is not identity-dependent | **continue** |

"At this scale" matters. With 10-20 cats, the intervals will be wide. Tail v3's per-cat recall on the holdouts ran from 0.00 to 1.00 with six cats. A "not shown" from BH1 means not shown with this many cats; it does not mean disproved.

## 9. What BH1 cannot tell you

- anything about emotion, intention, pain, welfare or health;
- performance on owners' home video, which may differ from Commons footage in angle, light, length and what people choose to film;
- performance on behaviours outside the five classes, or on finer distinctions inside them, such as play versus hunting;
- population accuracy: with tens of cats and a few hundred segments, BH1 is a feasibility check with wide intervals, not an accuracy estimate for cats in general.

## Amendments

None.
