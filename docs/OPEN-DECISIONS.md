# Open decisions — software-first release hold list

**Status:** the software-first research direction is approved. No owner-operated physical
capture, rig construction, or fabrication is required for Protocol v0.1.

Ordered by how expensive they are to get wrong.

---

## Resolved direction decisions

| Decision | Resolution |
|---|---|
| Benchmark purpose | Evaluate monocular feline visual intelligence through exact Unity simulation, observable real video, uncertainty-aware reconstruction, and optional external hidden gold |
| Ground-truth model | Per-observation provenance and time-varying uncertainty; no single equally certain skeleton per frame |
| Evidence tiers | Tier S synthetic exact, Tier R2 real observable, Tier R3 reconstructed estimate, Tier G external hidden gold |
| Observable versus latent anatomy | Visible surfaces, curves, contact evidence, and scene observations are separated from inferred hidden joints |
| Physical-work policy | Lead developer performs no bespoke capture, rig construction, calibration-lab work, or hardware fabrication; ordinary product use testing remains allowed |
| Synthetic data | Primary exact-data and controlled-evaluation source for v0.1, but never presented as real-world validation |
| Real data | Licence-clean or consented video evaluated only on externally observable variables unless independent measurements exist |
| External gold | Optional later acceptance gate operated by a partner; not a v0.1 implementation dependency |
| Portal work | Retained as an optional external-validation design study, not the project’s critical path |
| Behaviour scope | No pain, health, welfare, diagnostic, literal translation, or universal ethogram claim in benchmark v0 |
| First public unit | Protocol v0.1, deterministic Unity sequence and exporter, one real observable sequence, Unity viewer, and baseline evaluation |

See [RESEARCH-CHARTER.md](RESEARCH-CHARTER.md),
[SOFTWARE-FIRST-ROADMAP.md](SOFTWARE-FIRST-ROADMAP.md),
[GROUND-TRUTH-PROVENANCE.md](GROUND-TRUTH-PROVENANCE.md), and
[EXTERNAL-VALIDATION-CONTRACT.md](EXTERNAL-VALIDATION-CONTRACT.md).

---

## Tier 1 — must be resolved before implementation assets are committed

| # | Decision | Why it locks | Current position |
|---|---|---|---|
| 1 | **Pilot landmark and curve ontology** | Changing semantic targets invalidates exporters, labels, and metrics | Prioritise visible surface points, detailed ears/face, paws, body centreline, and tail spline; latent joints optional |
| 2 | **Rigged feline asset and animation rights** | Asset restrictions can contaminate rendered data, code examples, screenshots, and trained weights | Use only assets whose terms permit the intended rendered-data release and downstream model use; otherwise create or commission a clean asset |
| 3 | **Unity coordinate and unit contract** | All annotations, viewers, and baselines depend on consistent transforms | Use metres and one documented world/camera/image convention with round-trip tests |
| 4 | **Annotation export format** | Export structure locks synthetic generation and baseline ingestion | Extend the observation schema rather than create an unrelated synthetic-only format |
| 5 | **Determinism contract** | Exact regression claims require controlled seeds and reproducible export | Record engine version, asset version, seed, timestep, render settings, and platform-dependent tolerances |
| 6 | **Outbound licences** | Contributors, assets, generated data, and downstream product use depend on them | Still unresolved; no public data, weights, or reusable code until set |

## Tier 2 — resolve before Protocol v0.1 release

| # | Decision | Current position |
|---|---|---|
| 7 | **Canonical topology versus compatibility export** | Canonical representation may use curves and regions; conventional keypoints are an export |
| 8 | **Synthetic variation set** | Define the smallest credible morphology, motion, camera, lighting, blur, clutter, and occlusion matrix |
| 9 | **Physical validity checks in simulation** | Reject impossible anatomy, penetration, foot sliding, and unstable tail topology |
| 10 | **First real-video source** | Must be licence-clean or explicitly contributed with machine-readable rights |
| 11 | **Observable reviewer protocol** | Define sparse keyframes, propagation, visibility, ambiguity, disagreement, and adjudication |
| 12 | **Uncertainty representation** | Points: covariance or documented confidence region; curves: local covariance or parameter distribution |
| 13 | **Monocular baseline** | Select a commercially usable implementation; its own pseudo-labels cannot be its sole reference |
| 14 | **Metrics and gates** | Freeze exact synthetic tolerances, temporal metrics, transfer metrics, and real observable reviewer thresholds |
| 15 | **Unity viewer scope** | Extend current geometry viewer to synthetic sequences, exact labels, predictions, uncertainty, and failure comparison |
| 16 | **Scene-mapping backend** | Evaluate separately from feline pose; mapping uncertainty remains explicit |
| 17 | **Forbidden claims language** | Public documentation must distinguish observed signal, hypothesis, entertainment copy, and unsupported medical claims |

## Tier 3 — external validation decisions

| # | Decision | Current position |
|---|---|---|
| 18 | **Tier G custody mode** | Public release, private labels, remote evaluator, or escrow evaluation |
| 19 | **Measurement class** | Partner may use synchronized cameras, Vicon, RGB-D, pressure, mirrors, or another traceable system |
| 20 | **Partner and attribution terms** | Define publication, authorship, costs, data custody, and withdrawal |
| 21 | **External gold thresholds** | Freeze only after the partner measurement noise floor is documented; never tune on model test results |

Tier G decisions do not block v0.1.

## Tier 4 — deferred product and programme decisions

| # | Decision |
|---|---|
| 22 | Consumer brand name |
| 23 | Translator app repository and launch scope |
| 24 | Edge puck compute platform and camera |
| 25 | Hardware accelerator/RTL demonstration target |
| 26 | Contract manufacturer or hardware-development partner |
| 27 | Future veterinary collaboration and health-validation programme |
| 28 | Paper venue and release timing |
| 29 | Wider contributor and shelter recruitment strategy |

---

## Unresolved external dependencies

- **Model and checkpoint licensing.** Code and weights can carry different terms. Every
  baseline, teacher, tracker, mapper, and reconstruction checkpoint needs explicit review.
- **Rigged assets and rendered-data rights.** Source terms must permit the planned rendered
  derivatives and downstream model use. Do not assume that owning or downloading an asset
  grants dataset rights.
- **Real-video rights.** Platform availability does not imply redistribution or training
  permission. Sequence-level evidence is required.
- **External partner availability.** Lack of Tier G access restricts claims but does not
  block synthetic, observable-real, temporal, transfer, or entertainment-product work.

---

## Standing constraints

- No scraping or rights-by-assumption.
- No CC BY-NC, research-only, or licence-ambiguous dependencies in released data or
  production paths.
- No model family is evaluated solely against labels generated by that family.
- Synthetic exactness is not real-world ground truth.
- Hidden anatomy is labelled as inferred unless independently measured.
- Benchmark uncertainty varies with actual observability.
- No owner-operated research rig, calibration apparatus, or product fabrication enters
  the critical path.
- External measurement results remain separate from synthetic and model-derived scores.
- No medical, veterinary, welfare, or diagnostic claims from benchmark v0.
- No literal semantic translation claim.
- Coverage gaps, failed generations, failed annotations, and excluded cases are disclosed.
