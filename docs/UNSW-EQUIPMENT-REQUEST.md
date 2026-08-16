# Optional external validation partner request

This template is **not** a request for the project lead to borrow equipment and operate a
rig. It is for identifying an institutional partner willing to own and perform a small,
independent validation study under the CatPose external-validation contract.

## Subject

Collaboration enquiry: independent validation for an open feline computer-vision benchmark

## Message

Hello,

I am developing an open, software-first benchmark for monocular feline pose and temporal
motion analysis. The public project uses Unity-generated exact annotations and
licence-clean real video with observable labels. It intentionally does not require the
lead developer to build or operate bespoke physical apparatus.

I am seeking a laboratory or facility interested in independently operating a small
hidden-gold validation study. The project would provide the ontology, schemas, automated
QA, calibration manifests, prediction interface, and evaluation code. The partner would
own all physical setup, operation, safety, ethics, animal-welfare, consent, and data
custody.

Potential measurement methods include:

- synchronized calibrated RGB cameras;
- Vicon or another motion-capture system;
- calibrated RGB-D or photogrammetry;
- pressure walkway or contact instrumentation;
- a mirror-based simultaneous-view setup;
- another traceable method your laboratory considers more appropriate.

The initial study can be extremely small and may remain private behind a remote
evaluation service. The goal is to evaluate a few externally observable surface points,
tail geometry, timing, contact, or metric 3D variables without claiming medical or
behavioural diagnosis.

Would your group be open to a short discussion about:

1. suitable measurement capabilities already operated by your staff;
2. whether an existing ethically approved dataset could satisfy part of the interface;
3. a partner-operated pilot with the project providing software only;
4. data custody, attribution, publication, and collaboration terms?

The current protocol and interface are documented in the repository under
`docs/EXTERNAL-VALIDATION-CONTRACT.md`.

Kind regards,
Ava Kim

## Relevant UNSW capability classes

Potential pathways include groups operating:

- human or animal motion capture;
- close-range photogrammetry and spatial measurement;
- optical testing and calibration;
- veterinary or animal-behaviour research;
- research software and data infrastructure.

Availability of any specific camera, mirror, Vicon setup, or animal protocol must not be
assumed from a public facility page. The enquiry asks whether a group wants to operate
the validation, not whether equipment can be handed to the project lead.

## Information to attach

- repository: `in-c0/cat-pose-benchmark`;
- software-first roadmap: `docs/SOFTWARE-FIRST-ROADMAP.md`;
- external validation interface: `docs/EXTERNAL-VALIDATION-CONTRACT.md`;
- observation provenance: `docs/GROUND-TRUTH-PROVENANCE.md`;
- explicit statement: the project lead will not operate specialised physical equipment.
