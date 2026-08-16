# Identity assignment v0 — explicit LOST state prevents the measured cat switch

Status: **architecture feasibility passed on the original regression window; held-out ReID validation still required**

## Why this experiment exists

Two simpler temporal hypotheses failed on the same `Cat jumping backwards` sequence:

1. a local SAM2 tail object switches semantic target after occlusion / a second salient cat;
2. a clean whole-animal SAM2 object also switches from the intended grey cat to the second cat at frame 9.

The whole-animal failure showed that a segmentation object slot is not a persistent feline identity.

The next minimum architecture is therefore:

```text
multiple animal proposals
+ target appearance evidence
→ explicit assignment
→ TARGET / LOST / RE-ACQUIRED
```

The key rule is:

> **When no candidate matches the target, output LOST. Never select the best available animal merely because one exists.**

## Source / regression window

Source:
- Wikimedia Commons `Cat jumping backwards.webm`;
- CC-BY-3.0;
- first 8 s sampled at 1.5 fps.

This experiment isolates source frames 8–11, the exact window where single-object SAM2 switched cats.

Reference target:
- grey cat seeded at source frame 5 (~3.333 s);
- reference region derived mechanically from the frozen R3 SuperAnimal whole-body points;
- seed fixture: `temporal/fixtures/superanimal-grey-cat-identity-seed-frame5.json`.

All SuperAnimal detections and the target seed remain R3 research-only evidence.

## Step 1 — ask for multiple animal hypotheses

SuperAnimal-Quadruped was rerun with:
- `hrnet_w32` top-down pose model;
- `fasterrcnn_resnet50_fpn_v2` detector;
- `max_individuals=2`;
- CPU;
- confidence threshold 0.2.

First real probe:
- run `31918837072`;
- artifact `9255742345`;
- digest `sha256:009ef35ad045326b8491d1f4f7368af1bf8d8c655750745e20f761f229f31903`.

Candidate counts:

| Source frame | Candidate count | Visual interpretation |
|---|---:|---|
| 8 | 0 | detector misses the target |
| 9 | 1 | grey target cat |
| 10 | 1 | black/white distractor only; grey target is blurred at left |
| 11 | 2 | foreground black/white cat + grey target cat |

This is an important partial result:

- the detector does **not** give a usable target candidate every frame;
- but by frame 11 it exposes both animals, so explicit re-acquisition is possible;
- detector `individual` names are candidate slots, not trusted identities.

Frame 10 is the critical case: any policy that always chooses the only/highest-confidence candidate will necessarily switch cats.

## Step 2 — conservative appearance assignment

Second run:
- run `31919062223`;
- artifact `9255800604`;
- digest `sha256:4a9785e303ffad45f12bfb1fc924c69946aaf233c713229710d245bba4f6c0c8`.

Descriptor:
- RGB 8×8×8 histogram;
- target reference crop = bounding box of the frozen frame-5 body points with 5% padding;
- candidate crop = pose-derived high-confidence candidate bbox;
- distance = Jensen-Shannon divergence in bits.

Exploratory gate:
- accept target candidate only when `JSD <= 0.30`;
- otherwise output `LOST`.

**Important:** `0.30` is calibrated on this same regression sequence after observing the correct/wrong candidate separation. It is not a universal feline ReID threshold and is not used to claim held-out accuracy.

### Decisions

| Source frame | Proposals | Appearance JSD | Decision |
|---|---|---|---|
| 8 | none | — | `LOST` |
| 9 | grey cat only | **0.2155** | `RE-ACQUIRED → TARGET` |
| 10 | black/white cat only | **0.3686** | **reject → LOST** |
| 11 | grey + black/white | grey **0.2616**, black/white **0.4583** | **choose grey → RE-ACQUIRED** |

Pose confidence does not control identity:

- frame 10 wrong cat mean keypoint score: ~**0.570** — rejected;
- frame 11 foreground wrong cat mean score: ~**0.460**;
- frame 11 grey target mean score: ~**0.389** — selected because appearance matches the target better.

This is the behavior the prior pipelines were missing.

## Visual QA

Visual review confirms:

- frame 9 selected candidate is the blurred grey target cat;
- frame 10 the only proposal is the black/white cat while the intended grey cat is blurred at the left edge; the assignment correctly emits `LOST` rather than switching;
- frame 11 two proposals are present; the assignment selects the smaller grey cat at the upper-left/chair region and rejects the larger foreground black/white cat.

Thus on this regression clip the state machine avoids the known silent identity switch.

## Decision

### Architecture retained

Do **not** escalate to a large temporal transformer yet.

The first evidence-backed temporal identity decomposition is:

```text
frame
→ multiple animal proposals
→ target assignment gate
   ├─ appearance similarity
   ├─ later: geometry / motion / scale as supporting terms
   └─ pose confidence only as secondary evidence
→ TARGET / LOST / RE-ACQUIRED
→ bind local ear/tail detail only to the selected target
```

The explicit `LOST` state is not a fallback bug; it is a required safety property when the proposal layer does not expose the target.

### What remains unsolved

This experiment establishes **architecture feasibility**, not general identity accuracy.

Remaining work:

1. validate assignment on held-out multi-cat clips not used to choose the threshold;
2. replace raw RGB crop histograms with a more robust, licence-clean appearance descriptor if required;
3. improve the proposal layer for motion blur / partial occlusion, since frame 10 does not expose the grey target at all;
4. add geometry, scale and short-term motion priors without forcing an identity when appearance disagrees;
5. only escalate to learned feline ReID / sequence modeling when simpler held-out baselines fail for measured reasons.

## Product / licensing boundary

The identity architecture is model-neutral, but the current real experiment is **not** a product stack:

- SuperAnimal checkpoint is research-only for this project;
- target seed and candidate poses are R3 model-derived outputs;
- same-clip threshold tuning is exploratory;
- no identity labels are generated as independent truth.

A product path will need a commercially usable multi-animal proposal layer and held-out evaluation before the assignment logic can be treated as validated.

## Scientific boundary

- Visual QA of this known failure window supports the semantic interpretation of the decisions.
- Appearance JSD is not an identity probability.
- Candidate slot labels such as `animal0`/`animal1` are not assumed persistent.
- `LOST` means the current evidence is insufficient to bind detail to the target; it does not mean the target animal is physically absent.
