# Intent-event field dictionary

This dictionary accompanies `schemas/intent-event.schema.json` version `0.1.0`. The schema is normative; this document explains intended semantics.

## Event identity

| Field | Meaning |
| --- | --- |
| `schema_version` | Exact intent-event schema version used to encode the record. |
| `event_id` | Stable identifier for this programme-level event record. |
| `subject_id` | Pseudonymous cat identifier. Must not require an animal's public name. |
| `household_id` | Pseudonymous household or study-site identifier. |
| `session_id` | Capture/observation session containing the episode. |
| `episode_id` | Behavioural episode joined across modalities. Multiple event records may refer to the same episode when protocols require different inference snapshots. |

## `time`

| Field | Meaning |
| --- | --- |
| `start_time`, `end_time` | Absolute RFC 3339 timestamps used for coarse joining and audit. |
| `start_offset_ms`, `end_offset_ms` | Milliseconds from the episode clock origin. Normally the programme record begins at zero. |
| `clock_source` | Clock or synchronisation source used for offsets. |
| `uncertainty_ms` | Declared timing uncertainty for the programme-level interval. |

## `observations[]`

Observation records are references to modality-specific data, not copies of it.

| Field | Meaning |
| --- | --- |
| `observation_ref` | Unique local reference used by hypotheses and analyses. |
| `modality` | Evidence family such as `visual_pose` or `audio_vocalisation`. |
| `schema_ref` | Schema/contract governing the referenced modality record. V1 uses `schemas/observation.schema.json`. |
| `record_ids` | IDs in the modality-specific dataset or record stream. |
| `source_uri` | Optional location of the source asset or record. Private URI schemes are permitted. |
| `start_offset_ms`, `end_offset_ms` | Observation interval in the episode clock. |
| `features` | Optional compact derived features for cross-thread experiments. Raw modality records remain authoritative. |
| `uncertainty` | Optional modality-reference uncertainty. Detailed uncertainty belongs in the modality schema. |

## `context`

| Field | Meaning |
| --- | --- |
| `location` | Observable room/zone/study location; `null` when unavailable. |
| `objects[]` | Relevant scene objects and observable state. |
| `objects[].object_id` | Stable local object reference. |
| `objects[].object_type` | Functional object category such as door, food bowl, toy, or support surface. |
| `objects[].state` | Observable state only; do not encode an inferred feline intention here. |
| `objects[].relation_to_subject` | Optional subject-relative relation. |
| `social[]` | Humans, cats, or other animals present in the episode. |
| `social[].entity_id` | Pseudonymous entity reference. |
| `social[].entity_type` | `human`, `cat`, `other_animal`, or `unknown`. |
| `social[].relationship` | Optional declared relationship, e.g. household member. |
| `social[].distance_m` | Optional measured/estimated distance. |
| `social[].orientation` | Optional relative orientation description. |
| `environment` | Extensible observable environment variables. |
| `routine` | Extensible routine/history variables available at inference time. |

## `hypotheses[]`

| Field | Meaning |
| --- | --- |
| `hypothesis_id` | Unique hypothesis identifier within the event. |
| `kind` | `human_label`, `latent_state`, or `unknown`. |
| `label` | Human-readable interpretation. Required only for `human_label`. |
| `state_ref` | Learned/discovered latent-state ID. Required only for `latent_state`. |
| `probability` | Declared probability or calibrated score in `[0, 1]`; protocol defines whether competing entries are normalised. |
| `source` | Whether the hypothesis came from a prior, model, human, or derived analysis. |
| `calibration_model` | Optional identifier for the calibration procedure/model. |
| `evidence_refs` | Observation references used to produce the hypothesis. |

`unknown` is a real hypothesis state. It must not carry a human label or latent-state ID.

## `human_actions[]`

| Field | Meaning |
| --- | --- |
| `action_id` | Unique action identifier within the event. |
| `action_type` | Observable action, e.g. `open_door`, `present_toy`, `speak_name`. |
| `offset_ms` | Action time in the episode clock. |
| `actor_id`, `target_id` | Optional pseudonymous actor and target references. |
| `parameters` | Extensible observable action parameters. |

Logging an action does not make it an intervention. It becomes an intervention only when prospective competing predictions are declared.

## `interventions[]`

| Field | Meaning |
| --- | --- |
| `intervention_id` | Unique prospective test identifier. |
| `action_ref` | Reference to the concrete human action used as the intervention. |
| `candidate_hypotheses` | At least two hypotheses intended to be discriminated. |
| `predictions[]` | Prospectively declared expected responses. |
| `predictions[].hypothesis_ref` | Candidate hypothesis the prediction belongs to. |
| `predictions[].expected_response` | Observable expected consequence, not an interpretation written after seeing the result. |
| `predictions[].response_window_ms` | Optional time window for scoring the prediction. |
| `selection_policy` | Optional policy that chose the intervention. |
| `safety_class` | Currently fixed to ordinary low-risk household action. |

## `outcomes[]`

| Field | Meaning |
| --- | --- |
| `outcome_id` | Unique outcome identifier. |
| `outcome_type` | Immediate response, signalling termination, delayed outcome, no change, contradictory result, or unknown. |
| `start_offset_ms`, `end_offset_ms` | Outcome scoring interval. |
| `observation_source` | How the outcome was observed/scored. |
| `description` | Optional factual description of what happened. |
| `supports_hypotheses` | Hypothesis refs consistent with the prospectively declared scoring rule. |
| `contradicts_hypotheses` | Hypothesis refs contradicted under that rule. |
| `signalling_terminated` | `true`, `false`, or `null` when termination is not known/applicable. |

Null and contradictory outcomes are retained; they are not discarded as failed translations.

## Missingness and uncertainty

| Field | Meaning |
| --- | --- |
| `missing_modalities` | Explicit list of unavailable evidence channels. Missing data is legal and should not be silently imputed. |
| `uncertainty.episode_confidence` | Optional programme-level confidence summary. |
| `uncertainty.notes` | Optional explanation of uncertainty not captured structurally. |

## `provenance`

| Field | Meaning |
| --- | --- |
| `source_ids` | Stable source assets/records from which the programme event was constructed. |
| `lineage` | Ordered derivation/processing history. |
| `annotation_source` | Observed, human-annotated, model-inferred, synthetic, derived, or mixed. |
| `annotator_ids` | Optional pseudonymous annotator references. |
| `software_versions` | Optional exact software/model/schema versions used to generate the record. |

## `privacy`

| Field | Meaning |
| --- | --- |
| `data_class` | Synthetic, public, consented research, or private household. |
| `consent_status` | Not applicable, recorded, pending, or restricted. |
| `consent_record_id` | Reference to the governing consent record when applicable. |
| `retention_policy` | Reference/name of the applicable retention policy. |
| `contains_human_audio` | Whether human audio may be present. |
| `contains_human_image` | Whether human imagery may be present. |

Privacy fields describe handling metadata; they do not by themselves establish ethical approval, consent sufficiency, or permission to publish.
