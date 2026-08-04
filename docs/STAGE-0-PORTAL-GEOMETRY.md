# Stage 0 portal geometry experiment

**Status:** pre-registered engineering design. No animal recording is permitted in this
stage.

## Decision being tested

Determine whether one physical camera and two planar mirrors can create simultaneous
virtual views with sufficient geometric stability for the benchmark's compact gold
subset.

The consumer system remains monocular. The portal is measurement equipment used only to
estimate error and validate monocular outputs.

## Why Stage 0 precedes model work

A reflected image is equivalent to observing the scene from a virtual camera, but mirror
calibration has parity, handedness, plane-estimation, and degeneracy failure modes. A
small reprojection error can still hide a wrong reflected-camera convention. Stage 0
therefore uses a rigid 3D object with withheld check points before any deformable target
or animal is introduced.

Relevant starting references:

- Martins and Dias, *Camera calibration using reflections in planar mirrors and object
  reconstruction using volume carving method* (2004),
  <https://doi.org/10.1179/136821904225011609>.
- Takahashi, Nobuhara, and Matsuyama, *Mirror-based Camera Pose Estimation Using an
  Orthogonality Constraint* (2016),
  <https://doi.org/10.2197/ipsjtcva.8.11>.
- Juarez-Salazar, *Flat mirrors, virtual rear-view cameras, and camera-mirror
  calibration* (2024), <https://doi.org/10.1016/j.ijleo.2024.172067>.
- OpenCV's ChArUco calibration documentation,
  <https://docs.opencv.org/4.x/da/d13/tutorial_aruco_calibration.html>.

These references establish prior geometry and known calibration pitfalls. The proposed
contribution is not the existence of mirrors; it is an open, uncertainty-aware feline
benchmark capture protocol and its validation.

## Coordinate convention

The Stage 0 simulator and later Unity viewer use:

- `+x`: portal left to right;
- `+y`: from camera through the portal;
- `+z`: upward;
- metres for world coordinates;
- pixels for image coordinates;
- physical-camera frame: `+x` right, `+y` down, `+z` forward.

Every exported transform must state whether it maps `world -> camera` or
`camera -> world`. Mirrored observations also record whether parity correction has been
applied.

## Nominal capture volume

The first rigid-target experiment samples:

```text
width (x):  -0.30 m to +0.30 m
depth (y):  -0.05 m to +0.65 m
height (z): +0.05 m to +0.65 m
```

This is an engineering test volume, not a claim that every adult cat and tail will fit.
The final portal can expand after the optical noise floor is known.

## Camera class

Use one **colour global-shutter machine-vision camera** for the reference experiment:

- at least 1920 x 1200 active pixels;
- at least 60 frames per second at the selected resolution;
- manual gain, exposure, focus, and white balance;
- fixed, documented lens;
- uncompressed or minimally processed frames;
- per-frame timestamps;
- exposure settings short enough to compare a motion-frozen condition with an ordinary
  consumer-like condition.

Do not select the final lens by focal length alone. Select it after a field-of-view test
confirms that the direct region and reflected regions occupy enough pixels without
severe edge distortion.

A smartphone/rolling-shutter replication is a later benchmark condition, not the
reference measurement source.

## Mirror requirements

Use first-surface planar mirrors for the reference rig. Ordinary rear-surface household
mirrors introduce a second reflected path through glass and can create ghost edges that
invalidate subpixel calibration assumptions.

Record for every mirror:

- substrate and coating;
- nominal flatness if known;
- measured dimensions;
- plane pose and calibration timestamp;
- edge mask;
- scratches, flex, or mounting stress;
- temperature and any movement between calibration and capture.

Protect exposed edges and avoid any arrangement that can trap or contact an animal.
Stage 0 itself uses no animal.

# Candidate layouts

The dimensions below are starting points encoded in
[`stage0/layouts.json`](../stage0/layouts.json). They are deliberately adjustable.

## Layout A — symmetric lateral

```text
top view

                 capture volume
          /---------------------------\
 left mirror                       right mirror
             \                   /
              \                 /
                  physical camera
```

