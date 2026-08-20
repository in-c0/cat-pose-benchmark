# I1 intervention/outcome validation protocol

**Status:** I1.0 protocol v0.1  
**Parent issue:** #20  
**Programme contract:** `schemas/intent-event.schema.json`

## Question

Can prospective feline-state hypotheses make measurably different predictions about a cat's response to safe, ordinary household actions?

I1 does not treat an intervention as revealing a literal hidden sentence. It tests predictive adequacy.

## Episode eligibility

Use naturally occurring episodes initiated by the cat or clearly visible changes in behaviour. Examples include spontaneous approach/vocalisation, repeated movement between a person and a location/object, voluntary play initiation, or signalling around an already-due routine.

Do not manufacture labels through deprivation, confinement, startle, teasing, delayed necessities, restraint, or aversive stimuli.

## Prospective plan rule

Every scored intervention requires an `i1-plan` record produced before the action.

The validator enforces:

- `recorded_offset_ms < action.scheduled_offset_ms`;
- at least two candidate hypotheses;
- unique hypothesis IDs;
- hypothesis probabilities sum to 1;
- every candidate hypothesis has a prediction block;
- predictions cannot reference undeclared hypotheses;
- food actions are legal only when `feeding_due=true`;
- no-action observation is short and only when no necessary care is pending;
- expected-information-gain selection is reserved for I1.2.

The plan can then be referenced in event provenance/source lineage so the later outcome cannot silently rewrite the earlier hypothesis set.

## Phases

### I1.0 — measurement feasibility

Use naturally occurring ordinary actions. Establish that plans, actions, response windows, and outcomes can be captured consistently. Do not optimise action selection.

### I1.1 — controlled safe comparison

Where multiple actions are simultaneously safe and genuinely interchangeable, use a predeclared balanced or randomised schedule. Do not randomise care requirements.

### I1.2 — active information gain

Only after I1.0/I1.1 demonstrate usable predictive signal may an active policy select among the predeclared welfare-safe action set using expected information gain.

## Initial hypothesis vocabulary

- `access_location`
- `social_contact`
- `play_engagement`
- `routine_food_related`
- `object_interest`
- `latent_state`
- `unknown`

These are operational hypotheses. The programme can retain stable latent-state identifiers rather than forcing a human semantic label.

## Safe action vocabulary

- `offer_social_contact`
- `present_toy`
- `open_permitted_access`
- `interact_relevant_object`
- `continue_due_feeding_routine`
- `brief_no_action_observation`

The machine-readable source is `intervention/i1-vocabulary.json`.

## Response windows

- immediate: 0–5 s;
- short: 5–30 s;
- episode outcome: 30–60 s;
- delayed recurrence only when declared prospectively.

## Primary observable outcomes

Prefer direct observables such as:

- approach/withdrawal;
- target orientation;
- threshold crossing;
- voluntary social engagement;
- toy engagement;
- object engagement;
- vocalisation continuation;
- signalling termination;
- location transition.

Descriptions such as “looked satisfied” are not primary outcome labels.

## Analysis

There is no assumed directly observed `true_intent`. Compare the predictive quality of:

1. passive context/statistical response prediction;
2. hypothesis-conditioned response prediction;
3. intervention + hypothesis-conditioned response prediction;
4. unknown/abstention handling.

Use action-specific held-out probability scores and calibration where sample size permits. Do not pool incompatible actions into one misleading headline accuracy.

## Anti-storytelling safeguards

- freeze hypotheses before the action;
- freeze action-specific response predictions before the action;
- timestamp plan and action;
- retain every eligible recorded episode, including null and contradictory outcomes;
- never relabel the winning hypothesis after seeing the response;
- keep `unknown` legal;
- outcome coding should be blind to the preferred hypothesis where feasible.

## Safety gates

Stop or exclude an intervention on distress, panic, aggression escalation, persistent avoidance, necessary-care delay, restraint, forced contact, unsafe access, aversive stimulation, or medical/veterinary interference.

Ordinary care always overrides experimental completeness.

## I1.0 completion gate

Before moving to I1.1:

- prospective-plan validation is automated;
- at least one #18 event demonstrates a valid plan → action → observable outcome lineage;
- a null/contradictory outcome fixture is retained;
- outcome coding can be reproduced from the raw event record;
- no active information-gain policy is enabled.
