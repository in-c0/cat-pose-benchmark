# Human frame review

Status: first review set built 2026-09-13 on the two Wikimedia Commons clips; anchored tail method added the same day, grounded tail method 2026-09-14. No human verdicts yet.

This directory turns "the overlay looks right" into a number. A person looks at what the models drew on real cat frames and says, part by part, whether it is on the cat or not. That is coarse, but it is the first evidence in this repository that comes from someone checking real animals rather than from a model checking another model.

It does not measure pixel error. A verdict of `ok` means "the tail curve is on the tail", not "the tail curve is within 5 px". Numerical accuracy still needs Stage 0 or hand-placed labels. Verdicts collected here are G3-tier in the sense of `docs/GROUND-TRUTH-PROVENANCE.md` (human-verified under a written protocol), but they verify the model output, not a landmark position, so the scorer labels them `G3-verdict` rather than plain G3.

## What gets reviewed

Four methods:

- **body** — RTMPose-m AP-10K, the same checkpoint the bake-off runs, here via OpenMMLab's ONNX export and rtmlib so it runs on Windows without MMPose. Detection is YOLOX-m; the largest cat-or-dog box is used. Keypoints below score 0.3 are drawn hollow and are not judged.
- **tail** — the existing SAM2 tail propagation (`detail/sam2_tail_video.py`), seeded from the committed SuperAnimal fixtures with the seed frame index re-mapped to the review sampling.
- **tail_anchored** — `detail/anchored_tail.py`, added after the first review found the propagated mask on a hind leg. SAM2 segments the whole cat; the body is subtracted geometrically using the RTMPose keypoints; what is left at the tail root is the candidate, and anatomical rules reject anything that contains a limb keypoint, is speckle, or is a strip peeled off the back. It refuses more often than it guesses. Needs only body keypoints, so it runs on every clip.
- **tail_grounded** — `detail/grounded_tail.py`. Grounding DINO is asked for `"cat. tail."` on every frame; the highest-scoring tail box inside the cat box goes to SAM2 for a mask. Semantics only, no geometry, no propagation. Finds an extended tail well; when the tail is tucked it tends to draw a paw. Runs on every clip and needs no body run.

Frames are sampled at a fixed rate per clip (`clips.json`). The rate is chosen so the tail seed fixture lands exactly on a sampled frame; do not change it without re-checking the seed index. `sample_frames.py` refuses to run if they disagree.

## The rubric

One row per clip, frame and part. Seven parts:

| part | method | you are judging |
|---|---|---|
| `head` | body | eyes and nose are on the face |
| `spine` | body | neck and tail-root points are on the body, roughly where they belong |
| `front_paws` | body | front paw points are on front paws |
| `hind_paws` | body | hind paw points are on hind paws |
| `tail_curve` | tail | the yellow curve follows the tail of the seeded cat |
| `tail_curve_anchored` | tail_anchored | the yellow curve follows the tail of the cat the body skeleton is on |
| `tail_curve_grounded` | tail_grounded | the yellow curve (inside the cyan box) follows the tail of the boxed cat |

Three verdicts:

- `ok` — the drawn thing is on the right part. Small offsets are fine.
- `wrong` — it is on the wrong part, on a different object, on the wrong cat, or missing while the part is clearly visible. A red `NO OUTPUT` banner with a visible cat is `wrong`.
- `not_visible` — the part is hidden, out of frame, or the frame is too blurred to say. If in doubt, use this rather than guessing.

Only judge solid points. Hollow points are below threshold and the model is not claiming them.

Optionally add a `condition` from: `none`, `blur`, `occlusion`, `out_of_frame`, `dark`, `small`, `multi_cat`. It is used to group failures. `note` is free text.

For the two-cat jumping clip, the tail seed is on the grey tabby, so `tail_curve` is judged against the tabby's tail; a curve on the tuxedo cat is `wrong` with `multi_cat`. Body skeletons are judged on whichever cat they are drawn on, since the detector picks the largest box and is not tracking identity.

## How to review

1. Open the contact sheets under `results/<set>/sheets/`. Each tile is a cat-centred crop with the frame index and timestamp in its banner. Full-resolution overlays are under `work/<clip>/overlays/` if you need to zoom.
2. Copy `results/<set>/reviews/TEMPLATE.csv` to `results/<set>/reviews/<your-id>.csv`. The file stem becomes your reviewer id.
3. Fill `verdict` for each row. Leave rows blank if you did not review them; blank rows are ignored, not counted.
4. Score:

```bash
python -m review.score review/results/<set>/reviews/<your-id>.csv --output-md review/results/<set>/scores.md --output-json review/results/<set>/scores.json
```

With two reviewer files the scorer also reports raw agreement and lists every disagreement. Disagreements are kept, not averaged.

The scorer rejects any verdict, part or condition outside the vocabulary, and duplicate rows, so a typo shows up as an error rather than a silently skipped row.

## How to regenerate

```bash
python -m review.sample_frames
python -m review.run_body
python -m review.run_tail --device cuda
python -m review.run_tail_anchored --device cuda
python -m review.run_tail_grounded --device cuda
python -m review.sheets --output-dir review/work/sheets
python -m review.template --output review/results/<set>/reviews/TEMPLATE.csv
```

Requires `rtmlib`, `imageio-ffmpeg`, `transformers` (Grounding DINO), `sam2` (install with `SAM2_BUILD_CUDA=0`; the custom CUDA kernel is not needed) and the usual torch/PIL/scikit-image stack. Model weights download on first run. `review/work/` is git-ignored; the sheets, run summaries and frame manifests are copied into `results/` so a set can be reviewed without regenerating it.

## Adding a clip

Add an entry to `clips.json` pointing at a licence-verified manifest in `bakeoff/clips/`. If there is no SuperAnimal tail seed for it, omit `tail_seed`; body, tail_anchored and tail_grounded rows are still generated. Phone video of your own cat is fine; the body method needs nothing but the video.

## What this cannot tell you

- how far off a point is, only whether it is on the right part;
- anything about occluded joints;
- whether the tail method would work on a clip with no seed — every tail result here starts from a SuperAnimal prompt on one frame;
- population accuracy — two clips, two cats.

Treat the numbers as a failure-mode census.
