# Feline intent research programme

**Status:** public research direction v0.1  
**Date:** 2026-08-21

## Premise

A cat-intent system should not be defined as `pose -> English sentence`.

Intent, affect, need, preference, and communicative state are latent variables. They may produce many observable consequences at once: vocalisations, gaze, ear and tail motion, object-directed behaviour, location changes, routines, physiological changes, and responses to what a human does next.

The programme therefore asks a broader question:

> Can we infer useful feline latent states from multimodal, temporal, individual-specific evidence, and validate those inferences through predictive outcomes and interventions rather than storytelling?

This repository remains the visual pose/motion benchmark thread. It is one measurement programme inside that larger question, not the whole translator.

## Inference framing

Let:

- `I` be a latent feline intent/state;
- `O_1:t` be observations over time;
- `C` be current context;
- `H` be individual and household history.

A useful system estimates:

`P(I | O_1:t, C, H) ∝ P(O_1:t | I, C, H) P(I | C, H)`

When an intervention is available, its outcome becomes additional evidence:

`P(I | O, C, H, intervention outcome)`

The system should be allowed to remain uncertain. It should also be allowed to discover recurring latent states before assigning them human semantic labels.

## Evidence channels

The programme treats each of the following as a possible research thread or sensor family.

### Vision and motion

- temporally stable body pose;
- face, eye aperture, gaze, pupil state, whisker and muzzle geometry;
- ear articulation;
- tail position, curvature, velocity, and tip motion;
- paw contact and weight transfer;
- gait, crouch, freeze, piloerection, kneading, rolling, rubbing;
- object-relative and scene-relative trajectories.

### Vocal acoustics

- meow, chirp, trill, growl, hiss, yowl and mixed-call structure;
- pitch contour, duration, harmonic structure, amplitude and repetition;
- inter-call timing;
- individual vocal signatures;
- call changes conditioned on context and outcome.

### Non-vocal audio

- purring;
- breathing;
- scratching;
- eating and drinking;
- litter digging;
- pawing or impact sounds;
- movement and object-interaction acoustics.

### Object and environmental context

- bowl and water state;
- door/window state;
- toy, carrier, litter tray and hiding-place relations;
- room and household location;
- temperature, light, noise and novel environmental events;
- presence of people, other cats, prey-like stimuli or unfamiliar animals.

### Human input and response

- speech or name call;
- petting, handling, approach or withdrawal;
- presenting food, toys or access to a location;
- stopping an interaction;
- human gaze and attention state;
- how the cat changes behaviour immediately after each input.

### Temporal and routine evidence

- time of day;
- time since food, water, play, sleep, toileting or social contact;
- repeated approach sequences;
- escalation after ignored signals;
- household routines;
- deviations from the individual cat's normal pattern.

### Proxemics and social context

- distance and orientation to people, cats and objects;
- approach/avoidance trajectories;
- who is present;
- familiarity and relationship history;
- turn-taking and interaction sequences.

### Physiology and wearables

Where independently measurable and ethically appropriate:

- heart rate and HRV;
- respiration;
- temperature;
- activity and sleep;
- pressure/contact signals;
- other non-invasive physiological measures.

Health, pain, welfare and diagnosis are separate evidence programmes with separate validation requirements. A behavioural model must not silently become a veterinary model.

## Research threads

The programme is deliberately plural. No single thread is assumed to be sufficient.

