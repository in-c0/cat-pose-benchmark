# Beyond pose: what could a cat-intent system actually rely on?

*Research note — 21 August 2026*

The obvious first version of a cat translator is visual: track the cat, understand its posture, then infer what it means.

That is useful, but it is too narrow.

A cat's internal state can leave evidence in many places at once. Vocalisations, gaze, ear and tail motion, where the cat chooses to stand, what object it approaches, what happened ten seconds earlier, what normally happens at that time of day, and what the cat does after a human responds can all carry information.

So the research question should not be:

> Can pose be translated into intent?

It should be closer to:

> Can we infer useful feline latent states from multimodal, temporal and individual-specific evidence, and validate those inferences through what happens next?

Possible evidence includes vocal acoustics; purring, scratching and other environmental audio; face and gaze; fine body language; object-directed behaviour; location and proxemics; household routines; human input and cat response; physiology; social context; and longitudinal statistics for the individual cat.

The most interesting source may be **outcome feedback**.

Imagine a cat approaches and vocalises. A system might initially estimate:

- food: 38%
- open door: 29%
- attention: 21%
- play: 8%
- other: 4%

Instead of pretending it already knows, the system can test a low-risk action. If opening the door causes the cat to leave and the signalling sequence immediately ends, that is evidence. Over repeated episodes, the model can learn not only population patterns but this cat's own patterns.

That makes intervention itself a modality.

It also means we should not force every recurring behaviour into an English phrase. A model may first discover latent states — `Z17`, `Z42`, `Z103` — that recur across audio, motion, context and outcomes. Only later should we ask whether those states correspond to useful human interpretations.

The architecture then becomes something like:

`audio + vision + context + interaction + environment + history + physiology + outcomes`

`-> personalised temporal world model`

`-> latent feline state distribution`

`-> probabilistic human interpretation`

This changes how the existing research fits together. The current cat pose and motion benchmark still matters, but it becomes one thread among many rather than the definition of the translator. Its job is to make visual motion measurable and calibrated. Other threads can investigate vocalisation, context, routines, personalisation, interventions and multimodal fusion.

The scientific standard should remain conservative: plausible output is not evidence of understanding. A candidate signal becomes interesting when it predicts future behaviour, survives ablation, improves calibration, generalises across contexts, or responds to interventions in ways competing hypotheses do not.

The long-term goal is therefore not literal English-speaking-cat theatre. It is a system that can say, with evidence and uncertainty, what a cat may be trying to do, communicate or change — and can also say when it does not know.

See [`docs/FELINE-INTENT-RESEARCH.md`](../docs/FELINE-INTENT-RESEARCH.md) for the programme structure and proposed research threads.