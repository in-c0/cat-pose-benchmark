# Ground-truth provenance and uncertainty

**Status:** draft v0.2  
**Purpose:** prevent synthetic state, observable labels, reconstructed estimates, and
independent measurements from being silently treated as equivalent.

## Principle

The benchmark stores **observations**, not one supposedly complete and exact pose.

Each observation answers four questions:

1. What variable was observed or estimated?
2. Which source produced it?
3. How uncertain is it in this frame or interval?
4. Which transformations, models, and reviewers contributed to it?

Uncertainty is allowed—and expected—to vary across landmarks, axes, views, and time.

## Observation classes

### `surface_landmark`

A point or small region on the exterior of the animal, such as nose, eye corner, ear tip,
ear base, paw centre, or tail base.

### `surface_curve`

A sampled curve or spline, primarily for tail centreline, ear boundary, body centreline,
or another deformable exterior structure.

### `contact_event`

A temporally bounded interaction such as paw contact, stance, take-off, landing, or
support-surface transition.

### `scene_geometry`

Camera pose, floor plane, mesh or point-cloud surface, obstacle, support surface, and
other geometric scene state.

### `spatial_relation`

A categorical or scored relation such as `on`, `under`, `inside`, `behind`, `approaching`,
or `retreating`.

### `latent_anatomy`

A hidden joint centre, internal axis, or skeletal element inferred from anatomy,
kinematics, or a fitted model. It never omits inference provenance.

### `derived_temporal`

Velocity, acceleration, angular velocity, curvature change, blink duration, gait phase,
or another quantity computed from observations over time.

## Evidence tiers

Evidence tier describes the source of the observation, not whether the value is useful.

| Tier | Name | Meaning |
|---|---|---|
| S | Synthetic exact | Exact state inside the declared simulator, asset, animation, camera, and timestep configuration; not evidence of real-world accuracy |
| R2 | Real observable | Directly reviewable fact in real media, such as a visible landmark, tail curve, silhouette, or event timing; uncertainty includes reviewer ambiguity |
| R3 | Reconstructed estimate | Model-, geometry-, anatomy-, or constraint-derived real-world estimate without sufficient independent measurement |
| G1 | External simultaneous imaging | Independent calibrated simultaneous-view geometry operated by a partner |
| G2 | External motion capture | Vicon or another independently operated tracking system, with marker interpretation retained |
| G3 | External depth/surface | Calibrated RGB-D, photogrammetry, scanning, or another traceable surface measurement |
| G4 | External contact | Pressure walkway, force plate, transparent contact system, or another independent support/contact measurement |
| G5 | External anatomical/clinical reference | Existing ethically justified anatomical or skeletal measurement with declared registration and uncertainty |
| U0 | Unlabelled | Media retained for self-supervised, adaptation, or qualitative use without reference observations |

A frame can contain observations from several tiers. For example, visible ear tips may be
R2, an occluded hip R3, and a pressure-derived paw contact G4. A Unity sequence may have
S observations for all declared simulator variables.

## Quality states

Quality is separate from evidence source:

- `gold`: exact within Tier S, or independently measured/reviewed within its declared
  tier and acceptance protocol;
- `silver`: constrained or automatically generated evidence passing predefined checks;
- `bronze`: weak supervision unsuitable as the sole evaluation reference;
- `unknown`: not yet reviewed.

No quality name overrides the evidence tier. Tier S gold means exact inside the simulator,
not real-world gold. An attractive Tier R3 estimate cannot become gold merely because it
looks plausible.

## Required fields

Every observation records:

- schema version;
- sequence and frame or interval identifiers;
- subject identity;
- observation class and semantic name;
- coordinate space and units;
- mean geometry, state, or event interval;
- uncertainty representation where uncertainty is non-zero or modelled;
- visibility and occlusion state;
- evidence tier and quality state;
- source identifiers;
- transformation and processing lineage;
- validation checks and results;
- consent and licence record identifiers where applicable.

## Tier S requirements

A synthetic exact observation must record enough state to reproduce its claim:

- engine and project version;
- source asset and animation version;
- deterministic seed;
- timestep and frame index;
- camera configuration;
- coordinate conversion;
- exporter version;
- numeric validation comparing exported values with runtime state.

Tier S uncertainty may be zero for authoritative simulator state, but rendering,
projection, discretisation, and platform tolerances must still be declared in validation
metadata.

## Tier R2 requirements

A real observable observation records:

- visible-versus-inferred status;
- reviewer or annotation-process version;
- image scale and visibility;
- ambiguity or reviewer disagreement;
- propagation lineage when sparse keyframes are tracked through video;
- media rights and consent records.

A fully hidden landmark is not R2. It is omitted or supplied as R3.

## Tier R3 requirements

A reconstructed estimate records:

- model family and checkpoint;
- training and adaptation lineage where relevant;
- scene, anatomy, temporal, or identity constraints;
- confidence or uncertainty method;
- source observations;
- validation checks and disagreement between contributing methods.

R3 may support training and exploratory analysis, but cannot be the sole reference for
the same model family.

## External-gold requirements

