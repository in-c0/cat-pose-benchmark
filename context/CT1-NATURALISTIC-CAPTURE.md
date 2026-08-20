# CT1.2 — prospective naturalistic capture contract

CT1.2 is the first prospective-data preparation step after CT1.1. It does **not** collect or infer feline intent by itself. It freezes what must exist at prediction time so later context/routine results cannot be explained by retrospective annotation.

## Core change from CT1.1

CT1.1 treated the shared event record's top-level `context` as a prediction-time snapshot. That was acceptable for synthetic instrumentation, but the field itself has no timestamp.

CT1.2 therefore requires exactly one observation with:

- `modality = object_environment`;
- `schema_ref = context/ct1_context_snapshot.schema.json`;
- `start_offset_ms = 0`;
- `end_offset_ms = 0`;
- `features.captured_at == event.time.start_time`.

The timestamped snapshot and top-level `context` must agree on location, objects, social state and environment. Strict CT1 extraction reads context from the validated snapshot rather than trusting the untimestamped field.

## Capture sequence

For a naturally occurring episode:

1. **Episode start (`t0`)**
   - allocate `event_id`, `episode_id`, subject/household/session pseudonyms;
   - freeze system timestamp;
   - record the CT1 context snapshot immediately;
   - record capture provenance/source IDs.

2. **Observation window**
   - optional vocal audio, visual pose/microstate and environmental audio may be attached as separate observation references;
   - their absence remains explicit in `missing_modalities`;
   - CT1 passive predictors remain frozen at `t0`.

3. **Naturally occurring human actions**
   - ordinary household actions may be recorded with offsets;
   - they are **not** CT1 pre-action predictors;
   - if used for I1, its prospective hypothesis/prediction requirements apply separately.

4. **Outcome window**
   - append directly observable outcomes after they occur;
   - first CT1 target is `signalling_terminated`;
   - adding the outcome must never rewrite the `t0` snapshot.

5. **History**
   - routine/history features are derived programmatically from earlier timestamped events;
   - do not type retrospective `time_since_*` values into the record.

## Minimum context snapshot

Record only observable state:

- coarse location zone;
- relevant objects/access routes and their current state;
- people/other animals present;
- coarse distance/orientation only when directly measured/annotated;
- environmental fields that are actually observed;
- source IDs and capture method.

Do not insert inferred intention, mood, satisfaction, pain, or semantic translations into this snapshot.

## First household pilot

A first household is an instrumentation and longitudinal-sensitivity study, not population evidence.

Recommended initial target:

- 30–50 naturally occurring signalling episodes;
- chronological blocked evaluation;
- fixed 60 s termination window where observable;
- no manufactured hunger, denied access, teasing, confinement, startle or delayed necessities;
- preserve all eligible episodes, including `unknown`, null and contradictory outcomes.

The initial episode count is a practical instrumentation target, not a power claim. A formal sample-size plan should be based on the observed event prevalence/autocorrelation after the first non-evaluative capture tranche.

## Low-burden recording

The software should do as much timestamping as possible automatically. For the first pilot, manual burden should be limited to fields that sensors cannot reliably establish, such as coarse location/object state when no scene model is available.

Do not require the household member to choose an intent label.

## Privacy

Naturalistic capture may include human voice/image. Before any real recording:

- record consent/retention policy in the shared privacy fields;
- keep human media private by default;
- publish derived aggregate research records only when their provenance/licence/privacy permits it;
- separate research-only recordings from any later commercial training corpus.

## Readiness gate

CT1.2 instrumentation is software-ready when:

1. the timestamped snapshot schema validates;
2. shared #18 validation also passes;
3. duplicate/post-cutoff/mismatched snapshots fail;
4. strict extractor derives context only from the timestamped snapshot;
5. appending an outcome leaves predictors byte-equivalent;
6. CI exercises the pre-outcome and completed example.

Actual prospective collection remains a separate owner-operated step.
