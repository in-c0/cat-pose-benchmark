# S0B Unity exporter scaffold

This project is the Unity-side half of #57 and the next layer of the Stage S0 annotation handshake in #7.

It is intentionally minimal:

- Unity **6000.3.18f1 / Unity 6.3 LTS** is pinned in `ProjectSettings/ProjectVersion.txt`;
- no scene is required;
- no third-party packages or assets are required;
- the Editor command creates all proxy transforms and the occluder procedurally;
- no rendering, animal data, learned pose model or physical capture is involved.

## Batch export

Run from a machine with the pinned Unity Editor installed. Replace `Unity` with the platform-specific editor executable if needed.

```bash
Unity \
  -batchmode \
  -quit \
  -projectPath synthetic/unity/S0AProxy \
  -executeMethod CatPose.S0B.S0BProxyExportCommand.Run \
  -s0Output /tmp/s0b-unity.json \
  -logFile -
```

The exporter creates a temporary hierarchy in the Editor process, advances the five frozen S0A frames, reads world positions from Unity `Transform.position`, evaluates occlusion using the Unity `BoxCollider.bounds` ray intersection, and serializes the raw cross-language contract.

## Authoritative round-trip gate

Then run:

```bash
python -m synthetic.unity_roundtrip \
  /tmp/s0b-unity.json \
  --summary /tmp/s0b-roundtrip.json
```

The actual gate requires:

- `runtime_source == "unity_editor"`;
- `Application.unityVersion == "6000.3.18f1"`;
- frame/timestamp agreement;
- camera agreement;
- root/landmark/tail world coordinates within the frozen numerical tolerance;
- image projection agreement;
- contact agreement;
- visibility/occlusion agreement;
- scene-object transform agreement.

A zero-mismatch report sets `unity_runtime_verified: true`.

## CI boundary

Repository CI does **not** claim to launch Unity. It validates the Python comparator using `python_mock_unity_contract`, mutation/failure cases, project pinning and static exporter invariants. Mock exports require the comparator's explicit `--allow-mock` flag and can never produce `unity_runtime_verified: true`.

Until a real Editor or batch run produces a zero-mismatch report, S0B remains runtime-unverified.

## Scientific boundary

This proves only that the Unity exporter follows the frozen synthetic annotation convention. All resulting observations remain X1 synthetic exact. It does not establish feline pose accuracy, real-world uncertainty, behavioural inference or M1 eligibility.
