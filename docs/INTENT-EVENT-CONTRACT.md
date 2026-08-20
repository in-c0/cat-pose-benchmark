# Shared multimodal intent-event contract

**Schema:** `schemas/intent-event.schema.json`  
**Version:** `0.1.0`  
**Programme issue:** #18

## Purpose

The intent-event record is the cross-thread integration contract for the feline-intent research programme. It joins observations from different modalities into one episode without requiring those modalities to share a sampling rate, feature representation, or model.

The record deliberately separates three layers:

1. **observations and context** — what was measured or recorded;
2. **hypotheses** — probabilistic interpretations, including latent or unknown states;
3. **interventions and outcomes** — prospective tests and what observably happened next.

A plausible human-readable interpretation is therefore never treated as raw ground truth.

## Identity and time

Each record has stable pseudonymous identifiers for subject, household, session, episode, and event. `time` contains both absolute timestamps and offsets from the episode origin. Modality records use episode-relative millisecond intervals so asynchronous streams can be joined without forcing a shared frame rate.

## Observation references

`observations[]` references modality-specific records rather than embedding or replacing them. Each reference declares:

- modality;
- schema or contract used by the referenced record;
- one or more record IDs;
- interval within the episode;
- optional source URI, features, and modality-specific uncertainty.

For V1 pose/motion data, `schema_ref` should be `schemas/observation.schema.json` and `record_ids` should point to the existing V1 observation records. The programme contract does not rewrite V1 geometry or provenance.

## Context

`context` stores observable episode conditions such as location, object state, social configuration, environmental state, and routine variables. Context is first-class because time, location, object state, and identity can be stronger baselines than nominally sophisticated sensor models.

## Hypotheses

Every event includes at least one hypothesis. A hypothesis can be:

- `human_label` — a declared human-readable interpretation;
- `latent_state` — a model-discovered state such as `Z17`;
- `unknown` — explicit abstention / unresolved state.

Each hypothesis has a probability in `[0, 1]` and a source. The schema does not require probabilities to sum to one because some experiments may report independently calibrated hypotheses; each protocol must state its probability semantics.

Human labels and latent-state IDs are optional by design. `unknown` is not allowed to carry either field.

## Human actions, interventions, and outcomes

Ordinary human actions can be logged in `human_actions`. A subset can be promoted to a prospective `intervention` when it is used to discriminate between at least two candidate hypotheses.

An intervention records:

- the referenced action;
- competing hypotheses declared before outcome scoring;
- expected responses for those hypotheses;
- the selection policy;
- the fixed low-risk household safety class.

`outcomes` records observable responses separately from the hypothesis layer. Outcomes can support or contradict hypotheses, but null, contradictory, and unknown outcomes remain legal records.

## Missingness and uncertainty

`missing_modalities` explicitly records absent sensor families. Missing modalities are legal. A pose-only event, audio-only event, and multimodal event all validate under the same schema.

Uncertainty can be represented at episode and observation-reference levels. Modality-specific schemas remain responsible for their detailed uncertainty models.

## Provenance and privacy

Every event requires source IDs, lineage, and annotation source. Privacy metadata declares the data class and consent status and can flag human audio/image presence. This field is metadata, not a substitute for a research ethics or data-governance protocol.

## Examples

- `examples/intent-events/pose-only.json` — V1 observation references with every intent hypothesis abstaining to unknown.
- `examples/intent-events/audio-only.json` — A1-style vocalisation record with calibrated candidate hypotheses and no visual stream.
- `examples/intent-events/multimodal-intervention.json` — visual + audio + context episode with a preregistered low-risk intervention and observable outcomes.

All example probabilities and episode contents are illustrative fixtures unless explicitly linked to a released dataset.

## Validation

Run:

```bash
python -m programme.validate_intent_event examples/intent-events/pose-only.json
python -m unittest programme.test_intent_event_schema
```

CI validates the schema itself, all fixtures, and negative cases that enforce the programme boundaries.

## Versioning policy

The schema uses semantic versioning in `schema_version`.

- **Patch**: documentation or validator corrections that do not change accepted records.
- **Minor**: backwards-compatible additions, such as optional fields or new enum values where consuming code is required to tolerate unknown values.
- **Major**: removal/renaming of fields, changed required fields, changed probability semantics, or any change that makes previously valid programme records invalid.

Released datasets must record the exact schema version. A migration note and machine-testable migration path are required before a major version becomes the programme default.

## Cross-field checks beyond JSON Schema

JSON Schema validates structure, not every programme invariant. The validator also checks:

- episode end is not before episode start;
- observation intervals remain within the episode;
- hypothesis IDs are unique;
- intervention action refs exist;
- intervention hypothesis refs exist;
- every preregistered prediction points to a candidate hypothesis;
- outcome support/contradiction refs exist;
- probabilities are finite.

Future protocol-specific validators may add stronger requirements such as probability normalisation, split leakage checks, temporal synchronisation tolerance, or per-thread provenance gates.
