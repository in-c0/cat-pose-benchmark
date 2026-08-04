# CatPose Stage 0 Unity viewer

A minimal Unity Editor inspection tool for the Stage 0 catadioptric portal geometry.

The viewer does not produce benchmark labels. It makes coordinate conventions,
finite-mirror geometry, reflected-image parity, virtual cameras, sensor occupancy, and
simulated uncertainty assumptions visible before physical calibration.

## Editor version

The project is pinned to **Unity 6.3 LTS, 6000.3.0f1**. Open the `unity-viewer/`
directory as a Unity project.

The project deliberately uses only built-in Unity modules and Unity Test Framework
1.6.0. No render-pipeline package is required because the first milestone is an Editor
Scene-view diagnostic rather than a product UI.

## Canonical data flow

Do not edit `Assets/StreamingAssets/CatPose/stage0-layouts.json` by hand.

The canonical inputs remain at the repository root:

```text
stage0/layouts.json
stage0/geometry-conditioning-report.json
```

Regenerate the Unity-friendly array-based contract from the repository root:

```bash
python -m pip install numpy
python -m stage0.export_unity_config
```

CI regenerates the same file and verifies exact structure plus floating-point agreement
within documented numerical tolerance.

## Open the viewer

1. Open `unity-viewer/` in Unity 6.3 LTS.
2. Wait for script compilation and package resolution.
3. Choose **Tools > CatPose > Stage 0 Geometry Viewer**.
4. Keep a Scene view open; the tool draws its diagnostic geometry there.
5. Switch between `A_symmetric_lateral` and `B_lateral_pitched` in the viewer window.

The tool displays:

- repository and Unity coordinate axes;
- capture-volume bounds and sampled points;
- the physical camera and look direction;
- finite mirror rectangles and normals;
- reflected virtual-camera centres;
- direct and reflected ray paths;
- optional invalid finite-aperture rays;
- physical-sensor image-region bounds;
- direct versus mirrored parity labels;
- ideal-plane coverage and uncertainty summaries;
- Python-to-C# virtual-camera consistency error.

## Coordinate and parity contract

Repository coordinates use:

```text
+x = portal left to right
+y = physical camera through portal
+z = upward
```

Unity uses:

```text
+x = right
+y = upward
+z = forward
```

The conversion is therefore:

```text
repository (x, y, z) -> Unity (x, z, y)
```

This axis swap changes handedness intentionally. Mirror projections remain labelled as
`mirrored`; the viewer must not silently flip reflected observations into a direct-view
appearance.

## Run EditMode tests

In Unity:

1. Open **Window > General > Test Runner**.
2. Select **EditMode**.
3. Run `CatPose.Stage0.EditorTests`.

The initial tests cover:

- repository-to-Unity coordinate conversion and round trip;
- reflection across a known plane;
- generated configuration loading;
- agreement between Python and C# virtual-camera centres;
- finite-mirror intersection at the capture-volume centre.

A command-line Unity test run can be added once an authenticated Unity installation or
licensed CI runner is available.

## Verification boundary

Verified without Unity:

- canonical JSON export;
- generated-contract reproducibility;
- mirror reflection and finite-aperture geometry in Python;
- Python reference values embedded in the Unity contract;
- static inspection of the C# data and geometry implementation.

Not yet independently verified in this environment:

- Unity script compilation;
- EditMode test execution inside Unity;
- Scene-view rendering and interaction;
- behaviour under a different Unity patch release;
- physical camera or mirror calibration.

A clean Unity compilation and EditMode test run is required before this milestone can be
considered complete. Physical Stage 0 remains a separate experiment and must precede any
animal capture.
