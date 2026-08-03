# Keypoint topology — DRAFT

**Status: DRAFT, nothing decided.** This is the single most consequential design choice
in the project — it determines what the benchmark can measure, what downstream products
can express, and whether anyone else can use the result. Changing it after data
collection means recollecting.

---

## The design tension

Two goals pull in opposite directions:

- **Compatibility.** A skeleton that is a strict superset of AP-10K's 17 keypoints can
  be evaluated against existing models and reuses the field's tooling. Adoption is
  easier.
- **Sufficiency.** The entire reason this project exists is that existing skeletons
  cannot express ear and tail state. A skeleton that compromises on those reproduces the
  gap it was built to close.

**Recommended resolution: strict superset.** Keep AP-10K's 17 exactly, in their order,
then append. Costs nothing, buys cross-evaluation, and the appended points carry the
contribution. **OPEN** for the research pass to overturn.

---

## Existing skeletons, for reference

| Set | Count | Ear coverage | Tail coverage |
|---|---|---|---|
| AP-10K / APT-36K | 17 | **none** | 1 (root only) |
| Animal-Pose | 20 | 2 earbases | 1 (tailbase) |
| DLC multi-animal | 20 | 2 ears | 3 (base→tip) |
| CatFLW | 48 facial | facial landmarks incl. ear region | **none** (face only) |

Nothing published covers ear *articulation* (rotation and independent movement) or tail
shape beyond three points. Cat ears rotate ~180° independently — a single point per ear
cannot represent that, and ear rotation is one of the most information-dense signals in
feline body language.

---

## Draft proposal — 34 keypoints

### Block 1 — AP-10K compatible core (1–17), unchanged

`1 L_eye · 2 R_eye · 3 nose · 4 neck · 5 tail_root · 6 L_shoulder · 7 L_elbow ·
8 L_front_paw · 9 R_shoulder · 10 R_elbow · 11 R_front_paw · 12 L_hip · 13 L_knee ·
14 L_back_paw · 15 R_hip · 16 R_knee · 17 R_back_paw`

### Block 2 — Ear articulation (18–23) — **the contribution**

| # | Point | Rationale |
|---|---|---|
| 18 | L_ear_base_front | Base pair defines the ear's mounting axis |
| 19 | L_ear_base_back | With 18, gives rotation about the vertical |
| 20 | L_ear_tip | With 18–19, gives pitch/flatten state |
| 21 | R_ear_base_front | |
| 22 | R_ear_base_back | |
| 23 | R_ear_tip | |

Three points per ear is the minimum that distinguishes **rotation** (swivelled back,
listening behind) from **flattening** (airplane ears, defensive) — two states with
completely different meanings that a single ear point collapses into one.

**Known risk:** ear-base points are exactly what long fur occludes (benchmark stratum
A4) and what dark solid coats hide (A1). Expect these to be the lowest-accuracy points
in the set. That is a finding worth publishing, not a reason to drop them.

### Block 3 — Tail chain (24–28)

`24 tail_base (≡ 5, or replacing it) · 25 tail_q1 · 26 tail_mid · 27 tail_q3 · 28 tail_tip`

Five points along the tail. Rationale: a cat tail is a continuous curve whose *shape*
carries the signal — question-mark hook, bottle-brush, low swish, tip-flick. Three
points cannot represent an S-curve; five can approximate one.

**OPEN:** whether 24 duplicates keypoint 5 or replaces it. Duplication preserves strict
AP-10K compatibility at the cost of a redundant point. Recommend duplicate.

**OPEN:** is a fixed-count chain even right? Tail visible length varies enormously with
pose and occlusion. Alternatives: fixed count with visibility flags (simple, standard,
recommended for v1) versus a parametric curve fit (more faithful, non-standard, harder
to evaluate and for others to adopt).

### Block 4 — Head orientation and posture (29–34)

| # | Point | Rationale |
|---|---|---|
| 29 | head_top | Head pitch; head position is an FGS action unit |
| 30 | chin | With 29 and 3, a head orientation frame |
| 31 | L_whisker_pad | Muzzle tension proxy — an FGS action unit |
| 32 | R_whisker_pad | |
| 33 | withers | Spine line start; back-arch detection |
| 34 | spine_mid | With 4, 33, 5: posture curvature (arched, crouched, elongated) |

**OPEN and important:** points 31–32 are FGS-adjacent (muzzle tension is a pain action
unit). Including them is fine for a *research benchmark*, but any consumer product
reading them edges toward welfare inference and re-triggers the medical framing and vet
review. **The skeleton may legitimately measure more than a product is allowed to say.**
Keep that boundary explicit in product specs rather than by omitting points here.

---

## Not included, deliberately

- **Full facial landmarks (CatFLW's 48).** Out of scope: a different task (facial action
  analysis), a different capture regime (close-range), and the existing work there is
  CC BY-NC so there is no compatibility benefit to chase.
- **Individual toe/claw points.** Not resolvable at consumer video quality.
- **3D depth.** V1 is 2D. 3D is a later question and depends on the synthetic pipeline
  emitting depth, which Unity Perception can do — noted, not scoped.

---

## Open questions for the research pass

1. Strict AP-10K superset, or design fresh for cat anatomy and accept incompatibility?
2. Three points per ear, or is two sufficient in practice at consumer resolution?
3. Tail as fixed chain with visibility flags, or parametric curve?
4. Include the FGS-adjacent points (31–32) in a public research benchmark, given the
   product-side constraints they imply?
5. Are per-keypoint OKS sigmas estimable, or does the benchmark report PCK only?
6. Does the synthetic pipeline emit **occlusion** and **self-occlusion** flags per
   keypoint? Unity can, real annotation must match, and it changes the annotation
   protocol. Decide before either begins.
