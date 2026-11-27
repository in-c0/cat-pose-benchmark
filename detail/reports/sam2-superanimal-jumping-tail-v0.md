# Automatic real-cat tail centreline — SuperAnimal → SAM2 → geometry

Status: **feasibility passed; accuracy not yet established**

This experiment tests whether CatPose needs a dedicated learned tail network before trying
a simpler compositional approach.

## Pipeline

```text
licence-approved cat video
→ SuperAnimal-Quadruped tail endpoints (research-only R3 teacher)
→ automatic frame/prompt selection
→ SAM2.1 Hiera Tiny prompted segmentation
→ skeletonization
→ longest base-to-endpoint geodesic
→ 24-point ordered CatPose tail centreline
```

No owner-operated capture, manual frame selection, manual landmark annotation, or manual
segmentation is required by the pipeline.

## Source

- clip: Wikimedia Commons `Cat jumping backwards.webm`
- recorded licence: CC-BY-3.0
- experiment screens only the original-motion portion before the slow-motion replay
- sampled at 1.5 fps over the first 8 seconds

See `bakeoff/clips/commons-cat-jumping-backwards.json` for source provenance.

## Automatic teacher selection

GitHub Actions run: `31891814198`

Teacher-seed artifact:
- name: `jumping-cat-superanimal-tail-seed`
- artifact ID: `9248762634`
- digest: `sha256:917afea0d1cb60224194d04095d66c13a618354371125bdd2e9c1381291c6acf`

The selector chose sampled frame index **5** at timestamp approximately **3.333 s**.

SuperAnimal prompt endpoints:

- tail base: `(472.81, 304.38)`, score ≈ **0.778**
- tail tip: `(642.19, 415.00)`, score ≈ **0.840**
- endpoint separation: ≈ **9.22% of image diagonal**
- image: `1920 × 1080`

Seven body/paw points were used as negative prompts after spatial-clearance filtering.

The automatic selection rule maximizes the weaker of the two endpoint confidence scores,
subject to confidence and endpoint-separation gates. Visual QA of the generated prompt
overlay confirms that, unlike the earlier `Cat Plays` failure, both positive prompts fall
on the clearly separated visible tail while negative prompts remain on the body/paws.

The prompt remains **R3 model-derived evidence**. High teacher confidence is not an
independent accuracy measurement.

## SAM2 segmentation and centreline

Result artifact:
- name: `jumping-cat-auto-tail-result`
- artifact ID: `9248787039`
- digest: `sha256:cde6d0a97b9b7b4e78f7ee5b93e845720db287177f30e7298deee26c52b76576`

SAM2:
- repository: `facebookresearch/sam2`
- pinned code commit: `2b90b9f5ceec907a1c18123530e92e794ad901a4`
- checkpoint: `facebook/sam2.1-hiera-tiny`
- code/checkpoint licence: Apache-2.0
- execution: CPU

Three SAM2 mask candidates were evaluated. Candidate selection prioritizes prompt
semantics before SAM2's own predicted-IoU score:

1. all positive tail prompts must be contained;
2. negative body prompts should be excluded;
3. then use SAM2 predicted IoU;
4. then prefer a smaller mask as a tie-break.

Chosen candidate diagnostics:

- positive prompts inside: **2/2 = 100%**
- negative prompts outside: **7/7 = 100%**
- mask area: **7,830 px**
- mask area fraction: ≈ **0.378%** of the image
- SAM2 predicted IoU: ≈ **0.200**

The lower SAM2 score is deliberately not hidden. The chosen mask wins because it is the
only candidate that cleanly satisfies the semantic positive/negative prompt constraints;
higher-scoring alternatives include substantially more body/background.

The binary mask is skeletonized, anchored at the teacher tail base, traced to the
farthest reachable skeleton endpoint, and arc-length resampled to **24 ordered points**.

Visual QA of the generated `tail-overlay.jpg` shows the selected mask tightly following
the visible raised tail and the derived centreline following the tail arc from rump/root
to visible tip. This is qualitatively different from the earlier failed `Cat Plays`
case, where a semantically wrong teacher tail-tip caused a large limb/background mask and
loop-like skeleton.

## Earlier failure retained as evidence

Run `31891570005` on `Cat Plays.webm` is retained as a negative control.

The SuperAnimal tail-tip prediction in that frame landed on/above a raised hind limb,
not a clearly traceable visible tail. SAM2 was prompt-consistent but semantically wrong.
This demonstrates:

> Prompt consistency cannot rescue a wrong teacher landmark.

The failure is why frame/prompt selection and visual/evidence QA are part of the method,
rather than silently accepting every teacher-generated pseudo-label.

## Decision

### NO-GO now: dedicated learned tail network

This result crosses the feasibility bar for a non-tail-specific learned solution:

```text
existing animal endpoints
+ generic foundation segmentation
+ deterministic geometry
→ useful continuous feline tail curve
```

A dedicated neural tail head is therefore **deferred**, not justified by structural
absence alone.

### GO next

1. replace the research-only SuperAnimal endpoint source with a commercially clean or
   independently trained endpoint source;
2. add sparse independent visible-tail labels to measure actual curve error;
3. measure failure modes across occlusion, curled tails, body overlap and motion blur;
4. add temporal propagation/consistency so each frame does not start from scratch;
5. continue the learned-detail investigation on **ear geometry**, which remains less
   solved than the tail after this compositional result.

A learned tail component should be reconsidered only if these measurements expose a
persistent residual error that segmentation + geometry + temporal reasoning cannot close.

## Scientific and licensing boundary

- SuperAnimal prompts are research-only R3 model outputs under Issue #9.
- SAM2 masks are R3 model outputs, not independent annotations.
- the derived skeleton/centreline is also R3.
- visual QA establishes plausibility, **not numerical accuracy**.
- none of these artifacts are automatically cleared product-training labels.
- tail centreline represents visible surface geometry, not internal vertebral anatomy.

## Reproducibility

Main successful workflow: `31891814198`

Core feline-detail CI also passes across Python 3.11, 3.12 and 3.13, covering:

- observation schema;
- visibility-aware ear/tail metrics;
- variable-control-point arc-length comparison;
- mask-skeleton tail extraction;
- SAM2 candidate ranking;
- automatic tail frame/prompt selection.
