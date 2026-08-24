# ID1.2 — feline source-mask → REMIND DAVIS bridge

**Status:** source-format correction frozen before any REMIND score  
**Parent:** #72  
**Baseline:** REMIND `f88ea1d5d81da0a8ed28b206df6d4dab48327342`

## Purpose

The ID1.1 Tomcats smoke established that pinned REMIND executes coherently on feline video, but generic YOLO proposal recall was weak. ID1.2 therefore evaluates **identity association / re-identification** with independent persistent instance masks supplied through REMIND's DAVIS backend.

## Source correction before scoring

The experiment was initially preregistered against YouTube-VIS 2019 because the OpenDataLab repository is named `OpenDataLab/YouTubeVIS2019`.

The first authenticated acquisition completed with archive SHA-256:

`87ac10b9ea9635b95c77db7657be0a0c8e3612b68db05af27b7331fa6d6e6202`

Before any REMIND scoring, the downloaded archive was observed to contain:

```text
train/meta.json
train/JPEGImages/<video>/<frame>.jpg
train/Annotations/<video>/<frame>.png
```

That is the YouTube-VOS 2019 indexed-mask annotation model: `meta.json` stores persistent object IDs, categories and frame lists; those object IDs are the pixel values in the indexed PNG annotations. The failed first materialisation stopped before REMIND dependencies, evaluation or metric generation.

Accordingly the executed benchmark source is now recorded as **YouTube-VOS 2019**. This is a source-identification correction, not a result-driven dataset substitution. The original ranking order and minimum-two-cat requirement are unchanged; the historical selection-rule identifier remains `ID1-YTVIS-select-v0` to make that continuity explicit.

## Frozen candidate selection

`identity/id1_youtubevis_selection_spec.json` records both the original preregistration and the pre-score source correction.

Eligible videos must contain at least two persistent objects whose source category is exactly `cat` (case-insensitive). Candidates are ranked deterministically by:

1. more cat instances;
2. more co-visible annotated frames;
3. larger internal disappearance/re-entry gap measured on the ordered annotated-frame timeline;
4. more frames whose source-mask-derived cat bounding boxes overlap;
5. more total visible cat track-frames;
6. lexicographically lower source video ID as the final tie-break.

The indexed-mask adapter also verifies that every metadata-declared cat appearance exists in the corresponding source PNG. Inconsistent candidates are rejected before ranking and recorded in selection provenance.

## Actual archive adapter

`identity.youtubevos_archive` operates directly on the authenticated `train.zip` without fully extracting it. It:

- locates and hashes the single `meta.json`;
- resolves `cat` by category name;
- inspects only videos with at least two cat objects;
- computes the unchanged frozen ranking from source metadata/masks;
- selects rank 1 before REMIND scoring;
- extracts only the selected source frames;
- filters/remaps only the selected cats into stable DAVIS `uint8` IDs `1..N`;
- writes provenance-bound `meta.json`, `manifest.json`, frame hashes and mask hashes.

Output layout:

```text
ytvos-selected/
  selection.json
  source_meta.json
  davis/
    frames/
      frame_000000.jpg
      ...
    annotations/
      frame_000000.png
      ...
    meta.json
    manifest.json
```

The source object identity is not inferred or repaired. Stable DAVIS IDs are a deterministic renumbering of the source indexed-PNG object IDs.

## Integrity gates

The actual-source converter fails closed on:

- unsafe or duplicate ZIP member paths;
- malformed `meta.json` / object maps;
- non-integer or out-of-range indexed object IDs;
- duplicate/unsafe frame IDs;
- missing source image or mask members;
- metadata-declared object appearances absent from source masks;
- source-mask object appearances absent from metadata;
- mask/image dimension mismatch;
- changing frame dimensions within a sequence;
- non-empty output directories.

The earlier `identity.youtubevis_adapter` and its COCO-RLE tests remain in the repository as the originally preregistered VIS-format bridge; they are no longer the acquisition path for this verified archive.

## Quantitative execution

The credentialed workflow downloads the exact archive, verifies the frozen archive SHA, runs `identity.youtubevos_archive`, and hashes the selected sequence/ground-truth manifests **before scoring**. It then deletes the multi-gigabyte archive, installs the pinned REMIND runtime, runs REMIND's custom DAVIS batch evaluator with source masks as detections, and passes upstream `summary_global.csv` through `identity.remind_adapter` unchanged.

This isolates identity association from detector recall. With exact source masks supplied as detections, geometric detection quality is not an independent result.

Do not change the selected source video after seeing REMIND scores.

## Claims boundary

A successful run can establish REMIND identity-association performance on the selected annotated YouTube-VOS feline sequence under source masks. It does not establish end-to-end cat detection, longitudinal household identity, same-breed/look-alike robustness in the target home domain, intent, affect, translation, health or welfare inference.

A later feline-specific expansion should use Cat Royale or another independently annotated multi-cat longitudinal dataset when its files are accessible under suitable terms.
