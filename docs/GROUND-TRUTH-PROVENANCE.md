# Ground-truth provenance and uncertainty

**Status:** draft v0.1  
**Purpose:** prevent pseudo-labels, fitted anatomy, and direct measurements from being
silently treated as equivalent.

## Principle

The benchmark stores **observations**, not one supposedly complete and exact pose.

Each observation answers four questions:

1. What variable was observed or estimated?
2. Which independent source produced it?
3. How uncertain is it in this frame or interval?
4. Which transformations and models contributed to it?

Uncertainty is allowed—and expected—to vary across landmarks, axes, views, and time.

## Observation classes

### `surface_landmark`

A point or small region visible on the exterior of the animal, such as nose, eye corner,
ear tip, ear base, paw centre, or tail base.

### `surface_curve`

A sampled curve or spline, primarily for tail centreline, ear boundary, spine silhouette,
or another deformable exterior structure.

### `contact_event`

A temporally bounded interaction such as paw contact, stance, take-off, landing, or
support-surface transition.

### `scene_geometry`

Camera pose, floor plane, mesh or point-cloud surface, obstacle, support surface, and
object-relative spatial relation.

### `latent_anatomy`

A hidden joint centre, internal axis, or skeletal element inferred from anatomy,
kinematics, or a fitted model. It must never omit its inference provenance.

### `derived_temporal`

Velocity, acceleration, angular velocity, curvature change, blink duration, gait phase,
or another quantity computed from observations over time.

## Evidence tiers

Evidence tier describes the source of the observation, not whether the value is useful.

| Tier | Name | Meaning |
|---|---|---|
| G1 | Independent sensor | Direct measurement from a calibrated source independent of the evaluated pose model, such as contact surface or approved motion instrumentation |
| G2 | Simultaneous geometry | Triangulation or multi-view surface agreement from calibrated views captured at the same instant, including mirror-generated virtual views |
| G3 | Human-verified visual | Direct visual annotation reviewed under a defined protocol, with ambiguity and inter-annotator disagreement retained |
| S1 | Constrained estimate | Estimate from scene, anatomy, temporal, or identity constraints, validated where possible but not independently measured |
| S2 | Model pseudo-label | Output from a learned model or automated labeller without independent verification |
| X1 | Synthetic exact | Exact within the simulator or renderer; useful for synthetic evaluation but not evidence of real-world accuracy |
| U0 | Unlabelled | Media retained for self-supervised or qualitative use without a reference observation |

A frame can contain observations from several tiers. For example, paw contact may be G1,
ear tips G2, an occluded hip S1, and the unobserved tail tip absent.

## Quality states

Quality is separate from evidence source:

- `gold`: independently measured or simultaneously reconstructed and manually checked;
- `silver`: constrained or automatically generated evidence that passes predefined
  consistency checks;
- `bronze`: useful pseudo-label or weak supervision unsuitable as the sole evaluation
  reference;
- `unknown`: not yet reviewed.

No quality name overrides the evidence tier. A polished pseudo-label remains S2.

## Required fields

Every observation must record:

- sequence and frame or interval identifiers;
- subject identity;
- observation class and semantic name;
- coordinate space and units;
- mean geometry or event interval;
- uncertainty representation;
- visibility and occlusion state;
- evidence tier and quality state;
- source sensor or view identifiers;
- transformation lineage;
- annotator or automated process version;
- validation checks and their results;
- licence and consent record identifiers where applicable.

## Uncertainty representation

### Points

A 2D or 3D point should use a covariance matrix or another explicitly documented
confidence region. A scalar confidence alone is insufficient because depth uncertainty
may be much larger than image-plane uncertainty.

### Curves

A curve stores sampled means plus local covariance, or a basis/spline representation with
parameter covariance. Tail-tip uncertainty may be larger than tail-base uncertainty.

### Contact events

A contact event records start and end distributions or bounded intervals, spatial contact
region, sensor threshold, and temporal resolution.

### Occluded anatomy

If a location cannot be independently observed, represent the plausible region or omit
the label. Do not collapse an anatomical prior to an exact coordinate merely to satisfy
a conventional skeleton format.

## Visibility states

