# Software-first roadmap

**Decision:** the CatPose programme must be executable without the lead developer
constructing, fabricating, calibrating, or operating bespoke physical apparatus.

Physical involvement is limited to ordinary user testing of an eventual app or
externally manufactured product.

## Operating principle

The programme separates four kinds of work:

| Workstream | Lead developer | Remote contributors | External laboratory/vendor |
|---|---:|---:|---:|
| Unity simulation and exact labels | owns | optional | no |
| Real-video sourcing and observable review | software/QA | supplies or reviews | optional |
| Monocular models and evaluation | owns | no | optional compute |
| Specialised metric validation | protocol/software only | optional | operates equipment |
| Product fabrication | specifications/software | no | manufactures |
| Product use testing | ordinary user | optional beta users | supplies unit |

## Critical path

```text
ontology + schema
    ↓
Unity exact-data generator
    ↓
synthetic challenge benchmark
    ↓
real-video observable benchmark
    ↓
monocular pose / tracking / uncertainty baseline
    ↓
playful translator application
    ↓
software-defined edge and RTL/HLS workflow
    ↓
external hidden-gold validation
    ↓
externally manufactured puck / AR product
```

No step before external validation requires a custom physical rig.

## Milestone S0 — exact annotation handshake

Deliver one deterministic Unity scene containing:

- one rigged feline asset;
- one short animation;
- one camera;
- a floor and two scene objects;
- declared body and facial landmarks;
- tail spline;
- paw-contact state;
- visibility and object-relation labels.

Export one machine-readable frame sequence and verify that every exported value agrees
with Unity runtime state within a declared tolerance.

### Exit gate

- repeated generation under the same seed is identical;
- coordinate transforms are unit-tested;
- all labels preserve source and evidence tier;
- no proprietary or non-redistributable asset contaminates the planned release.

## Milestone S1 — procedural CatSynth4D

Add parameterized variation for:

- morphology and scale;
- coat appearance;
- facial, ear, and tail articulation;
- locomotion and local high-frequency motion;
- camera position, motion, and lens;
- lighting, clutter, blur, compression, and occlusion;
- scene contacts and spatial relations.

Every generated sequence receives exact annotations and a challenge manifest.

### Exit gate

- invalid anatomy and foot sliding are detected;
- challenge factors can be isolated for ablation;
- at least one baseline can consume generated data end-to-end;
- synthetic confidence targets and visibility are validated.

## Milestone R0 — real observable seed

Acquire one licence-clean real sequence through an existing permissive source, remote
contributor, contractor, or partner.

Review only observable facts:

- visible landmarks;
- ear and tail geometry;
- track continuity;
- occlusion state;
- visible contact and event timing;
- ambiguity and confidence.

### Exit gate

- rights and consent are machine-readable;
- no hidden anatomy or metric depth is presented as truth;
- at least two independent reviews exist for a subset;
- disagreement is retained rather than erased.

## Milestone M0 — baseline and uncertainty

Integrate one commercially usable pose/tracking baseline and report:

- Tier S 2D and 3D error;
- Tier S derivative and contact error;
- Tier R2 visible landmark and tail-curve error;
- jitter, drift, occlusion recovery, and re-detection;
- confidence calibration and risk–coverage;
- synthetic-to-real degradation.

### Exit gate

- no circular evaluation;
- model and checkpoint licences are recorded;
- evaluation is reproducible from a clean environment;
- failure examples are inspectable in Unity.

## Milestone P0 — playful translator

Build a monocular entertainment application that presents:

1. observations;
2. cautious behavioural hypotheses;
3. playful translation copy;
4. confidence and limitations.

It must not claim literal translation, diagnosis, pain detection, or veterinary advice.

User testing may use ordinary owner-shot footage or a finished app build. No research rig
is required.

## Milestone H0 — software-defined hardware workflow

Demonstrate hardware-aware implementation through:

- ONNX export and quantisation;
- operator profiling and partitioning;
- one HLS or RTL kernel;
- cocotb or equivalent verification;
- Verilator simulation;
- synthesis and timing/area/power reports;
- OpenROAD or FPGA implementation where practical;
- benchmark-driven accuracy/latency/resource trade-offs.

Physical board or silicon execution is optional and may be performed remotely or by a
vendor. Simulation evidence must be labelled as simulation.

## Milestone G0 — external hidden gold

Invite a qualified partner to implement the external-validation contract. The partner
operates equipment and returns either:

- encrypted observations;
- private evaluation results;
- a hosted evaluation endpoint;
- a publishable subset under agreed terms.

The lead developer writes integration software and analyses outputs but performs no
physical measurement.

## Milestone D0 — manufactured device

Specify camera, compute, thermal, power, enclosure, and software interfaces. Use a
contract manufacturer, development service, or hardware collaborator to fabricate the
puck or AR device.

The lead developer receives a finished unit and tests it as a normal user.

## Explicit exclusions

The critical path excludes:

- buying mirrors or machine-vision cameras for a home rig;
- measuring bedroom dimensions for research apparatus;
- printing and assembling calibration targets;
- filming cats for benchmark collection personally;
- soldering or machining a product prototype;
- operating Vicon, pressure, or calibration equipment;
- presenting simulation as measured physical validation.

## Immediate next implementation

The next repository change after this roadmap is a specification for the Stage S0 Unity
annotation handshake:

- asset requirements and licence policy;
- coordinate system;
- landmark and tail schema;
- annotation export format;
- deterministic seed contract;
- frame-level unit tests;
- minimal viewer acceptance criteria.
