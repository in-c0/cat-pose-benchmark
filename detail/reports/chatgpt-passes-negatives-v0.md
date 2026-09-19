# ChatGPT-pass session, 20/09/2026 — negatives and non-adopted variants

Status: **record of what was tried against frozen truth and rejected.** Nothing here
changes a shipped method. The pass-by-pass log with numbers lives in the portfolio hub
(`_hub/reviews/2026-09-20-cat-pose-chatgpt-passes.md`); this file keeps the negatives
next to the code so the next person does not re-run them.

All numbers are against `review/truth/frames.csv` (protocol 1 until pass 8, 1.1 after),
reviewer `claude-809c44f2` — a model, not a human. Counts are TP / FPv / FN / FPn on the
four review clips (Cat Plays, jumping, walking, licking). Reference: v1 77/0/22/2,
v3 85/0/14/2.

## Dense inference at fixed timestamps (pass 1) — rejected

Run the clips at 2–4× the review frame rate and score only the review timestamps
(`dense_of` / `dense_factor` in `review/clips.json`, `--dense` in the scorer). The proxy
scorer first showed +3 recall points; under frozen truth it is 73/1/25/8 — worse on both
axes. Denser sampling gives the temporal pass more junk proposals on hidden-tail frames
and the NONE state loses.

## Time-normalised emissions (pass 2) — rejected

Scaling the Viterbi emission and switch terms by frame interval (`detail/rechoose.py
--time-scale`, ChatGPT's exact weights) collapses Cat Plays: 63/0/32/1. The frozen
weights were tuned at the review rate; normalising them is not a free change.

## Top-K lattice (pass 3) — rejected before building

Oracle: how many frames does the correct box appear in the top-5 candidates but not the
top-2? One (`detail/topk_oracle.py`). A K>2 lattice cannot gain more than that frame.

## Lower detector threshold (pass 5) — rejected

`detail/lowthresh_oracle.py` dumps every "tail" box down to score 0.05. Usable boxes
below 0.20 on frames v1 missed: 2 (jumping f004, f013). On hidden-tail control frames the
detector proposes 2.9 boxes ≥ 0.20 per frame. Thresholds are not the bottleneck; the
detector always proposes something.

## Loose cat gate (pass 6) — no change

`--loose-gate` (tail box need only be 30 % inside the cat box): identical to v1. The
0.35/0.41 boxes that looked recoverable were the *other* cat's tail (pass-5 mislabel,
corrected).

## Switch-cost sweep (pass 6) — no plateau

`NONE_SWITCH_COST` 0.20 → 77/0/22/2; 0.15 and 0.10 → 78/0/21/3; 0.05 → 77/0/22/10;
0.00 → 75/0/24/12. The first FP arrives with the first TP.

## Bidirectional bridge variants (pass 6) — intersection adopted, others not

left / right / union each admit the jumping f019 blob (one side's mask 3× its seed,
IoU 0.00 between sides); intersection refuses it (empty). Adopted as v3.

## Contiguous-gap tracking, v4 (pass 8) — rejected

`detail/tail_track.py`: track from every accepted frame through the whole adjacent
refusal run, two-sided intersection with no length limit, one-sided until the first
failure (empty mask / no centreline / area ≥ 2.5× seed), no re-admission after a stop.
Result 90/0/9/10: +5 TP (jumping f002–f005 on the tabby tail, licking f028) and +8 FPn,
all Cat Plays, where SAM2 slides from the tail onto the black hind leg and never goes
empty. Frame-level diagnostics (area ratio, previous-frame IoU, SigLIP paw probability)
do not separate the false tracks from the true ones; only the context does (the detector
had a cat box and refused candidates on the false runs, nothing at all on the true ones).
Acceptance test was ΔTP ≥ 3 with ΔFPn = 0; failed on the second clause.

## Truth corrections made along the way

Cat Plays visible set revised three times (white-tip rule: a black limb ending in a white
paw is a leg); walking f006 v0 box was on the ear; pass-5 oracle labels on jumping
f013/f015 were the other cat's tail. Truth v1.1 adds the second cat's tail on the jumping
clip, including the tuxedo tail standing upright on the scratcher on f007–f017 with the
body hidden, which no earlier annotation had.