G1–G5 observations are accepted only through
[EXTERNAL-VALIDATION-CONTRACT.md](EXTERNAL-VALIDATION-CONTRACT.md). The external partner
owns physical operation, safety, ethics, calibration, synchronization, consent, and data
custody. The CatPose project supplies software, schemas, QA, imports, and evaluation.

External gold is not required for Protocol v0.1. Its absence restricts metric real-world
claims but does not invalidate synthetic exact or real observable benchmarks.

## Uncertainty representation

### Points

A 2D or 3D point uses a covariance matrix or another explicitly documented confidence
region when uncertainty is non-zero. A scalar confidence alone is insufficient because
depth uncertainty can differ substantially from image-plane uncertainty.

### Curves

A curve stores sampled means plus local covariance, or a basis/spline representation with
parameter covariance. Tail-tip uncertainty may be larger than tail-base uncertainty.

### Contact events

A contact event records start and end distributions or bounded intervals, spatial contact
region, measurement or rule, and temporal resolution.

### Occluded anatomy

If a location cannot be directly observed, represent a plausible region as R3 or omit the
label. Do not collapse an anatomical prior to an exact coordinate merely to satisfy a
conventional skeleton format.

## Visibility states

- `visible`;
- `partially_occluded`;
- `fully_occluded`;
- `out_of_frame`;
- `motion_blurred`;
- `indistinguishable`;
- `not_applicable`.

Multiple flags may apply. Visibility affects uncertainty but does not determine it alone.
In Tier S, visibility is computed from declared camera/frustum/occlusion rules rather
than assumed from object existence.

## Time-varying uncertainty

Uncertainty responds to measurable conditions, including:

- image scale and focus;
- motion blur and shutter interval;
- occlusion duration;
- point-track survival and re-detection;
- scene-map uncertainty;
- inter-reviewer spread;
- model or constraint disagreement;
- external calibration and synchronization residuals;
- triangulation baseline and viewing angle where applicable.

An observation may transition from R2 while visible to R3 during occlusion, then return
to R2 when directly resolvable. Lineage preserves that transition.

## Derived temporal quantities

Finite differences amplify noise. Velocity and acceleration therefore use a declared
estimator and propagated uncertainty.

At minimum, a derived observation records:

- source observations and timestamps;
- simulator timestep or real capture timing;
- smoothing or state-space model, if any;
- differentiation window;
- output covariance or interval;
- handling of missing and occluded samples;
- whether the result spans an evidence-tier transition.

Benchmark metrics must avoid rewarding over-smoothed trajectories that erase genuine
fast motion.

## Anti-circularity rules

1. A model family cannot be evaluated solely against labels generated by that family.
2. Scene or anatomical constraints may improve an estimate but do not create independent
   measurement.
3. Human correction of a model output retains the original model lineage.
4. Tier S validates simulator and algorithm behaviour, not real-world accuracy.
5. Tier R3 may support training, but primary real-observable claims require R2 and metric
   real-world claims require G1–G5.
6. Manual adjudication performed after seeing a model result is logged.
7. External-gold scores remain separately reported from S, R2, and R3.

## Aggregating multiple sources

Do not overwrite disagreement. Store each source observation, then create an optional
fused observation with:

- named fusion method;
- source observation identifiers;
- assumptions about independence;
- outlier handling;
- resulting covariance;
- residuals and rejected inputs.

Correlated sources are not treated as independent merely because they produce separate
files.

## Evaluation implications

A submission is evaluated on estimate quality and uncertainty quality:

- positional or curve error;
- topology and contact error;
- likelihood-based error where distributions are provided;
- confidence-region coverage;
- calibration error;
- risk–coverage curve;
- error stratified by visibility, evidence tier, motion, fur, lighting, and viewpoint;
- recovery when a landmark transitions from visible to occluded and back;
- synthetic-to-real degradation between matched S and R2 strata.

Leaderboards state which tiers are included. Scores from different evidence tiers are not
combined into one number that obscures evidence strength.

## Example Tier S observation

```json
{
  "schema_version": "0.2.0",
  "observation_id": "s0-proxy/frame-000012/tail-tip/world",
  "sequence_id": "s0-proxy",
  "frame_index": 12,
  "timestamp_ns": 200000004,
  "subject_id": "proxy-cat-001",
  "observation_class": "surface_landmark",
  "semantic_name": "tail_tip",
  "coordinate_space": "world",
  "units": "metres",
  "mean": [0.42, 0.31, 0.18],
  "visibility": ["visible"],
  "evidence_tier": "S",
  "quality": "gold",
  "source_ids": ["unity-runtime:tail-tip-transform"],
  "lineage": [
    "unity-project:stage-s0-v0.1",
    "seed:17",
    "fixed-delta-time:0.016666667",
    "exporter:stage-s0-v0.1"
  ],
  "validation": {
    "runtime_transform_error_m": 0.0,
    "tier_scope": "exact-inside-simulator"
  }
}
```

## Open questions

- minimum uncertainty representation required for public submissions;
- how to estimate reviewer covariance without excessive annotation cost;
- which latent anatomy variables should be omitted entirely from v0;
- how rich observations map into conventional keypoint files;
- whether external-gold custody uses private labels, remote evaluation, or escrow.
