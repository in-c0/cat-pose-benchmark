# Bilateral ear geometry v0 — endpoint anchors + generic segmentation are sufficient for visible 2D base geometry

Status: **compositional geometry feasibility passed on both ears of the first selected real frame**

## Question

Phase 0 established that existing quadruped systems can expose a single ear-base landmark and an ear-tip landmark, but CatPose's observation-first representation needs a visible base line with two endpoints:

- `base_medial`;
- `base_lateral`;
- `tip`.

This experiment asks whether those missing base endpoints require a dedicated feline segmentation/geometry network.

The tested composition is:

```text
existing ear-base midpoint + ear-tip semantic anchors
→ generic prompted part segmentation
→ proximal ear-mask chord
→ medial/lateral base endpoints
→ visible 2D ear axis / triangle
```

## Source and seed

Source:

- Wikimedia Commons `Cat jumping backwards.webm`;
- CC-BY-3.0;
- same 1.5 fps first-8-second screening sequence used by the tail work.

Selected frame:

- frame index 11;
- approximately 7.333 s;
- 1920×1080;
- foreground black/white cat, rear-facing, both ears visibly separated from the background.

Endpoint seeds are frozen **R3 research-only** outputs from the prior SuperAnimal-Quadruped run `31891814198`, artifact `9248762634`.

Automatic endpoint ranking by minimum base/tip confidence with a separation gate selected the right ear as the strongest ear candidate in the sequence. The opposite left ear in the same frame was then used as a bilateral replication.

### Right ear seed

- base score: ~0.704;
- tip score: ~0.865;
- base-tip separation: ~44.3 px.

### Left ear seed

- base score: ~0.670;
- tip score: ~0.806;
- base-tip separation: ~48.0 px.

These are semantic anchors, not independent landmark truth.

## Segmentation and geometry method

Model:

- SAM2.1 Hiera Tiny;
- `facebookresearch/sam2` code pinned to commit `2b90b9f5ceec907a1c18123530e92e794ad901a4`;
- CPU execution.

For each ear:

1. prompt SAM2 with the target ear base and tip as positive points;
2. use the opposite ear, eyes, nose and neck as negative points;
3. request multiple masks;
4. rank semantic prompt agreement before SAM2's own predicted-IoU score;
5. prefer a smaller geometrically valid part mask over a larger head/cat mask when semantic consistency ties;
6. project the base/tip semantic anchors onto the selected mask;
7. use the projected base→tip direction as the visible ear axis;
8. search the proximal region for the widest valid chord perpendicular to that axis;
9. assign the chord endpoint closer to the face-reference centroid as `base_medial` and the farther endpoint as `base_lateral`.

The result is visible image-space surface geometry only. It does **not** claim internal cartilage geometry or a unique 3D ear plane.

## Real bilateral run

GitHub Actions run: `31918164516`.

### Right ear

Artifact:

- ID `9255554742`;
- digest `sha256:ad3664ac28edf8b657f66f38dbae9596d44657257b12fb35d44fa4b8b91300c1`.

Chosen mask:

- candidate 1;
- area: **1,242 px** = **0.0599%** of the frame;
- negatives excluded: **6/6**;
- SAM2 predicted IoU: ~**0.725**;
- base chord: ~**37.0 px**;
- visible base-centre→tip length: ~**40.0 px**;
- width/length ratio: ~**0.925**;
- triangle area: ~**725 px²**.

The binary mask is a small triangular region aligned with the visible right ear. Visual QA places the derived chord across the ear attachment and the axis toward the visible tip.

The exact rounded tip prompt pixel falls just outside the chosen binary boundary, giving an exact-pixel positive containment score of 1/2. However the nearest selected-mask tip anchor is approximately `(723, 555)` versus the teacher seed `(725.15, 555.12)`, i.e. only ~2.15 px away. This is treated as a boundary-discretisation/seed-location diagnostic, not as evidence that the mask selected the wrong object.

### Left ear

Artifact:

- ID `9255553199`;
- digest `sha256:818452c99b9b18854ae90783e6504c6e5237c89b5bd6224d5b5fdfb7388ecc39`.

Chosen mask:

- candidate 1;
- area: **1,454 px** = **0.0701%** of the frame;
- positive anchors inside: **2/2**;
- negatives excluded: **6/6**;
- SAM2 predicted IoU: ~**0.456**;
- base chord: ~**31.0 px**;
- visible base-centre→tip length: ~**34.9 px**;
- width/length ratio: ~**0.888**;
- triangle area: ~**525 px²**.

Visual QA again shows a small triangular ear mask rather than a head mask, with the derived base chord and tip axis aligned to the visible left ear.

## Negative-mask evidence

For both sides SAM2 also offered much larger candidates covering roughly 3.8–4.0% of the image. Those masks included much of the head/cat and violated most negative prompts.

The semantic-first ranking correctly rejected them despite some larger candidates having competitive model scores. This is important: generic segmentation is only useful here when the benchmark explicitly encodes the part semantics being requested.

## Decision

### Ear segmentation/geometry

**NO-GO on a dedicated learned ear segmentation/geometry network at this stage.**

The first bilateral real test supports a smaller composition:

```text
ear base/tip anchors
→ generic part segmentation
→ deterministic visible base chord
→ CatPose ear triangle / image-space axis
```

This mirrors the tail result: a generic foundation segmenter plus deterministic geometry can supply the richer visible representation once reliable semantic anchors are available.

### What may still require learning

This does **not** eliminate the need for a feline-specific learned detail component entirely.

The remaining learned question is narrower:

> Can we obtain stable, licence-clean ear base/tip anchors under cat pose, scale, blur and occlusion without depending on research-only SuperAnimal weights?

RTMPose Animal does not expose ear landmarks, while the SuperAnimal checkpoint used here remains research-only for this project. Therefore a future product path may still need a **small ear-endpoint head** over a replaceable commercially usable animal/image backbone.

That head should predict semantic anchors only; it does not need to relearn segmentation or continuous ear geometry unless later experiments falsify this composition.

## Next experiments

Before training a large feline model:

1. measure anchor robustness over additional licence-clean frames, scales and head poses;
2. create sparse independent visible-ear reference labels for base corners/tip;
3. identify a product-clear feature backbone;
4. test the smallest endpoint-only head on licence-clean/synthetic labels;
5. escalate the backbone only if frozen-feature endpoint prediction fails for a diagnosed representational reason.

## Scientific boundary

- SuperAnimal seed points are R3 model-derived evidence, not ground truth.
- SAM2 masks and derived base corners are R3 model-derived evidence.
- Bilateral visual plausibility establishes engineering feasibility, not landmark accuracy.
- A unique 3D ear plane cannot be recovered from one 2D triangle without additional assumptions/observations.
- No behavioural, affective, pain or veterinary claim follows from ear orientation alone.
