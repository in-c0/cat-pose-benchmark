# Grounded tail v0 — ask a detector for "tail"

Date: 2026-09-14. Code: `detail/grounded_tail.py`, driven by `review/run_tail_grounded.py`.
Evidence tier of every output: S2. Counts below are one person's read of the contact
sheets, not verdicts recorded under the review protocol.

## Why

The anchored method (`anchored-tail-v0.md`) showed that geometry can rule out a leg but
cannot tell a tail from a strip of shadow. The missing thing was semantics. This is the
cheapest way to get some: a text-promptable detector, Grounding DINO (tiny, Apache-2.0),
asked for `"cat. tail."` on every frame, and SAM2 to turn the chosen tail box into a mask.

## What it does

1. Grounding DINO returns labelled boxes for `cat` and `tail`. Prompting `"cat tail."` as
   one phrase grounds the whole animal at 0.85+; splitting into two phrases gives
   separate cat and tail boxes, which is what is used.
2. The cat box is the one overlapping the body run's detection when there is one
   (keeps the same cat on the two-cat clip), else the highest score.
3. The tail box is the highest-scoring `tail` whose centre lies in that cat box and whose
   area is under half the cat box. Threshold 0.2.
4. SAM2 segments the tail box; the mask is clipped to the box; the centreline starts at
   the `tail_root` keypoint when the body run has one, else at the cat-box centre.

No propagation, no geometry rules. A keypoint veto exists behind a flag and is off; see
below for why.

## Result on the review set

| clip | frames | grounded: curve | on the tail (eyeball) | what the wrong ones are |
|---|---|---|---|---|
| commons-cat-plays | 33 | 33 | 11 (f000, 004, 005, 007–012, 019, 020) | the white hind or front paw, 20 frames; white chest, 1; ambiguous, 1 |
| commons-cat-jumping-backwards | 24 | 15 | 14 (f005–012, 016, 017, 020–023) | f014 is a small stub; 9 frames have no cat box (blur) |

Against the other two methods on the same frames:

| method | Cat Plays: curve / on tail | Jumping: curve / on tail | never claims a leg? |
|---|---|---|---|
| propagated (`sam2_tail_video`) | 20 / 4 | 21 / ~12 | no — 15 frames on a paw |
| anchored (`anchored_tail`) | 7 / 3 | 6 / 4 | yes, by construction |
| grounded (this) | 33 / 11 | 15 / 14 | no — 20 frames on a paw |

Three things stand out.

- **When the tail is visible and extended, the detector finds it.** Every frame of the
  jumping clip where a cat was detected and a tail is out has the right tail, on both
  cats, including two frames (f016, f017) where YOLOX-m had no detection at all.
  The detector also serves as a better cat detector than YOLOX-m on this footage.
- **When the tail is tucked, it draws a paw.** *Cat Plays* is a cat rolling on its back
  with its tail under it for two thirds of the clip. The detector has no "no tail"
  answer once it has a cat, so it returns the most tail-like thing: a white paw or the
  white chest, at scores 0.25–0.40. The right tails score 0.32–0.60. Not separable by
  threshold alone; f012 is right at 0.25, f001 wrong at 0.40.
- **The keypoint veto does not fix that.** Refusing masks that contain a limb keypoint
  removed six true tails (RTMPose had put paw keypoints on the tail of the upside-down
  cat) and kept five paws (its keypoints were wrong there too). It trades one model's
  errors for another's, so it is off by default and the keypoints inside the mask are
  recorded as diagnostics instead.

## Addendum 2026-09-14: grounded + anchored geometry

The owner asked for the combination: apply the anchored method's body-contact and
elongation rules to the grounded tail mask (against a SAM2 cat mask), so a paw lying
against the body is refused. Implemented as `--geometry-rules`, off by default; the
features are recorded on every accepted frame regardless.

Measured on the same frames (eyeball truth):

| clip | grounded alone: accepted / right | + geometry rules: accepted / right | true tails lost to the rules |
|---|---|---|---|
| commons-cat-plays | 33 / 11 | 10 / 5 | f000, 004, 007, 008, 011, 019 |
| commons-cat-jumping-backwards | 15 / 14 | 10 / 10 | f016, 020, 022, 023 |

Precision goes up (33 % → 50 % on *Cat Plays*, 93 % → 100 % on the jumping clip) and
recall roughly halves. The features do not separate the two classes: right tails span
body-contact 0.0–0.93 and elongation 1.1–6.4; paws span 0.19–1.0 and 0–6.0. A tucked
paw and a tail curled against the flank look the same to these measures, and the
centreline skeleton is noisy enough on small masks that elongation is unreliable below
about 3 000 px of area. A counter-prompt (`"cat. tail. leg. paw."`) was also tried: the
detector returns merged labels such as `tail leg` on right and wrong frames alike, so it
does not separate them either.

So the honest state is: the detector decides *where* well and *whether* badly, and
neither geometry nor a second prompt fixes *whether* on this footage. Left off.

## What would move it further

- A better "no tail visible" decision. Geometry on the box and a paw counter-prompt were
  both tried (addendum above) and do not do it. Temporal consistency is untested: a real
  tail box moves smoothly between frames, a paw picked by default jumps. So is asking a
  vision-language model the direct question, "is this cat's tail visible?", per frame.
- A stronger grounding model. This is the tiny variant. SAM 3 accepts text concepts
  natively and tracks them through video; its licence needs checking before it goes
  anywhere near the product path.
- Human verdicts. `tail_curve_grounded` rows are in the template; the numbers above are
  an eyeball pass and should be replaced.

## Not done

- No human verdicts on any method.
- No held-out clip. Thresholds and the two-phrase prompt were chosen on these frames.
- Runtime: about 0.45 s per frame for Grounding DINO on an RTX 2080 plus SAM2. Fine for
  a benchmark, not for a puck.
