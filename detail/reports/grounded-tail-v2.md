# Grounded tail v2 — coverage: detector, bigger models, bridging, SAM 3

Date: 2026-09-14. Code: `detail/tail_bridge.py`, `review/run_tail_grounded_v2.py`,
`review/run_body.py --detector grounding`, model switches in `detail/grounded_tail_v1.py`.
Evidence tier of every output: S2. Proxy truth as in `grounded-tail-v1.md` (note 01's
frame reading; IoU ≥ 0.3 with the v0 box counts as right). Items refer to the accuracy
plan the owner set after note 01: 4 bigger models, 5 Grounding DINO as the cat detector,
6 grounded re-seed + SAM2 propagation, 7 SAM 3.

## A bug found first

`pick_cat_box` accepted only detections labelled exactly `cat`. Grounding DINO sometimes
merges the two phrases and labels the whole animal `cat tail`; on four jumping-clip
frames (f002, 003, 004, 018) that was the only cat box, so v0 and v1 reported `no_cat`
there. Fixed to accept any label containing the word `cat`. After the fix v0 accepts 17
jumping frames instead of 15; v1's proxy score moves from 18/1/7 to 17/1/8
(precision 0.94, recall 0.68) because the temporal path changes around the new frames.
Note 01's and note 02's numbers predate the fix and are left as published; this report
and note 03 use the fixed code.

## Item 4 — bigger models

| change | accepted | right | wrong | missed | precision | recall |
|---|---|---|---|---|---|---|
| v1 as shipped (tiny + SigLIP base) | 19 | 18 | 1 | 7 | 0.95 | 0.72 |
| Grounding DINO **base** instead of tiny | 6 | 3 | 3 | 22 | 0.50 | 0.12 |
| SigLIP **so400m** instead of base | 25 | 17 | 8 | 8 | 0.68 | 0.68 |

Neither is a drop-in. The base detector returns lower scores on this footage (the same
tail box at 0.38 where tiny gives 0.58) and fewer candidates, so the temporal pass, whose
none-emission is calibrated to tiny's score scale, refuses almost everything. It would
need its own thresholds, which would mean another fit on the same 57 frames; not done.
The larger SigLIP is more confident and calls more tails paws. Both switches remain
available (`--detector`, `--classifier`).

## Item 5 — Grounding DINO as the cat detector for the body run

`review/run_body.py --detector grounding` prompts Grounding DINO with `"cat."` and hands
the box to RTMPose exactly as YOLOX-m's box was. Now the default.

| clip | YOLOX-m: frames with a cat | Grounding DINO: frames with a cat |
|---|---|---|
| commons-cat-plays | 26 / 33 | 33 / 33 |
| commons-cat-jumping-backwards | 17 / 24 | 22 / 24 |

Downstream (eyeball): the anchored method on the jumping clip goes from 6 accepted / 4
right to 13 accepted / about 9 right, 2 wrong (a strip of back on f010, a blob on f012)
and 2 stubs; on *Cat Plays* it is unchanged at 6–7 accepted. v1 is unaffected because
it runs its own detection; it only uses the body run for the cat-box preference and the
`tail_root` keypoint. This is the cheapest change in the stage and the one with the
clearest effect: the detection ceiling that capped every method in note 01 is mostly
gone.

## Item 6 — bridging gaps with SAM2 propagation

`detail/tail_bridge.py` takes a v1 result, seeds SAM2's video predictor with the mask of
each accepted frame, and propagates into neighbouring frames refused for lack of evidence
(`no_cat`, `no_tail_box`, `temporal_none`) up to `max_reach` frames each way. Frames
refused because every candidate looked like a paw are never filled. A propagated mask is
accepted if its area is within 0.4–2.5× the seed's and the SigLIP check does not call
its bounding box a paw.

| reach | frames added | right (eyeball) | wrong (eyeball) |
|---|---|---|---|
| 1 | 2 (*Cat Plays* f004, jumping f006) | 2 | 0 |
| 2 | 7 (+ f003, f010, f017; jumping f005, f014) | 5 | 2 (f003 a paw, f017 the hip) |

Shipped at reach 1 as method `tail_grounded_v2`. The SigLIP check on propagated masks
did not fire on either wrong frame (its scores were near zero for every class), so the
area-ratio rule and the short reach are what hold precision. Propagation drifts onto a
paw within two frames at 4 fps on *Cat Plays*, the same failure note 01 started from.

## Item 7 — SAM 3

`facebook/sam3` on the Hub is gated (manual approval) under a non-standard licence. Not
attempted: access needs the owner's account and the licence needs reading before the
model goes anywhere near this repository. Recorded as blocked on the owner.

## Where this leaves the numbers

Proxy scoring, both clips, after the label fix, with the grounding body run:

| method | accepted | right | wrong | missed | precision | recall |
|---|---|---|---|---|---|---|
| v0 grounded | 50 | 25 | 25* | 0 | 0.50 | 1.00 |
| v1 grounded + crop check + temporal | 18 | 17 | 1 | 8 | 0.94 | 0.68 |
| v2 = v1 + bridging (reach 1) | 20 | 19 | 1 | 6 | 0.95 | 0.76 |

\* includes the two jumping frames (f002, f003) the label fix added, which note 01 never
judged and the proxy therefore counts as wrong.

Stage 2 moved recall by two frames and detection coverage by twelve. The recall the
owner asked for is still capped by the temporal pass refusing isolated true tails
(*Cat Plays* f000, f009–012) and the crop check refusing white-tipped tails next to white
paws. Those are not coverage problems; they are the "whether" trade-off from note 02,
and the way past them is labels, not another rule.
