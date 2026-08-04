# CatPose Stage 0 Unity viewer

A minimal Unity 6 LTS project for inspecting the CatPose Portal coordinate convention,
mirror planes, physical/virtual cameras, representative reflected rays, and capture
volume.

## Run

1. Open `unity-viewer/` as a Unity project with the editor version recorded in
   `ProjectSettings/ProjectVersion.txt`.
2. Create or open an empty 3D scene.
3. Enter Play Mode.

`Stage0Viewer` bootstraps automatically. It reads
`Assets/StreamingAssets/stage0-scene-v2.json` and constructs the nominal geometry at
runtime; no scene asset or manual object setup is required.

## Coordinate conversion

The research geometry uses:

- `+x`: portal left to right;
- `+y`: physical camera through the portal;
- `+z`: up.

Unity receives:

```text
unity = (source.x, source.z, source.y)
```

The viewer is an engineering parity tool, not measured evidence. The current JSON is
generated from `stage0/layouts.json` by:

```bash
python stage0/export_unity_scene_v2.py \
  --config stage0/layouts.json \
  --layout A_symmetric_lateral \
  --output unity-viewer/Assets/StreamingAssets/stage0-scene-v2.json
```

## Current visualisation

- capture-volume wireframe;
- source-to-Unity coordinate axes;
- physical camera and virtual reflected cameras;
- finite mirror planes and normals;
- direct and reflected paths through a representative point;
- representative target point.

## Required measured-data extension

After physical Stage 0 capture, extend the scene format and renderer with:

- calibrated camera intrinsics/extrinsics;
- measured finite mirror boundary masks;
- detected and reconstructed target points;
- holdout residual vectors;
- per-point covariance ellipsoids;
- invalid/dropout rays;
- parity state per reflected region;
- frame and calibration identifiers;
- side-by-side Layout A/Layout B comparison.

The Unity reconstruction must agree numerically with the Python reference geometry; a
visually plausible scene is not sufficient.
