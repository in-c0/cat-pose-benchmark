# Grounded tail v1 — zoom, crop check, temporal consistency

Date: 2026-09-14. Code: `detail/grounded_tail_v1.py`, driven by `review/run_tail_grounded_v1.py`.
Evidence tier of every output: S2. Truth used below is the v0 eyeball reading
(`grounded-tail-v0.md`) turned into a proxy: a v1 frame counts as right when v0 was
judged right there and the v1 box overlaps the v0 box at IoU ≥ 0.3; wrong when v1
accepts anything else; missed when v0 was right and v1 refused. Not protocol verdicts.

## Why

v0 finds an extended tail and draws a paw when the tail is tucked. Three ideas were
proposed to fix "whether": give the detector more pixels (zoom), ask a second model
whether the crop is a tail (crop check), and require the box to move smoothly
(temporal). All three were built; each can be switched off.

## What was built

1. **Zoom.** Detect the cat on the full frame, then run `"cat. tail."` on a 25 %-padded
   crop of the cat box; map boxes back.
2. **Crop check.** SigLIP (`google/siglip-base-patch16-224`, Apache-2.0) scores each
   candidate tail box, padded 30 %, against six texts: a cat's tail / paw / leg / face /
   belly / floor. A candidate is refused when its paw score is at least 0.10 and above its
   tail score.
3. **Temporal.** Up to two candidates per frame plus a "no tail" state, Viterbi over the
   sequence. Emission is the detector score; "no tail" emits 0.20; moving between boxes
   costs 0.5 × centre displacement in cat-box diagonals; entering or leaving "no tail"
   costs 0.20.

## Ablation

Proxy scores over both clips (48 frames with a cat box; 25 v0-right frames).

| configuration | accepted | right | wrong | missed | precision | recall |
|---|---|---|---|---|---|---|
| none (= v0) | 48 | 25 | 23 | 0 | 0.52 | 1.00 |
| zoom | 50 | 24 | 26 | 0 | 0.48 | 1.00 |
| crop check | 42 | 21 | 21 | 1 | 0.50 | 0.95 |
| temporal | 45 | 22 | 23 | 2 | 0.49 | 0.92 |
| zoom + crop check | 43 | 22 | 21 | 1 | 0.51 | 0.96 |
| crop check + temporal (first params) | 29 | 20 | 9 | 4 | 0.69 | 0.83 |
| zoom + crop check + temporal | 34 | 18 | 16 | 7 | 0.53 | 0.72 |
| **crop check + temporal (chosen)** | **19** | **18** | **1** | **7** | **0.95** | **0.72** |

The chosen parameters came from an offline grid over the saved candidates (paw
threshold 0.05/0.10/0.20, 1–3 candidates, none-emission 0.10–0.25, move weight
0.3–1.0, switch cost 0.05–0.20). The top of the grid is a plateau: a dozen settings give
18/1/7 or 17/1/8, and the strictest give 16/0/9. The chosen point is in the middle of it.

Per clip, chosen configuration:

| clip | accepted | right | wrong | missed | refused as paw | refused by temporal |
|---|---|---|---|---|---|---|
| commons-cat-plays | 6 | 5 | 1 (f006, a paw) | 6 (f000, 004, 009, 010, 011, 012) | 15 | 12 |
| commons-cat-jumping-backwards | 13 | 13 | 0 | 1 (f005) | 0 | 2 |

## What the ablation says

- **Zoom hurt.** The crop-pass detector returns lower scores and different boxes; the
  candidates on the tucked frames got no better and some right ones got worse. Off by
  default.
- **The crop check alone did nothing.** It correctly refuses the paw the detector picked
  first, and the detector's second candidate is another paw with SigLIP scores near zero
  for every class, so it passes. Refusing one wrong answer just exposes the next.
- **Temporal alone did little.** Wrong candidates on consecutive frames are often the
  same paw, which is as smooth as a tail.
- **Together they work.** The crop check removes the confident paws; what is left on the
  tucked frames is low-scoring and inconsistent, and the temporal pass prefers "no tail"
  to a low, jumping candidate. On *Cat Plays* every tucked frame is now a refusal.

The cost is recall. Six true tails on *Cat Plays* are refused: f009, f011, f012 by the
crop check (SigLIP calls them paw at 0.73, 0.30, 0.29), f000, f004, f010 by the temporal
pass (isolated frames with no smooth neighbour). On the jumping clip one true tail is lost
(f005, the tuxedo's tail before the tabby sequence starts) and every accepted frame is
right.

## Caveats

- The parameters were chosen on the same 57 frames they are reported on. The plateau in
  the grid is encouraging, but this is not a held-out result.
- The proxy truth is v0's eyeball reading, so a v1 frame that finds a tail v0 missed
  would count as wrong. On this set that does not happen (v0 had no misses on frames
  with a cat), but it would on a harder clip.
- Per-frame cost roughly doubles: SigLIP on two crops per frame plus the detector.