- `visible`: feature is directly resolvable;
- `partially_occluded`: only part of the feature is visible;
- `fully_occluded`: feature is not directly visible but may be constrained;
- `out_of_frame`;
- `motion_blurred`;
- `indistinguishable`: present but not separable from fur, body, reflection, or scene;
- `not_applicable`.

Multiple flags may apply. Visibility affects uncertainty but does not determine it alone.

## Time-varying uncertainty

Uncertainty should respond to measurable conditions, including:

- triangulation baseline and viewing angle;
- reprojection disagreement;
- calibration residual;
- image scale and focus;
- motion blur and shutter interval;
- occlusion duration;
- point-track survival and re-detection;
- mirror boundary or reflection ambiguity;
- scene-map uncertainty;
- inter-annotator spread;
- model or constraint disagreement.

A landmark may move from G2/gold to S1/silver during occlusion, then return to G2 when it
becomes visible again. The lineage must preserve that transition.

## Derived temporal quantities

Finite differences amplify noise. Velocity and acceleration must therefore be computed
with a declared estimator and propagated uncertainty.

At minimum, a derived observation records:

- source observations and timestamps;
- smoothing or state-space model;
- differentiation window;
- output covariance or interval;
- handling of missing and occluded samples;
- whether the result spans a quality-tier transition.

Benchmark metrics should avoid rewarding over-smoothed trajectories that erase genuine
fast motion.

## Anti-circularity rules

1. A model family cannot be evaluated solely against labels generated by that family.
2. Scene or anatomical constraints may improve an estimate but do not make it an
   independent measurement.
3. Human correction of a model output must retain the original model lineage.
4. Synthetic labels validate simulator consistency, not real-world accuracy.
5. Silver and bronze observations may support training, but primary benchmark claims
   require a separately reported gold subset.
6. Any manual adjudication performed after seeing a model result must be logged to avoid
   benchmark leakage.

## Aggregating multiple sources

Do not overwrite disagreement. Store each source observation, then create an optional
fused observation with:

- named fusion method;
- source observation identifiers;
- assumptions about independence;
- outlier handling;
- resulting covariance;
- residuals and rejected inputs.

Correlated sources must not be treated as independent merely because they produce two
files. For example, two labels derived from the same foundation model share lineage.

## Evaluation implications

A submission should be evaluated on both estimate quality and uncertainty quality:

- expected positional or curve error;
- Mahalanobis or likelihood-based error where distributions are provided;
- coverage of declared confidence regions;
- calibration error;
- risk–coverage curve when low-confidence predictions are abstained;
- error stratified by visibility, evidence tier, motion, fur, lighting, and viewpoint;
- recovery behaviour when a landmark transitions from visible to occluded and back.

Leaderboards must state which evidence tiers are included. A score against mixed gold and
pseudo-labels without separation is invalid.

## Example observation

```json
{
  "observation_id": "seq-0007/frame-001284/tail-tip",
  "sequence_id": "seq-0007",
  "frame_index": 1284,
  "timestamp_ns": 428001284000,
  "subject_id": "cat-0003",
  "observation_class": "surface_landmark",
  "semantic_name": "tail_tip",
  "coordinate_space": "world",
  "units": "millimetres",
  "mean": [142.1, 88.4, 311.9],
  "covariance": [
    [3.2, 0.1, 0.4],
    [0.1, 4.7, 0.8],
    [0.4, 0.8, 18.6]
  ],
  "visibility": ["partially_occluded", "motion_blurred"],
  "evidence_tier": "G2",
  "quality": "gold",
  "source_ids": ["camera-0/direct", "camera-0/mirror-left"],
  "lineage": [
    "calibration:v0.1.2",
    "triangulation:robust-ray-v0.1",
    "manual-review:reviewer-02"
  ],
  "validation": {
    "reprojection_error_px": 1.3,
    "cross_view_track_consistent": true
  }
}
```

## Open questions

- Minimum uncertainty representation required for public submissions
- How to estimate covariance for manual landmarks without excessive annotation cost
- Which latent anatomy variables should be omitted entirely from v0
- Whether quality tiers are assigned per observation, interval, or both
- How benchmark consumers should map rich observations into conventional keypoint files
