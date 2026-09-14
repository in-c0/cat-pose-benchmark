# Held-out clips, dense sampling, and a self-trained tail probe

Date: 2026-09-14. Code: `detail/tail_probe.py`, `review/clips.json` (two held-out and two
dense entries), results set `review/results/2026-09-14-heldout-v0/`. Evidence tier of every
model output: S2. Counts marked eyeball are one person's read of the sheets.

This is stage 3 of the accuracy plan, item 8: train the tail. It has three parts, because
training turned out to depend on the other two.

## 1. Held-out clips

Every threshold in notes 01–03 was chosen on the same 57 frames. Two more Commons clips
were added after the last threshold was fixed and nothing was tuned on them:

| clip | licence | frames (2 fps) | what it is |
|---|---|---|---|
| commons-black-cat-walking | CC0-1.0 | 38 | one black cat walking towards and past the camera, tail up throughout, 1080p |
| commons-cat-licking-tail | CC-BY-SA-3.0 | 52 | one young cat on a sofa licking its tail, which lies along the sofa edge for the first half and is curled under the cat for the second, 640×480 |

Results, eyeball:

| clip | method | accepted | on the tail | wrong | refused with tail visible |
|---|---|---|---|---|---|
| walking | v0 grounded | 36 | 36 | 0 | 0 (f036, f037 have no cat box: extreme close-up, the tail fills the frame) |
| walking | v1 | 34 | 34 | 0 | 2 (f031, f032, refused by the temporal pass) |
| walking | v2 | 35 | 35 | 0 | 1 |
| walking | anchored | 30 | not read closely | | 6 refused, 1 no root |
| licking | v0 grounded | 34 | ~25 | ~9 (face, paw, sofa cushion, a leg) | 0 |
| licking | v1 | 27 | 27 | 0 | 0 |
| licking | v2 | 28 | 28 | 0 | 0 |
| licking | anchored | 0 | — | — | 27 |

v1's held-out precision is 61 of 61 by this read, and on the licking clip it refuses the
25 tucked frames on which v0 draws something wrong nine times. The walking clip is easy
for every grounded variant; the licking clip is where the "whether" machinery earns its
keep. The two clips are easier than *Cat Plays* (no white paws next to the tail), so this
is not a claim of 1.0 in general; it is the first evidence that the crop check and the
temporal pass were not fitted to the training clips' quirks. The anchored method, whose
thresholds were fitted more tightly, produces nothing on the licking clip.

## 2. Dense sampling

The temporal pass was tuned at 3–4 fps. Resampling the two training clips at 8 fps
(entries `*-dense` in `clips.json`, excluded from review) changes v1 substantially on
*Cat Plays*:

| sampling | v1 accepted | on the tail (eyeball) | tail-visible frames refused |
|---|---|---|---|
| 4 fps (33 frames) | 6 | 5 | 6 |
| 8 fps (66 frames) | 25 | ~22 | ~3 |

At 8 fps a true tail has a smooth neighbour a quarter of the distance away, so the
temporal pass stops refusing isolated frames, which was the main recall loss in note 02.
The tucked stretch is still refused entirely. This is the cheapest recall gain found in
the whole programme and it is a sampling-rate setting, not a model change.

## 3. The probe

`detail/tail_probe.py` trains a logistic-regression probe on SigLIP crop embeddings from
pseudo-labels: positives are the tail boxes v1 accepted on the dense clips (61), negatives
every other candidate on those frames (138). No human label is involved. The probe is
meant to replace the six-sentence zero-shot crop check.

Leave-one-clip-out, which is the only honest number with two clips:

| held-out clip | precision | recall | n |
|---|---|---|---|
| commons-cat-plays-dense | 0.31 | 0.16 | 128 |
| commons-cat-jumping-backwards-dense | 0.50 | 0.72 | 71 |

It does not transfer. A probe trained on one cat's tails does not recognise the other
cat's. With 61 positives from two animals in two rooms this is the expected outcome,
and it says what item 8 needs before it is worth doing: tails from more cats than two,
and labels a person has checked rather than the pipeline's own output. The probe is kept
in the repository as `detail/models/tail_probe_v0.json` with its training counts and
leave-one-clip-out numbers inside it, so that the next attempt can be compared, and it
is not wired into any method.

## What this stage changes

- Notes 01–03 now have a held-out check. v1/v2 hold; anchored does not.
- Sampling rate is a first-class parameter of the temporal pass. The review set's 3–4 fps
  was chosen for the SAM2 seed fixtures, not for the method.
- Training a tail component is blocked on data, not code. The review protocol's
  correction mode and the public call for clips are the path to that data.
