# Observable topology — DRAFT v0.1

**Status:** direction resolved; exact pilot targets remain open.

The canonical benchmark representation should describe what can actually be observed:
points, curves, regions, contacts, visibility, and uncertainty. A conventional fixed
keypoint skeleton remains available as a compatibility export.

## Design rules

1. **Prefer visible surface anatomy over hidden joint centres.**
2. **Represent deformable structures as curves or regions when points discard the
   signal.**
3. **Do not force an exact label when the feature is occluded or anatomically ambiguous.**
4. **Store left/right semantic identity separately from image order.**
5. **Permit task-specific detail:** full-body footage and close facial footage need not
   expose identical landmark density.
6. **Preserve compatibility through exports, not by weakening the canonical format.**
7. **Every target carries visibility, evidence tier, quality, and uncertainty.**

## Canonical target families

### Face and head

#### Pilot-required

- `nose_tip`
- `left_eye_outer`
- `left_eye_inner`
- `right_eye_inner`
- `right_eye_outer`
- `chin_visible`
- `head_crown_visible`

Eye corners support eye aperture and blink measurements when image resolution permits.
`chin_visible` and `head_crown_visible` are surface targets, not claims about internal
head axes.

#### Optional close-range face profile

A later face-specific profile may add eyelid, muzzle, mouth, and whisker-pad boundaries.
These points should not be required in wide full-body footage where they are not
resolvable.

### Ears

Each ear requires enough geometry to distinguish orientation and deformation rather than
one undifferentiated “ear point”.

Pilot candidates per ear:

- `ear_tip`
- `ear_base_rostral_visible`
- `ear_base_caudal_visible`
- optional sampled outer boundary curve

The base targets are explicitly visible surface locations. Long fur, viewpoint, or
self-occlusion may make one or both unavailable; this becomes missing or uncertain data,
not a guessed exact point.

Derived measurements may include:

- ear direction in image or world coordinates;
- left/right ear angular difference;
- flattening proxy from visible geometry;
- angular velocity and flick timing.

### Body surface and centreline

Pilot candidates:

- `neck_dorsal_visible`
- `withers_visible`
- `spine_mid_visible`
- `sacrum_visible`
- optional dorsal centreline curve
- body silhouette or mask

These targets support posture and curvature without claiming exact vertebral centres.
The silhouette remains important because fur and body deformation cannot be represented
fully by a sparse skeleton.

### Limbs and paws

For each limb, pilot candidates include externally resolvable surface locations:

- upper-limb or shoulder/hip surface anchor;
- elbow or stifle visible centre;
- carpus or hock visible centre;
- paw centre or paw contact region.

Names must distinguish `*_visible` surface observations from optional `*_joint_estimate`
latent anatomy.

Paw contact is represented separately from paw appearance because an instrumented or
underside view may know contact precisely even when the paw is partly hidden in the
ordinary camera.

### Tail

The canonical tail representation is an ordered centreline curve:

```text
tail_base_anchor
+ ordered visible/estimated curve samples
+ tail_tip when resolvable
```

Each sample may have its own visibility, evidence tier, and uncertainty. The curve may be
stored as:

- sampled 2D/3D points at normalised arc-length positions; or
- a documented spline with control-point uncertainty.

Derived measurements may include:

- elevation and direction;
- arc length visible;
- local and integrated curvature;
- curvature change;
- tip velocity;
- travelling wave or isolated flick timing.

A fixed three- or five-point tail chain is generated only for model compatibility.

### Contact and support

Canonical contact observations are events or regions, not keypoints:

- paw identity;
- contact region;
- start and end time with temporal uncertainty;
- support-surface identifier;
- take-off or landing role;
- optional pressure or force values where independently measured.

### Scene-relative targets

Where a scene map is available:

- camera pose distribution;
- subject root or surface trajectory;
- floor and support surfaces;
- contact surface relation;
- obstacle and occluder identity;
- object-relative relations.

Scene-derived coordinates inherit map and calibration uncertainty.

## Latent anatomical profile

Hidden joint centres may be exported under explicit names such as:

- `left_shoulder_joint_estimate`
- `left_hip_joint_estimate`
- `left_stifle_joint_estimate`

These observations must use an inferred evidence tier and carry a distribution or
confidence region. They are optional in v0 and cannot be evaluated as independent gold
unless a separate anatomical measurement validates them.

## Compatibility export

A compatibility adapter may emit a conventional quadruped keypoint array for existing
pose frameworks. It should:

- map canonical surface observations to the closest declared semantic target;
- mark unavailable or non-equivalent targets explicitly;
- export tail base/mid/tip samples from the canonical curve;
- avoid fabricating hidden joints merely to fill every array position;
- document any dependence on an external dataset ontology or licence.

Compatibility order is not the canonical ontology. It may change without recollecting
data as long as source observations remain intact.

## Proposed pilot subset

The smallest portal pilot should attempt:

- nose and four eye corners when visible;
- three surface targets per ear;
- dorsal neck, withers, spine midpoint, and sacrum targets;
- visible distal limb points and paw centres;
- paw-contact regions where available;
- tail base and centreline curve;
- body mask;
- visibility and covariance for every target.

This is deliberately not yet a frozen numbered list. The rigid-object and articulated
object experiments must establish whether the mirror geometry can measure the intended
precision and whether each target has an operationally repeatable definition.

## Annotation questions to resolve

1. Which ear-base surface locations can independent annotators identify consistently?
2. Should eye aperture be represented by corner points, eyelid curves, a scalar, or more
   than one of these?
3. Which limb surface landmarks remain repeatable across coat types?
4. What tail sampling density captures curvature without creating unstable labels?
5. How are curve samples matched through self-occlusion and topology ambiguity?
6. Which targets become absent rather than inferred after a visibility threshold?
7. Which compatibility formats are worth supporting in v0?
8. What minimum image scale is required for each target family?

## Freeze condition

The pilot topology may be frozen only after:

- written operational definitions exist;
- repeated annotation or measurement estimates uncertainty;
- rigid and articulated tests confirm sufficient geometry;
- the portal pilot demonstrates that targets can be captured without coercion;
- the compatibility export can be generated without silently inventing labels.
