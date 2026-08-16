# Held-out identity v0 — Domestic catfight

Status: **FAIL — frozen whole-bbox RGB appearance gate silently switches identity under close contact**

## Protocol frozen before inference

Source:
- Wikimedia Commons `Domestic catfight.webm`;
- 38.207 s original, 1920×1080;
- two domestic cats in close fighting/contact;
- CC0 1.0 Universal;
- repository manifest: `bakeoff/clips/commons-domestic-catfight.json`.

For compute efficiency the evaluation workflow downsamples only after licence/provenance materialization:
- 1 fps;
- 640×360;
- 38 evaluation frames.

Before proposal inference or identity scores were inspected, the same held-out protocol used for `Tomcats conflict` was frozen:

1. request up to two SuperAnimal-Quadruped candidates per frame;
2. target = **leftmost candidate in the first frame with >=2 candidates**;
3. reference appearance = seed candidate bbox + 5% padding;
4. descriptor = RGB 8×8×8 whole-bbox histogram;
5. distance = Jensen-Shannon divergence;
6. acceptance threshold = **0.30**, unchanged from the original regression;
7. no retuning on this clip;
8. output `LOST` when no candidate is below the gate;
9. visually inspect identity only after the quantitative run.

Raw 1 fps screening before model inference showed a much harder case than `Tomcats conflict`: repeated close contact, partial overlap, motion blur and the smaller white/grey cat frequently underneath the larger tabby. The deterministic leftmost seed rule was retained unchanged.

## Run

GitHub Actions run: `31919841865`

Artifact:
- ID `9256067945`;
- digest `sha256:db31ec67c0475928546dfb09ee35ae165199b828058f3310e08dc4fcaa1b7f74`.

## Proposal layer

Across all 38 one-second frames:
- frames with >=2 candidates: **18**;
- frames with exactly 1 candidate: **20**;
- frames with 0 candidates: **0**.

This already differs materially from the easy held-out case. During close contact the detector often collapses two cats into one animal proposal or exposes only one of them.

The first frame with two proposals was source frame 3. The deterministic leftmost rule selected slot `animal1`:
- bbox ~`[27.2, 21.8, 311.5, 290.3]`;
- centroid ~`[213.6, 156.3]`.

Visual inspection identifies this target as the **smaller white/grey cat**. The large brown/black tabby is the distractor.

## Frozen 0.30 gate — quantitative result

The gate evaluates source frames 3–37 = 35 frames.

Pure threshold statistics look deceptively strong:
- accepted `TARGET`: **35/35 = 100%**;
- `LOST`: **0**;
- maximum selected JSD: **0.2965**, just below the frozen 0.30 threshold.

That quantitative result is **not semantically correct**.

## Visual QA — silent identity switches

Post-run overlays show the whole-bbox histogram is contaminated by close contact, background and merged proposals. It can assign a low JSD to the wrong tabby and therefore fails the core safety property: emit `LOST` instead of silently binding to another cat.

Concrete failure examples:

### Frame 12 — distractor-only proposal accepted

The white/grey target is visibly lying at the left side of the frame.

The proposal layer returns **one** candidate:
- slot `animal0`;
- bbox ~`[120.0, 11.1, 625.2, 347.8]`;
- whole-bbox JSD ~**0.1258**.

The candidate is dominated by the large tabby / merged contact region. The system accepts it as `TARGET` even though the intended white/grey cat is visibly separate at left.

Correct conservative state should have been `LOST`.

### Frame 20 — both animals proposed, wrong one ranks better

Two proposals exist:
- large tabby / merged foreground candidate: JSD ~**0.1329**;
- smaller white/grey candidate at left: JSD ~**0.1455**.

The current cost selects the **tabby** because 0.1329 < 0.1455.

This is a direct assignment failure, not merely a proposal miss.

### Frame 30 — wrong large cat selected over partial target proposal

Two proposals exist:
- large tabby: JSD ~**0.1402** → selected;
- small partial white/grey target proposal: JSD ~**0.2965**.

Again the whole-bbox descriptor strongly favors the wrong animal.

### Frame 33 — another wrong-cat selection during overlap

Two proposals exist in close contact. The selected large-tabby box has JSD ~**0.1427**, while the alternative white/grey-region proposal is ~**0.1695**. Visual QA shows the selected thick box is on the tabby.

## Why whole-bbox RGB fails here

The easy `Tomcats conflict` clip worked because both animals were spatially separated and visually distinct; each candidate bbox mostly contained one cat.

In `Domestic catfight`:
- candidate boxes often include substantial pixels from **both cats**;
- boxes contain large amounts of common carpet/background;
- the target is partly occluded while the distractor fills the candidate bbox;
- detector boxes can merge the interaction region;
- RGB histograms discard spatial / local fur-pattern structure.

Thus low whole-box JSD is not sufficient evidence that the candidate is the same cat.

## Decision

### Falsified

Do **not** keep:

```text
multi-animal proposals
→ whole-bbox RGB histogram
→ JSD <= 0.30
→ TARGET
```

as the sole identity gate.

The frozen threshold correctly generalized to the easy independent clip but **fails on dynamic close contact**.

### Architecture retained

The higher-level architecture still holds:

```text
multiple animal proposals
→ explicit identity assignment
→ TARGET / LOST / RE-ACQUIRED
→ bind local detail only after identity passes
```

The failure is in the **candidate evidence**, not in the explicit-state architecture.

### Next minimal change

Before learned feline ReID, test more local / proposal-specific appearance evidence that is less contaminated by merged boxes:

1. appearance sampled around the candidate's own high-confidence keypoints rather than the full bbox;
2. optionally torso/core keypoint patches as a separate veto signal;
3. proposal-size / geometry sanity checks;
4. ambiguity / consensus gate when descriptors disagree;
5. preserve `LOST` rather than forcing a match.

A development prototype on this failure already indicates local keypoint patches strongly raise the wrong-tabby distance on frames such as 12 and 20. That prototype is development evidence only; it must be implemented reproducibly and then validated on another independent clip before any new ReID claim.

## Scientific / licensing boundary

- SuperAnimal proposals remain research-only R3 outputs.
- The deterministic seed rule does not create identity ground truth.
- Visual review identifies clear semantic failures in this regression clip but is not a dense annotated identity benchmark.
- This failed held-out clip can now be used as **development data** for identity v1; it must not simultaneously be counted as held-out validation of the changed method.
