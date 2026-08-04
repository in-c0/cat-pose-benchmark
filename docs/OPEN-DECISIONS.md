# Open decisions — collection hold list

**Status:** the research direction and Stage 0 rigid-target experiment are specified.
Software-only geometry work may proceed. Real-animal collection remains blocked by the
Tier 1 decisions below.

Ordered by how expensive they are to get wrong.

---

## Resolved direction decisions

| Decision | Resolution |
|---|---|
| Benchmark purpose | Evaluate monocular feline visual intelligence using a compact independently measured gold subset plus a real-home challenge set |
| Ground-truth model | Per-observation provenance and time-varying uncertainty; no single equally certain skeleton per frame |
| Observable versus latent anatomy | Visible surface, curves, contact, and scene observations are separated from inferred hidden joints |
| Multi-view role | Simultaneous views are for a small reference subset, not the consumer product |
| Preferred capture concept | Investigate a one-camera catadioptric portal with calibrated mirrors; optional transparent or instrumented floor |
| Stage 0 layouts | Compare symmetric lateral mirrors against a lateral-plus-overhead configuration before construction is frozen |
| Stage 0 camera class | Use a colour global-shutter machine-vision camera as the reference source; consumer rolling-shutter capture is a later replication condition |
| Stage 0 target | Use an asymmetric non-coplanar rigid target with separate calibration, validation, and holdout points |
| Stage 0 decision bands | Pre-register go/revise/stop bands before physical calibration; do not tune thresholds on feline results |
| Synthetic data | Supplementary training and ablation source, not the sole methodological core or real-world validation |
| Behaviour scope | No behaviour, pain, health, welfare, diagnostic, or literal translation claims in benchmark v0 |
| First public unit | Protocol v0.1, one small validated capture experiment, observation schema, Unity viewer, and baseline |

See [RESEARCH-CHARTER.md](RESEARCH-CHARTER.md),
[GROUND-TRUTH-PROVENANCE.md](GROUND-TRUTH-PROVENANCE.md), and
[STAGE-0-PORTAL-GEOMETRY.md](STAGE-0-PORTAL-GEOMETRY.md).

---

## Tier 1 — must be resolved before real-animal collection

| # | Decision | Why it locks | Current position |
|---|---|---|---|
| 1 | **Pilot landmark and curve ontology** | Changing semantic targets after capture invalidates labels and metrics | Prioritise visible surface points, detailed ears/face, paws, and tail centreline; latent joints optional |
| 2 | **Portal optical design** | Determines view baselines, capture volume, occlusion pattern, and calibration method | Two candidate layouts and nominal geometry are committed; physical rigid-target validation remains required |
| 3 | **Contact design** | Floor material and instrumentation may change gait and construction | Start with transparent/underside visual contact unless sensing is demonstrably non-intrusive |
| 4 | **Geometric acceptance thresholds** | Must be set before seeing feline results | Stage 0 rigid-object decision bands are pre-registered; final gold-label uncertainty rules must be frozen after physical noise-floor measurement and before feline capture |
| 5 | **Sourcing, consent, and contributor terms** | Rights and withdrawal conditions cannot be retrofitted safely | Self-recorded pilot first; public contribution only after reviewed templates exist |
| 6 | **Outbound licences** | Contributor permissions and downstream product use depend on them | Still unresolved; no public data or weights until set |
| 7 | **Ethics and welfare review path** | The portal must be voluntary and non-coercive, and institutional requirements may apply | Determine requirements before recording beyond ordinary owner footage |

## Tier 2 — resolve before Protocol v0.1 release

| # | Decision | Current position |
|---|---|---|
| 8 | **Canonical topology versus compatibility export** | Canonical representation may use curves and surface regions; conventional keypoints are an export |
| 9 | **Uncertainty representation** | Points: covariance or documented confidence region; curves: local covariance or parameter distribution |
| 10 | **Gold/silver/bronze assignment rules** | Must be per observation or interval, not only per sequence |
| 11 | **Minimum frame rate and exposure metadata** | Stage 0 reference class is >=60 FPS with manual exposure; final deployment strata remain unresolved |
| 12 | **Monocular baseline** | Select a licence-clean implementation; model-generated labels cannot be its sole reference |
| 13 | **Metrics and pilot gates** | Rigid-target gates are specified; feline surface/temporal gates require ontology and measured Stage 0 noise |
| 14 | **Unity viewer scope** | Stage 0 view is specified: cameras, mirrors, rays, residuals, covariance, boundaries, axes, and parity; implementation remains open |
| 15 | **Scene-mapping backend** | Evaluate separately from dynamic cat reconstruction; map uncertainty must remain explicit |

## Tier 3 — deferred product and programme decisions

| # | Decision |
|---|---|
| 16 | Consumer brand name |
| 17 | Translator app repository and launch scope |
| 18 | Edge puck compute platform and camera |
| 19 | Hardware accelerator/RTL demonstration target |
| 20 | Future veterinary collaboration and health-validation programme |
| 21 | Paper venue and release timing |
| 22 | Wider contributor and shelter recruitment strategy |

---

## Unresolved external dependencies

- **AP-10K licence conflict.** The source repository and secondary listings reportedly
  disagree. Do not use it until the authors or rights-holder confirms applicable terms
  in writing and the evidence is committed.
- **Model and checkpoint licensing.** Code and weights can carry different terms. Every
  baseline, teacher, tracker, mapper, and reconstruction checkpoint needs an explicit
  production and redistribution review.
- **Rigged assets and rendered-data rights.** If synthetic data is released, source asset
  terms must explicitly permit redistribution of rendered derivatives and downstream
  trained weights.
- **Animal-research requirements.** Confirm whether the proposed voluntary portal capture
  is ordinary owner recording, institutional animal research, or another regulated
  category in the relevant jurisdiction and institution.

---

## Standing constraints

- No scraping or rights-by-assumption.
- No CC BY-NC, research-only, or licence-ambiguous dependencies in released data or
  production paths.
- No model family is evaluated solely against labels generated by that family.
- Synthetic exactness is not real-world ground truth.
- Hidden anatomy is labelled as inferred unless independently measured.
- Benchmark uncertainty must vary with actual observability; it cannot be one global
  confidence score.
- Geometry-conditioning simulations are design aids, not measured ground truth.
- No animal capture occurs before the portal, consent, licence, and ethics gates are met.
- No medical, veterinary, welfare, or diagnostic claims from benchmark v0.
- No literal semantic translation claim.
- Coverage gaps, failed captures, and excluded cases are disclosed.