Nominal construction:

- frame: approximately 0.75 m wide x 1.20 m deep x 0.90 m high;
- two vertical first-surface mirrors, approximately 0.45 m x 0.80 m each;
- mirrored planes placed symmetrically around the direct view;
- one direct view plus two lateral reflected views.

Expected strengths:

- symmetric conditioning;
- simple construction and calibration comparison;
- good left/right coverage;
- straightforward direct-plus-one versus direct-plus-two ablation.

Expected weaknesses:

- all views remain near the same elevation;
- paws, back, and tail can share similar occlusion patterns;
- mirror area may compete with direct-view resolution.

## Layout B — lateral plus overhead

```text
side/front concept

             tilted overhead mirror
                    /
                   /
          capture volume ---- side mirror
                   |
             physical camera
```

Nominal construction:

- frame: approximately 0.75 m wide x 1.20 m deep x 1.20 m high;
- one vertical side mirror, approximately 0.45 m x 0.80 m;
- one tilted overhead mirror, approximately 0.70 m x 0.50 m;
- one direct, one lateral, and one elevated reflected view.

Expected strengths:

- greater baseline diversity;
- better conditioning for depth in some regions;
- complementary visibility for back, ears, tail curvature, and self-occlusion.

Expected weaknesses:

- less symmetric error;
- a larger enclosure;
- harder mirror support and masking;
- the overhead reflection may receive fewer usable pixels.

## Selection rule

Do not select a layout from simulated covariance alone.

Select the first physical layout using this priority order:

1. stable mirror calibration across teardown/reassembly;
2. low holdout-point error and calibrated uncertainty;
3. sufficient usable capture volume;
4. complementary visibility;
5. image area per view;
6. build simplicity and safety.

If Layout B provides materially better depth conditioning but unreliable mounting,
Layout A remains the reference rig and the overhead view becomes an optional extension.

# Rigid target

Build one asymmetric rigid 3D target approximately 300 mm across.

Recommended structure:

- three mutually orthogonal rigid faces;
- a ChArUco-style corner field on each face;
- unique face identities;
- non-coplanar points distributed through depth;
- at least eight **withheld holdout points** not used to estimate intrinsics, mirror
  planes, or virtual-camera poses;
- independently measured target coordinates and measurement uncertainty.

Reflection reverses image parity. For each mirror region, try both parity hypotheses
before fiducial decoding and retain the hypothesis that satisfies the registered mirror
geometry. Do not use a visually symmetric board that allows a reversed solution to look
correct.

Separate points into:

- `calibration`: used to estimate camera and mirror parameters;
- `validation`: used for model selection and debugging;
- `holdout`: used only for the final Stage 0 error report.

# Experiment sequence

## 0A — geometry conditioning

Run:

```bash
python -m pip install numpy
python stage0/geometry_sim.py \
  --config stage0/layouts.json \
  --output stage0/geometry-conditioning-report.json
```

The simulator compares direct plus one reflection and direct plus two reflections. It is
not a renderer and does not claim physical accuracy.

## 0B — intrinsic calibration

For each lens/focus configuration:

- capture at least 30 useful ChArUco views covering the sensor;
- include near, middle, and far target distances;
- report per-view error and parameter uncertainty;
- freeze focus and all lens settings;
- version the calibration file by camera serial, lens, resolution, and focus state.

## 0C — mirror-plane calibration

Estimate each mirror plane using direct and reflected observations of the rigid target.

Required checks:

- explicit reflected-image parity handling;
- correct virtual rear-view convention;
- independent plane estimate from multiple target poses;
- bundle adjustment over physical camera, mirror planes, and target poses;
- comparison against a separately measured mirror plane where practical.

## 0D — static volume sweep

Place the rigid target at a pre-registered grid:

- near, centre, and far depth;
- left, centre, and right;
- low, middle, and high;
- additional positions near every mirror boundary.

At every position, capture at least 100 frames without moving the rig.

Report:

- per-view reprojection residual;
- 3D holdout-point error;
- reconstructed rigid-distance error;
- frame-to-frame repeatability;
- calibration-to-calibration repeatability;
- error by region and axis;
- reflected-view dropout and boundary failure.

