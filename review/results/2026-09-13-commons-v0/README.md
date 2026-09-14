# Review set 2026-09-13 — Commons clips v0

Sheets, run summaries and the empty verdict template for the first human frame review. See `review/README.md` for the rubric.

No human verdicts have been recorded yet. Everything below is what the models produced, not how correct it is.

| clip | licence | fps | frames | body: frames with a detection | tail: frames with a curve | tail: no curve | tail: mask expansion flagged | tail_anchored: frames with a curve | tail_grounded: frames with a curve |
|---|---|---|---|---|---|---|---|---|---|
| commons-cat-plays | CC-BY-SA-4.0 | 4.0 | 33 | 26 | 20 | 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32 | — | 7 (f001, 002, 011, 015, 016, 019, 020) | 33 |
| commons-cat-jumping-backwards | CC-BY-3.0 | 3.0 | 24 | 17 | 21 | 0, 17, 19 | 21, 22, 23 | 6 (f004, 010, 011, 012, 020, 021) | 15 (no cat box on f000–004, 013, 015, 018, 019) |

`tail_anchored` was added after the owner's first look at the sheets found the propagated tail on a hind leg. See `detail/reports/anchored-tail-v0.md` for what it does and an eyeball comparison. `tail_grounded` (Grounding DINO + SAM2) was added 2026-09-14; see `detail/reports/grounded-tail-v0.md`. The template now has 399 rows (seven parts).

Things visible on the sheets before any verdict is entered, for the reviewer to confirm or reject:

- `commons-cat-plays` tail: the seed on frame 1 is on the tail, but from about frame 5 the propagated mask sits on the raised white hind paw rather than the tail, and after frame 19 there is no mask at all. The earlier tail report already called this clip a failure case.
- `commons-cat-jumping-backwards` tail: the seed is on the grey tabby. Frames 21–23 are flagged for mask expansion; on the sheet the mask has swallowed the tuxedo cat.
- `commons-cat-jumping-backwards` body: the detector switches between the two cats, and misses 7 of 24 frames, mostly the motion-blurred ones.
- The tail run reports `video_seed_vs_input_mask_iou: 0.0` for the jumping clip even though the seed-frame overlay from the image predictor and from the video predictor look identical. This run was on CUDA without the SAM2 `_C` extension; the CI smoke ran on CPU and reported the seed preserved. Not investigated here.

Runtime: RTMPose via rtmlib/onnxruntime on CPU, about 0.25 s per frame; SAM2 hiera-tiny on an RTX 2080.
