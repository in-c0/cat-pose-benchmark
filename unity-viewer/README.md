# CatPose Stage 0 Unity viewer

A minimal Unity 6 LTS project for inspecting the CatPose Portal coordinate convention,
mirror planes, physical/virtual cameras, reflected rays, and capture volume.

## Run

1. Open `unity-viewer/` as a Unity project with the editor version recorded in
   `ProjectSettings/ProjectVersion.txt`.
2. Create or open an empty 3D scene.
3. Enter Play Mode.

`Stage0Viewer` bootstraps automatically and reads
`Assets/StreamingAssets/stage0-scene-v2.json`; no scene asset or manual setup is required.

## Coordinate conversion

The research geometry uses `+x` portal-left-to-right, `+y` through the portal, and `+z`
up. Unity receives:

```text
unity = (source.x, source.z, source.y)
```

Run the exporter from the repository root as a Python module:

```bash
python -m stage0.export_unity_scene_v2 \
  --config stage0/layouts.json \
  --layout A_symmetric_lateral \
  --output unity-viewer/Assets/StreamingAssets/stage0-scene-v2.json
```

## Current visualisation

- capture-volume wireframe;
- coordinate axes;
- physical camera and virtual reflected cameras;
- finite mirror planes and normals;
- direct and reflected representative rays;
- representative target point.

This is an engineering parity tool, not measured evidence. Physical Stage 0 will extend
the format with calibrated intrinsics/extrinsics, measured mirror boundaries, detected
and reconstructed target points, holdout residuals, covariance ellipsoids, dropout rays,
parity state, and frame/calibration identifiers.

The Unity reconstruction must agree numerically with the Python reference geometry; a
visually plausible scene is not sufficient.
