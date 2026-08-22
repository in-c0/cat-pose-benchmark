# ID1.2 — YouTube-VIS feline → REMIND DAVIS adapter

**Status:** software bridge frozen before REMIND scores  
**Parent:** #72  
**Baseline:** REMIND `f88ea1d5d81da0a8ed28b206df6d4dab48327342`

## Purpose

The ID1.1 Tomcats smoke established that pinned REMIND executes coherently on feline video, but the generic YOLO proposal layer missed many visible cats. ID1.2 separates **identity association** from **detector recall** by using independent video-instance masks and persistent IDs as the REMIND DAVIS detector/ground-truth input.

YouTube-VIS is used as the first bridge because its annotation model already represents per-video instances across frames. This adapter does not assign new semantic identity: stable DAVIS IDs are a deterministic renumbering of source annotation IDs.

## Frozen candidate selection

`identity/id1_youtubevis_selection_spec.json` is frozen before any REMIND result is inspected.

Eligible videos must contain at least two persistent `cat` annotations. The category is resolved by **name**, not a hard-coded numeric category ID.

Candidates are ranked deterministically by:

1. more cat instances;
2. more co-visible frames;
3. larger internal disappearance/re-entry gap;
4. more frames with overlapping annotation bounding boxes;
5. more total visible track-frames;
6. lower source `video_id` as the final tie-break.

These are data-only selection criteria. They do not use REMIND output or performance.

## Commands

Inspect candidates without scoring:

```bash
python -m identity.youtubevis_adapter inspect \
  --annotations /path/to/train.json \
  --category-name cat \
  --min-instances 2 \
  --output /tmp/id1-youtubevis-candidates.json
```

Convert the frozen top-ranked candidate (or an explicitly preselected eligible video):

```bash
python -m identity.youtubevis_adapter convert \
  --annotations /path/to/train.json \
  --frames-root /path/to/train/JPEGImages \
  --output-dir /tmp/id1-youtubevis-davis \
  --source-uri '<dataset provenance URI>'
```

Output layout:

```text
id1-youtubevis-davis/
  frames/
    frame_000000.jpg
    ...
  annotations/
    frame_000000.png
    ...
  meta.json
  manifest.json
```

The PNG annotation uses background `0` and stable `uint8` foreground IDs `1..N`. `meta.json` includes `frame_names` plus labels such as `cat_1`, `cat_2`, matching the pinned REMIND DAVIS loader contract.

## Integrity gates

The converter fails closed on:

- missing or duplicate source IDs;
- category mismatch;
- malformed video/frame metadata;
- segmentation or bounding-box arrays with the wrong temporal length;
- missing or path-traversing frame paths;
- source frame dimensions that disagree with annotations;
- malformed compressed/uncompressed COCO RLE;
- more than 255 foreground instances for an 8-bit DAVIS mask;
- overlapping source instance masks that would require modifying ground truth;
- non-empty output directories.

COCO compressed RLE is decoded using the same signed delta/run logic as the reference COCO mask API. Polygon annotations require `pycocotools` so rasterisation stays COCO-compatible rather than using an approximate custom polygon fill.

## Provenance

`manifest.json` binds:

- exact source annotation SHA-256;
- source video/category identity;
- deterministic stable-ID mapping;
- source and copied frame hashes;
- generated mask hashes;
- generated meta hash;
- candidate statistics frozen before scoring;
- explicit `remind_scoring_performed=false` at conversion time.

## Quantitative run

Once official YouTube-VIS media + annotation files are present, the selected converted sequence can be evaluated through the pinned upstream DAVIS evaluator. The resulting `summary_global.csv` must then pass the already-merged `identity.remind_adapter` under the unchanged ID1.0 metric contract.

Do not change the selected source video after seeing REMIND scores.

## Claims boundary

A successful YouTube-VIS run can establish performance on the selected annotated feline video instance sequence. It does not establish longitudinal household identity, same-breed/look-alike robustness in the target home domain, or any intent/affect/translation/health claim.

A later feline-specific expansion should use Cat Royale or another independently annotated multi-cat longitudinal dataset when its source files are accessible under suitable terms.
