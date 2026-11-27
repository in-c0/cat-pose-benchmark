# Whole-animal identity v0 — single-object propagation still switches cats

Status: **REVISE — a whole-animal SAM2 track does not solve the measured multi-cat identity failure**

## Question

The tail-sequence experiment showed that a local tail mask switches semantic target when a second cat becomes salient. The smallest proposed repair was to track the **whole target cat** independently and bind local ear/tail detail to that persistent identity.

This experiment asks:

> If SAM2 is seeded with a clean whole-grey-cat mask before the failure window, does it preserve that cat's identity when another cat becomes more salient?

## Source and R3 seed

Source:
- Wikimedia Commons `Cat jumping backwards.webm`;
- CC-BY-3.0;
- first 8 seconds;
- 1.5 fps = 12 regression frames.

Target seed:
- frame index 5 (~3.333 s);
- intended animal: grey cat;
- nine distributed SuperAnimal-Quadruped R3 positive points: nose, neck, back, four paws, tail base, tail tip;
- prior teacher run `31891814198`, artifact `9248762634`;
- teacher/checkpoint remains research-only for this project.

The second dark cat is already visible elsewhere in the seed frame, so this is not a trivial sequence where a distractor appears only after conditioning.

## Whole-animal seed construction

The image predictor receives the nine distributed target-cat points plus eight background negatives generated mechanically outside the teacher-point envelope.

Chosen SAM2 image candidate:
- candidate 2;
- all target positives supported: **9/9**;
- all auto-background negatives excluded: **8/8**;
- predicted IoU: ~**0.8664**;
- mask area: **56,662 px = 2.7325%** of the 1920×1080 frame;
- bbox: `[159, 249, 606, 492]`.

Visual QA confirms the seed mask is the intended grey cat.

The explicit image mask is then supplied to `SAM2VideoPredictor.add_new_mask` rather than using ambiguous point prompts directly.

Video-model seed preservation:
- seed-mask IoU: **0.9923**.

So the identity failure below cannot be explained by a bad initial mask or poor handoff into the video model.

## Real regression run

GitHub Actions run: `31918506215`

Artifact:
- ID `9255661564`;
- digest `sha256:f39f9e67154388d33b82b1347e9c6c9b7328112f7a2942c4bdd0ea87fc3977e4`.

Automated continuity summary:
- non-empty masks: **11/12 = 91.7%**;
- empty frame: **0**;
- no crude area-expansion/collapse flags;
- strict automated result: **REVISE** because of the empty frame;
- mean centroid step: ~**9.12%** image diagonal;
- maximum centroid step: ~**24.91%**.

These coarse metrics alone are insufficient to detect semantic identity, which is why visual regression review was predeclared as required.

## Visual identity result

Frames approximately 1–8 generally follow the intended grey cat.

At **frame 9**, the track switches to the other cat on/near the small chair while the intended grey cat is visibly blurred at the left side of the frame.

The switch persists:
- frame 9: wrong cat;
- frame 10: wrong foreground cat;
- frame 11: wrong foreground cat.

Therefore:

> **A clean whole-animal SAM2 mask is not a sufficient persistent feline identity representation in this multi-cat sequence.**

This falsifies the proposed architecture `whole-animal SAM2 track → identity gate → local details` if SAM2 propagation alone is expected to provide identity.

## Appearance diagnostic

A simple RGB histogram Jensen-Shannon divergence against the seed masked appearance was recorded as an unsupervised diagnostic.

Selected values:
- frame 4: ~0.0019;
- seed frame 5: ~0.0000;
- frame 6: ~0.1000;
- frame 7: ~0.2213;
- frame 8: ~0.1928;
- **frame 9: ~0.3801**;
- **frame 10: ~0.4085**;
- **frame 11: ~0.4236**.

The frame-8→9 transition also has a large centroid jump (~16.85% image diagonal), followed by ~24.91% at frame 10.

On this single sequence, the appearance diagnostic rises sharply exactly when visual identity changes. This is useful evidence for an explicit **lost/suspicious identity state**, but it is **not** a calibrated feline ReID score and no universal threshold is claimed.

## Decision

### Rejected as sufficient

```text
single target seed
→ one SAM2 video object
→ assume object ID == persistent cat ID
```

The model's object slot can drift to a different animal after motion/occlusion/salience change.

### Next minimal layer

Do not jump to a large temporal transformer yet.

Test:

```text
multi-animal candidate proposals
+ prior target appearance / geometry
→ explicit assignment
→ target / lost / re-acquired state
```

The first gate is simply whether a two-individual animal-pose run exposes both cats around frames 9–11. If it does, test the smallest assignment cost before any learned ReID model:

1. seed-appearance similarity;
2. prior position/scale/shape consistency;
3. confidence only as a supporting term, never identity by itself.

When no candidate matches, output **lost** rather than silently switching.

## Scientific boundary

- Seed points, SAM2 masks and propagated masks are R3 model-derived evidence.
- Visual QA identifies the semantic switch in this regression clip; it is not a dense identity benchmark.
- RGB appearance JSD is an engineering diagnostic, not an identity probability.
- No current output is automatically eligible as product-training supervision.
