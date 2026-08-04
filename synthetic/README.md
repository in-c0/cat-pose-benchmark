# Stage S0 synthetic annotation handshake

This directory contains the software-only exact-data contract for the first CatPose
implementation milestone.

The first exporter uses a deliberately simple procedural feline proxy. Its purpose is to
prove:

```text
Unity runtime state
→ deterministic sequence export
→ schema validation
→ independent Python projection comparison
→ later viewer and baseline ingestion
```

It does **not** claim visual realism, real-cat accuracy, behavioural validity, or external
metric validation.

## Evidence scope

Every sequence produced by this exporter is:

- evidence tier `S`;
- quality `gold` only within its declared Unity configuration;
- exact for exported runtime transforms and declared states;
- not real-world ground truth.

See:

- `schemas/synthetic-sequence.schema.json`;
- `schemas/observation.schema.json`;
- `docs/GROUND-TRUTH-PROVENANCE.md`;
- `docs/SOFTWARE-FIRST-ROADMAP.md`.

## Generate from the Unity editor

1. Open `unity-viewer/` in the Unity version recorded in
   `unity-viewer/ProjectSettings/ProjectVersion.txt`.
2. Wait for scripts to compile.
3. Select **CatPose → Generate Stage S0 Synthetic Fixture**.

The exporter writes:

```text
synthetic/fixtures/stage-s0-unity-export.json
```

The exporter creates and destroys a temporary scene in memory. It does not require a
saved scene, imported cat model, camera, mirror, animal, or physical apparatus.

## Generate in Unity batch mode

From the repository root, replace the editor path with the installed Unity executable:

```powershell
& "C:\Program Files\Unity\Hub\Editor\6000.0.75f1\Editor\Unity.exe" `
  -batchmode `
  -quit `
  -projectPath "$PWD\unity-viewer" `
  -executeMethod CatPose.StageS0.StageS0SyntheticExporter.ExportFromCommandLine `
  -catposeOutput "$PWD\synthetic\fixtures\stage-s0-unity-export.json" `
  -logFile "$PWD\synthetic\fixtures\stage-s0-unity-export.log"
```

The command may require its path to be adjusted to the locally installed editor version.

## Validate an export

First run structural and cross-field validation:

```bash
python synthetic/validate_sequence.py \
  synthetic/fixtures/stage-s0-unity-export.json
```

Then compare the Unity result against the independent Python camera and procedural-motion
reference:

```bash
python -m synthetic.reference_stage_s0 \
  synthetic/fixtures/stage-s0-unity-export.json
```

The reference implementation independently reconstructs:

- Unity-compatible camera right/up/forward axes;
- world-to-camera transforms;
- pinhole projection from vertical field of view and aspect ratio;
- root motion and fixed timestamps;
- semantic landmark positions;
- procedural tail motion;
- contact and scene-relation records.

A serializer can therefore not pass merely by being self-consistent. Camera, timing,
topology, or procedural-state drift appears as a path-specific numerical error.

Validation covers:

- JSON Schema conformance;
- evidence tier and deterministic metadata;
- contiguous frame indices and fixed timestamps;
- finite vectors;
- unique landmark identities;
- visible points within the declared image and in front of the camera;
- known support-surface references;
- subject identity in spatial relations;
- root velocity against finite differences;
- canonical SHA-256 generation;
- independent Unity/Python transform and projection parity.

## Current proxy content

The generated sequence contains:

- five frames at a fixed 100 ms timestep;
- one moving procedural feline proxy;
- nose, ear-tip, paw, tail-base, and tail-tip landmarks;
- a four-point animated tail curve;
- one camera at 640 × 480 and 60° vertical field of view;
- a floor and two box objects;
- four declared paw contacts;
- an `on floor` spatial relation;
- exact world, camera, and image coordinates.

## Current limitations

- no licence-clean realistic feline asset yet;
- no animation clip or deformable skin;
- no renderer output committed;
- visibility is currently frustum-based, not raycast occlusion-aware;
- contacts are declared by the procedural fixture, not collider events;
- no Unity execution occurs in GitHub CI yet;
- the committed Python tests validate the contract, camera equations, and invariants,
  but not Unity compilation.

These limitations keep Issue #7 open after the code lands.

## Next slice

1. Execute the exporter in the pinned Unity editor.
2. Run both validation commands and commit the first generated fixture.
3. Add raycast visibility and explicit occluder test cases.
4. Add exact acceleration and tail-derivative exports.
5. Add Unity Test Framework coverage or a licensed CI execution path.
6. Replace or supplement the proxy with a licence-clean rigged feline asset without
   changing the sequence contract.