| Thread | Research question | Example output |
| --- | --- | --- |
| V1 — Pose & motion benchmark | Can visual surface/contact motion be recovered reliably over time? | calibrated visual features |
| V2 — Face/gaze/ear/tail microstate | Which fine visual signals add information beyond whole-body pose? | micro-behaviour embeddings |
| A1 — Vocalisation acoustics | Which acoustic structures predict context, response or outcome? | call embeddings + calibrated classifiers |
| A2 — Environmental audio | Do non-vocal sounds improve state inference? | activity/event features |
| C1 — Object/context reasoning | How much intent information comes from where the cat is and what it is acting on? | object-relative state model |
| T1 — Temporal routines | Can sequence history and routine priors outperform single-event interpretation? | temporal prior model |
| S1 — Social/proxemic context | Do distance, orientation and social configuration predict interaction state? | relational features |
| P1 — Personalisation | How quickly does an individual model outperform population priors? | per-cat adaptation curves |
| I1 — Intervention/outcome | Can candidate intents be tested by actions that should change behaviour if the hypothesis is true? | causal evidence records |
| M1 — Multimodal fusion | Which combinations produce calibrated gains over the best unimodal model? | ablation-tested fusion model |
| L1 — Latent-state discovery | Are there stable recurring communicative states that do not map cleanly to existing human labels? | unsupervised latent-state catalogue |
| E1 — Edge sensing | What useful subset can run continuously on practical home hardware? | latency/power/accuracy frontier |

The current `cat-pose-benchmark` work is **V1**, not the programme's definition.

## Validation doctrine

A model saying something plausible is not evidence that it understood the cat.

The programme should prefer tests that can fail:

1. **Prediction:** does the inferred state predict what the cat does next?
2. **Outcome termination:** if the proposed need is satisfied, does the signalling sequence stop or change in the predicted way?
3. **Intervention discrimination:** do competing hypotheses respond differently to controlled actions?
4. **Cross-context robustness:** does the signal retain meaning across rooms, times and environmental changes?
5. **Personalisation gain:** does within-cat history improve prediction without simply memorising time or location?
6. **Multimodal ablation:** does each modality contribute information beyond strong baselines?
7. **Calibration:** when the system says 70%, is it right approximately 70% of the time under the declared evaluation protocol?
8. **Unknown-state handling:** can the system abstain or create a new latent cluster instead of forcing every event into a familiar label?

## Intervention as a first-class modality

Suppose a cat approaches a human and vocalises. A model might initially estimate:

- food: 0.38
- open door: 0.29
- social attention: 0.21
- play: 0.08
- other/unknown: 0.04

Rather than outputting a confident sentence, an active system could choose an intervention that maximises expected information gain. If opening the door produces immediate exit and terminates the signalling sequence, the posterior changes. Repeated observations build an individual-specific model.

This makes the research closer to behavioural inference than theatrical translation.

## Latent states before human labels

The programme should not assume that the correct ontology already exists in English.

A multimodal model may discover recurring states such as `Z17`, `Z42`, or `Z103`. Those states can then be characterised by:

- contexts in which they occur;
- signals that co-occur;
- actions that terminate or intensify them;
- next-event predictions;
- individual and population prevalence;
- eventual human-readable interpretations where evidence supports them.

This is preferable to forcing observations into labels chosen before the data exists.

## Programme architecture

A future system can be thought of as:

`audio + vision + objects/context + human interaction + environment + routine/history + physiology + outcomes/interventions`

`-> personalised temporal world model`

`-> latent feline state distribution`

`-> probabilistic human interpretation`

The human-facing output is the last layer, not the ground truth.

## Relationship to the pose benchmark

The pose benchmark remains valuable because reliable motion measurement can feed many downstream threads. Its capture portal, provenance model, uncertainty representation, temporal metrics and monocular deployment work should continue unchanged unless evidence from that thread requires revision.

What changes is the hierarchy:

- **before:** visual motion was implicitly close to the translator's central representation;
- **now:** visual motion is one evidence source among several;
- **goal:** compare and combine modalities under common predictive, causal and calibration tests.

## Immediate next steps

1. Continue V1 without expanding its claims.
2. Define a programme-wide event record linking sensor observations, context, human actions and outcomes.
3. Start A1 with a small audio protocol focused on reproducible acoustic features and context labels.
4. Start I1 with low-risk household interventions and explicit competing hypotheses.
5. Define M1 ablations before building a large fusion model.
6. Add personalisation experiments only after population baselines are frozen.
7. Keep health/welfare inference separated until its own ethics and evidence programme exists.

The aim is not to make a cat say English. The aim is to build increasingly testable models of what a cat may be trying to do, communicate or change in its environment — and to know when the evidence is insufficient.