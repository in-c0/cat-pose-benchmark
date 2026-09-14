# Review set 2026-09-14 — held-out clips v0

Two clips added after every threshold in the repository was fixed, so nothing here was tuned on them. Sheets, run summaries and the empty verdict template for the human frame review; rubric in `review/README.md`. No human verdicts yet.

| clip | licence | fps | frames | body: frames with a cat | v0 grounded: curve | v1: curve | v2: curve | anchored: curve |
|---|---|---|---|---|---|---|---|---|
| commons-black-cat-walking | CC0-1.0 | 2.0 | 38 | 38 | 36 | 34 | 35 | 30 |
| commons-cat-licking-tail | CC-BY-SA-3.0 | 2.0 | 52 | 52 | 34 | 27 | 28 | 0 |

What is visible on the sheets before any verdict (one person's read, see `detail/reports/held-out-and-probe-v0.md`): on the walking clip v1's 34 accepted frames all sit on the tail; on the licking clip v1 accepts the 27 frames where the tail lies along the sofa and refuses the 25 where the cat has curled around it, while v0 draws a face, a paw or the sofa on seven of those. The anchored method produces nothing on the licking clip: every candidate fails its rules.