## 0E — controlled motion

Move the same target through the volume under two exposure conditions:

- short exposure intended to freeze motion;
- longer consumer-like exposure.

Use a repeatable path where feasible, such as a linear rail, turntable, pendulum, or
stepper-driven stage. When absolute trajectory is unavailable, rigid inter-point
distances and repeat-cycle consistency remain valid checks, but they do not establish
absolute trajectory truth.

Report:

- temporal jitter while stationary;
- rigid-distance variation while moving;
- lag and frame drop;
- sensitivity to speed and blur;
- uncertainty growth under motion.

## 0F — uncertainty estimation

Use two complementary estimates:

1. **Propagation:** perturb detected image points and calibrated parameters according to
   their estimated noise, then re-triangulate.
2. **Empirical repeatability:** repeat detection, calibration, placement, and
   reconstruction across independent trials.

For each reconstructed point, export a covariance matrix or another documented
confidence region. Validate 68% and 95% coverage against held-out measured points.
Uncertainty is rejected if it is merely monotonic with a model score but fails empirical
coverage.

## 0G — Unity parity check

The minimal Unity scene must show:

- physical camera;
- mirror planes;
- virtual camera centres;
- direct and reflected rays;
- target points and reconstructed points;
- residual vectors;
- covariance ellipsoids;
- capture-volume boundaries;
- coordinate axes and transform direction;
- parity state for each reflected view.

Unity and the offline calibration code must reconstruct the same test points within
floating-point tolerance. A visually plausible but convention-inconsistent scene fails
the stage.

# Metrics

Record at minimum:

- RMS and percentile reprojection error by view;
- median, p95, and maximum 3D holdout-point error;
- axis-wise error;
- rigid-distance error;
- reconstruction repeatability;
- calibration parameter repeatability;
- covariance coverage;
- error anisotropy;
- usable-volume fraction;
- reflected ROI pixel area;
- failure rate near mirror boundaries;
- static versus moving-target degradation.

# Pre-registered decision bands

These are engineering bands for the rigid target, not final feline-label accuracy.

## Go

- central-volume p95 holdout error <= 3 mm;
- full-volume p95 holdout error <= 5 mm;
- repeated-calibration p95 point displacement <= 2 mm;
- no unreported region with systematic error > 10 mm;
- nominal 95% uncertainty regions contain 90% to 98% of held-out observations;
- direct plus both reflections materially outperforms direct plus one reflection;
- the usable region is large enough for the next articulated-target experiment.

## Revise

- central p95 error > 3 mm and <= 6 mm;
- full-volume p95 error > 5 mm and <= 10 mm;
- instability is concentrated near documented boundaries;
- covariance is miscalibrated but error remains spatially predictable;
- one layout fails while the other remains viable.

Revise mirror angle, stiffness, field of view, target design, or calibration method and
repeat Stage 0.

## Stop this pathway

- full-volume p95 error remains > 10 mm after one documented redesign;
- calibration changes materially after ordinary handling;
- reflected-view parity or correspondence remains ambiguous;
- useful triangulation exists only in an impractically small region;
- uncertainty cannot identify failure regions;
- Unity and offline geometry cannot be reconciled.

Stopping the portal pathway does not stop the project. It redirects gold capture to a
different independent measurement design.

# Outputs

Stage 0 is complete only when the repository contains:

- physical rig diagram and measured dimensions;
- camera and lens metadata;
- intrinsic calibration artefacts;
- mirror-plane calibration artefacts;
- target design and measured coordinates;
- raw sequence manifests;
- reconstruction code;
- Unity validation scene;
- generated metric report;
- failure map;
- go/revise/stop decision;
- frozen thresholds for the next deformable-target stage.

# Explicit exclusions

Stage 0 does not:

- record cats;
- choose behavioural labels;
- validate latent skeletal joints;
- validate a monocular pose model;
- make health or welfare claims;
- establish the final consumer camera;
- treat the geometry simulation as measured evidence.
