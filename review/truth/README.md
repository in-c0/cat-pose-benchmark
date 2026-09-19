# Frame truth v1

Two layers, so that what is in the frame is never entangled with what a method did.

## Layer 1 — frame truth (`frames.csv`), method-independent, annotated once and frozen

Columns: `clip_id, frame_index, timestamp_s, target_cat, tail_visibility, tail_identity_confidence, condition, note, reference_box`

- `tail_visibility`: `visible` | `partial` | `not_visible` | `uncertain`
- `tail_identity_confidence`: `high` | `medium` | `low` — how sure the annotator is that the appendage judged is the tail (Cat Plays showed that "I can see an appendage" and "that appendage is the tail" are different claims).
- `condition`: `none` | `blur` | `occlusion` | `out_of_frame` | `dark` | `small` | `multi_cat` | `appearance_ambiguous`
- `reference_box`: `x0 y0 x1 y1` in frame pixels, a box the annotator confirmed lies on the tail, used by the scorer to decide whether a method's box is on the same thing. Blank when nothing confirmed.
- `uncertain` is excluded from precision and recall, never converted to `not_visible`.

Clip-level annotation instructions (in `clips.md`) hold the rules that made decisions reproducible, for example: *the Cat Plays tuxedo cat has an all-black tail; a black limb ending in a white paw is a leg.*

Annotation was done on raw frames with no method overlay visible, then every `visible` / `partial` / `uncertain` frame was re-opened once more.

## Layer 2 — method judgement (`methods/<method>.csv`), one row per method × frame

Columns: `clip_id, frame_index, method, output_status, wrong_part, box_quality, note`

- `output_status`: `correct` | `partial` | `wrong_part` | `wrong_cat` | `no_output` | `unusable_curve`
- `wrong_part`: `front_leg` | `hind_leg` | `paw` | `ear` | `head` | `torso` | `furniture` | `background` | `other` | blank
- `box_quality`: `usable` | `partial` | `unusable` | blank

`review/score_truth.py` derives these rows from a method's `result.json` and the reference boxes (correct = accepted and the box overlaps the reference at IoU ≥ 0.3 or 80 % containment), then applies the hand overrides in `methods/overrides.csv` for the frames where the automatic match is known to be wrong (recorded with a reason). Metrics are derived, never encoded by the reviewer:

- visible/partial + correct → TP; visible/partial + no_output → FN; visible/partial + wrong_part/wrong_cat → FP and FN
- not_visible + no_output → correct refusal; not_visible + any asserted tail → FP
- uncertain → excluded
- `partial` frames are reported separately as well as inside the visible denominator.

## Revisions

- **1.1** (pass 8, 2026-09-20): instance-complete. `alt_cat`, `alt_tail_visibility`, `alt_identity_confidence`, `alt_note`, `alt_reference_box` carry a second cat's tail where one is discernible (only the jumping clip). The primary metric is instance-agnostic — an output on any annotated tail is correct; `assoc_mismatch` in the scorer counts TPs that sit on the other cat's tail while the method's cat box is on the target.
- **1.2** (pass 9): walking f006/f007 reference boxes replaced. Both had been taken from detector boxes that cover the whole cat with the tail tip at the top edge, so a whole-body box scored as a tail. The references are now the tail tip itself. The scorer's containment rule became one-way at the same time (a box no larger than the reference with 80 % of itself inside it), so a box that merely contains the tail no longer matches.

## Provenance

- `annotation_protocol_version: 1`
- `reviewer_id: claude-809c44f2` — **a model, not a human.** Produced by Claude Code during the 2026-09-20 ChatGPT-pass session from raw frames with the rules in `clips.md`. It supersedes the proxy readings in notes 01–04 and in `review/eval_proxy.py`, which are kept for the record. A human reviewer should replace or confirm this file; the review protocol's own template (`review/results/*/reviews/TEMPLATE.csv`) remains the human path.
- `frozen_at_commit`: recorded in `frames.csv` header comment when frozen.
