# Product evidence check (2026-10-11)

This note asks one question and keeps it apart from the benchmark: does anything this repository has shown support a paid consumer product? It is written for the owner deciding where to spend time and money next. The README's position still holds: the consumer brand and its products stay separate from this research artefact, and nothing here is a product claim.

## What has actually been shown

| capability | evidence | who checked it |
|---|---|---|
| Finding a cat's tail in a frame of ordinary video (tail method v3) | Two prospective holdouts, 12 clips, pooled: precision 0.57, recall 0.65 as frozen; 0.70 and 0.81 after post-inference overrides. Per-cat recall ranges from 0.00 to 1.00, median 0.26 as frozen. Clip-level 95 % intervals are roughly 0.1–0.9. | A model, against labels written by a model. No human has checked any of it (HR1 is the gate for that). |
| Refusing when the tail is hidden | On frames with a hidden tail, v3 asserted a tail 36 times out of 240 across the holdouts. The errors come in long consistent runs: a rump patch read as a tail for 17 frames, a face edge for 11. | Same as above. |
| Body keypoints (RTMPose AP-10K) | The detector finds a cat on most frames. Keypoint accuracy has never been measured in this repository. | Nobody. |
| Ear geometry | One frame per ear, feasibility only (issue #11). | One person by eye. |
| Emotion, intention, welfare | Nothing. The multimodal "intent" programme ran in August 2026, produced no positive result and was carved out on 2026-09-11. | Not applicable. |

So the verified capability, in the strict sense of something checked by a person under a written protocol, is currently none. The model-checked capability is a tail locator that is wrong on roughly three to four of every ten assertions on unseen clips and that works very well on some cats and not at all on others.

## Pose is not translation

A consumer pitch in this space usually says what the cat feels or wants. Getting from "the tail is up" to "your cat is happy to see you" needs a second claim: that a measured posture reliably indicates an internal state, for this cat, in this context. That claim needs its own validation against something other than the posture itself, such as observed outcomes or independently scored behaviour. This repository does not test it and says so in the README. A perfect tail locator would still not be an emotion translator. Apps that sell "cat translation" already exist (MeowTalk is one, for vocalisations). Their existence shows there is demand for the claim. It does not show that the claim is valid.

## Could the current capability support a paid product?

Not at its current level, and not yet on any evidence a buyer could check. Three reasons stand out.

1. **Error rate.** At about 0.6–0.7 precision on unseen video, a product that reports tail position would be wrong on about a third of what it says, and the wrong answers arrive in confident runs. Consistency makes them look trustworthy, which is worse for a consumer than visible noise.
2. **Per-cat variance.** The failures are specific to particular cats and scenes, such as an orange rump patch or a face filling the frame. An owner whose cat falls on the bad side would see the product fail all the time, whatever the average says.
3. **Licensing is unrecorded for the v3 stack.** Issue #9 tracks commercial status per model. It covers SuperAnimal (research-only) and the RTMPose code, but has no entry for Grounding DINO, SAM2 or SigLIP weights as used here. That has to be filled in before any commercial use.

Two narrower ideas are less exposed to these problems, and both would be cheap to test once HR1 passes:

- **A research or annotation aid.** Pre-drawing tail candidates for behaviour researchers who confirm or reject them. The human stays in the loop, so the value is time saved per labelled frame, which is measurable.
- **A "find the moment" clip search** for owners ("show me when the tail went up"). The owner sees the clip, so an error costs a few seconds rather than a wrong belief about the cat. It still must not claim to say what the cat feels.

## What would change this assessment

- HR1 shows human precision on the holdouts at or above about 0.9 with alpha ≥ 0.80. On present evidence that is unlikely without a new method.
- The same holds on owner-shot home video from at least 20 different cats, because Commons clips are not home-camera footage.
- A willingness-to-pay test for one of the two narrow ideas above, phrased without any emotion claim.

Until the first of these exists, the recommendation is to spend nothing on product work for this capability and to treat any product framing as a hypothesis, not a plan.
