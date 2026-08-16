# CatPose Unity project

This Unity 6 LTS project now supports two distinct workflows:

1. **Stage S0 synthetic exact export** — the active software-first implementation path.
2. **Stage 0 portal geometry viewer** — an optional external-validation design study.

Neither workflow requires the project lead to construct or operate physical apparatus.

## Stage S0 synthetic export

The editor script at
`Assets/Editor/StageS0SyntheticExporter.cs` creates a temporary procedural feline proxy,
camera, floor, and scene objects entirely in memory. It exports exact Unity runtime state
to:

```text
../synthetic/fixtures/stage-s0-unity-export.json
```

### Editor command

1. Open `unity-viewer/` using the editor version in
   `ProjectSettings/ProjectVersion.txt`.
2. Select **CatPose → Generate Stage S0 Synthetic Fixture**.
3. Validate the output from the repository root:

```bash
python synthetic/validate_sequence.py \
  synthetic/fixtures/stage-s0-unity-export.json
```

### Batch command

```powershell
& "C:\Program Files\Unity\Hub\Editor\6000.0.75f1\Editor\Unity.exe" `
  -batchmode `
  -quit `
  -projectPath "$PWD\unity-viewer" `
  -executeMethod CatPose.StageS0.StageS0SyntheticExporter.ExportFromCommandLine `
  -catposeOutput "$PWD\synthetic\fixtures\stage-s0-unity-export.json" `
  -logFile "$PWD\synthetic\fixtures\stage-s0-unity-export.log"
```

Adjust the Unity executable path to the installed editor version.

The procedural proxy is a contract test, not a realistic cat asset and not evidence of
real-world accuracy.

## Optional portal geometry viewer

The runtime `Stage0Viewer` inspects the archived mirror-portal coordinate convention,
mirror planes, physical/virtual cameras, reflected rays, and nominal capture volume.

To run it:

1. Create or open an empty 3D scene.
2. Enter Play Mode.

`Stage0Viewer` bootstraps automatically and reads
`Assets/StreamingAssets/stage0-scene-v2.json`.

### Portal coordinate conversion

The archived portal geometry uses `+x` portal-left-to-right, `+y` through the portal, and
`+z` up. Unity receives:

```text
unity = (source.x, source.z, source.y)
```

Regenerate the nominal portal scene from the repository root:

```bash
python -m stage0.export_unity_scene_v2 \
  --config stage0/layouts.json \
  --layout A_symmetric_lateral \
  --output unity-viewer/Assets/StreamingAssets/stage0-scene-v2.json
```

The portal viewer is an engineering parity tool. It is not measured evidence and is not
on the Protocol v0.1 critical path.

## Next Unity work

- execute and validate the first Stage S0 fixture;
- add a sequence player for exact labels and model predictions;
- add raycast visibility and occlusion cases;
- add uncertainty and error overlays;
- import a licence-clean rigged feline asset without changing the export contract;
- add Unity Test Framework or licensed batch CI coverage.
