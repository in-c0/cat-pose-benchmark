# Anchored tail v0 — segment the cat, subtract the body

Date: 2026-09-13. Code: `detail/anchored_tail.py`, driven by `review/run_tail_anchored.py`.
Evidence tier of every output: S2. The counts below are one person's read of the contact
sheets, not verdicts recorded under the review protocol.

## Why

The owner reviewed the first frame-review set and reported the obvious: the propagated
SAM2 tail mask (`sam2_tail_video`) mistakes a hind leg for the tail. On *Cat Plays* the
seed is on the tail at frame 1 and on the raised white hind paw by frame 5, and stays
there. SAM2 tracks the blob it was shown; nothing in that loop knows what a tail is.

## What was tried, in order

1. **Point-prompt SAM2 for the tail directly**: `tail_root` positive, every other
   keypoint negative. Does not work. With more than about four negative points SAM2's
   IoU head reports 0.0 for all three candidates and the masks stay whole-cat or rump.
   Adding a ring of probe positives around the root produced elongated masks that were
   strips of the cat's back, or speckled ground texture. Abandoned.
2. **Segment the whole cat, subtract the body.** SAM2 is prompted with the detection
   box (plus the root, plus the previous tip when known), which it does well. The body is
   then removed geometrically: a morphological opening of the cat mask with a disc of
   0.045 × bbox diagonal keeps everything thick (trunk, head) and drops everything thin
   (tail, legs, ears); leg tubes drawn along the RTMPose limb bones and a head polygon
   remove the thin parts that have keypoints. What remains and touches the root is the
   candidate.
3. **Rules on the candidate**: within 0.10 diag of `tail_root`; ≤ 30 % of bbox area;
   survives a 3 px opening (not speckle); contains no limb or head keypoint; centreline
   long and thin (`length² / area ≥ 3`); centreline starts near the root; ≤ 35 % of its
   pixels lie in a thin band around the body (a tail touches the body at its base, a
   peeled-off strip of back touches it along its length).

Rules and thresholds are in the module and recorded in every `result.json`.

## Result on the review set

| clip | frames | detected | propagated: curve | propagated: on the tail (eyeball) | anchored: curve | anchored: on the tail (eyeball) |
|---|---|---|---|---|---|---|
| commons-cat-plays | 33 | 26 | 20 | 4 (f000–f003), then hind paw ×15 | 7 | 3 (f001, f019, f020); f011, f015, f016 are back strip; f002 uncertain |
| commons-cat-jumping-backwards | 24 | 17 | 21 | ~12 on the tabby, then tuxedo cat ×3 | 6 | 4 (f010, f011, f020, f021); f012 is a blob beside the cat; f004 a stub |

What changed:

- **No accepted output contains a limb keypoint.** That is by construction, and it is the
  failure the owner reported. The propagated method had it on 15 of 20 accepted frames on
  *Cat Plays*.
- **Coverage halved.** The anchored method refuses when it is unsure; the propagated method
  never refuses. Refusals on a visible tail are misses and a reviewer will mark them
  `wrong`, so this is a real cost, not free.
- **The new failure is the back strip.** On a cat lying on its back or curled, SAM2's cat
  mask includes a thin dark band of fur or shadow along the silhouette. The opening peels
  it off, it is elongated, it touches the root, and no keypoint is on it. Three of seven
  accepted *Cat Plays* frames are this.
- **Detection caps everything.** 7 of 24 jumping frames and 7 of 33 *Cat Plays* frames
  have no YOLOX-m detection at all, mostly motion blur. Neither tail method runs there.

This is an improvement in the kind of error, not a drastic improvement in accuracy.
Roughly half of what the anchored method accepts is a tail; roughly a quarter of what the
propagated method accepted was.

## What would actually move accuracy

- **Semantics.** Neither model knows what a tail is. A text-grounded segmenter
  ("cat tail") or a small tail-part head on a clean backbone gives per-frame semantics
  without hand-written geometry. The bake-off already concluded a small endpoint head is
  the one learned component worth building; it needs labels, which the review loop's
  correction mode would produce.
- **A better cat mask.** The back-strip failure is a SAM2 cat-mask boundary artefact; a
  mask that hugs the fur would not leave a sliver to peel.
- **A better detector.** A cat-specific detector or a tracker that bridges blur would lift
  the ceiling for every method.

## Not done

- No human verdicts yet on any method. `tail_curve_anchored` rows are in the template.
- Thresholds were set by looking at these two clips. They are not validated on held-out
  video and should be expected to move.
