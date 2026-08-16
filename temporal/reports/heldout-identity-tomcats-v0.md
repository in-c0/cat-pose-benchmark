# Held-out identity v0 — Tomcats conflict

Status: **PASS on an independent easy/static two-cat appearance case; harder dynamic held-out validation still required**

## Protocol frozen before inference

This clip was not used to choose the exploratory appearance threshold from the original `Cat jumping backwards` regression.

Source:
- Wikimedia Commons `Tomcats conflict.webm`;
- 45.485 s, 640×480;
- two tomcats in a face-off / conflict scene;
- CC0 1.0 Universal;
- repository manifest: `bakeoff/clips/commons-tomcats-conflict.json`.

Before running SuperAnimal or inspecting identity scores, the held-out protocol was fixed as:

1. sample the full clip at **1 fps** → 45 frames;
2. request up to two SuperAnimal-Quadruped candidates per frame;
3. define target mechanically as **the leftmost candidate in the first frame with at least two candidates**;
4. build the reference appearance crop from that seed candidate bbox + 5% padding;
5. keep the previous RGB 8×8×8 histogram + Jensen-Shannon divergence gate at **0.30**, unchanged;
6. never retune the threshold on this clip;
7. apply `TARGET / LOST / RE-ACQUIRED` logic;
8. visually review selected boxes only after the quantitative run.

The screen was selected for evaluation because both cats are continuously visible and spatially separated. It is therefore a useful independent appearance-generalization case, but not a hard occlusion/re-acquisition benchmark.

## Run

GitHub Actions run: `31919411591`

Artifact:
- ID `9255939127`;
- digest `sha256:83202cacdc116b33aeb1146ffd23664b00bb6abb75d39096599f10b413e3a90b`.

### Proposal layer

SuperAnimal with `max_individuals=2` returned:
- **2 candidates on all 45/45 frames**;
- 0 single-candidate frames;
- 0 zero-candidate frames.

The deterministic seed rule selected source frame 0, leftmost candidate slot `animal1`:
- bbox ~`[26.4, 204.8, 241.7, 371.3]`;
- centroid ~`[156.9, 274.2]`.

Visual inspection identifies this seed candidate as the left brown/tabby cat. The second candidate is the right grey cat.

Candidate slot names switch repeatedly over the clip (`animal0` / `animal1`), confirming again that detector slot labels cannot be treated as persistent identity.

## Frozen 0.30 appearance gate

Quantitative result over all 45 held-out frames:
- target decisions: **45/45 = 100%**;
- LOST: **0/45**;
- re-acquisition events: 0 (target was continuously accepted);
- maximum selected-target JSD: **0.1552**;
- no frame approached the frozen 0.30 rejection threshold.

The distractor is usually much farther from the seed appearance than the selected target. Examples:

| Frame | selected target JSD | distractor JSD |
|---:|---:|---:|
| 0 | 0.0089 | 0.3700 |
| 10 | 0.0612 | 0.3329 |
| 20 | 0.0469 | 0.3745 |
| 29 | 0.1552 | 0.5445 |
| 40 | 0.0502 | 0.3137 |
| 44 | 0.0412 | 0.4251 |

Some detector slot IDs swap while the appearance assignment continues to select the same physical cat, which is the intended behavior.

## Visual QA

All 45 post-run overlays were reviewed through three contact sheets.

Result:
- every selected box stays on the **left brown/tabby cat**;
- the right grey cat is never silently selected;
- no false identity switch is visible;
- the target remains continuously detected, so this clip does not exercise the `LOST`/re-acquisition path strongly.

Thus the frozen appearance gate generalizes cleanly to this independent, visually distinct, mostly static two-cat scene.

## Decision

### Supported

The current modular identity architecture survives its first true held-out clip:

```text
multi-animal proposals
→ appearance-based explicit assignment
→ persistent target binding independent of candidate slot IDs
```

There is still no evidence-backed reason to jump to a large learned temporal/ReID model solely for this easy case.

### Not yet established

This is **not** broad feline ReID validation.

The two animals are visually distinct and mostly remain on opposite sides with limited severe occlusion. Therefore this result does not prove robustness to:
- similar-looking cats;
- crossing trajectories;
- motion blur;
- close contact / overlap;
- long occlusion;
- target disappearance and later re-entry;
- camera motion / illumination change.

## Next gate

Keep the same frozen threshold and move to a harder independent CC0 clip with close dynamic interaction: `Domestic catfight.webm`.

Do not retune 0.30 before that run. If the frozen RGB-histogram baseline fails there, use the failure to determine whether the next minimal addition should be:
- geometry / motion consistency;
- a stronger licence-clean appearance descriptor;
- proposal-layer improvement;
- only then a learned ReID / sequence component.

## Scientific / licensing boundary

- SuperAnimal candidates remain research-only R3 model outputs.
- The target definition is deterministic but is not an independent identity annotation.
- Visual review establishes semantic consistency for this one clip, not statistical ReID accuracy.
- The 0.30 gate remains an engineering threshold inherited from the prior regression; it was not fitted to this held-out clip.
