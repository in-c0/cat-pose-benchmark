# S0B Unity exporter scaffold

This project is the Unity-side half of #57 and the next layer of the Stage S0 annotation handshake in #7.

It is intentionally minimal:

- Unity **6000.3.18f1 / Unity 6.3 LTS** is pinned in `ProjectSettings/ProjectVersion.txt`;
- official changeset: `5ebeb53e4c07`;
- no scene is required;
- no third-party packages or assets are required;
- the Editor command creates all proxy transforms and the occluder procedurally;
- no rendering, animal data, learned pose model or physical capture is involved.

## Windows one-command verification

From the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File synthetic/unity/run_s0b_windows.ps1
```

The launcher uses the normal Unity Hub install path by default:

`C:\Program Files\Unity\Hub\Editor\6000.3.18f1\Editor\Unity.exe`

If that exact Editor is not installed, installation can be explicitly requested:

```powershell
powershell -ExecutionPolicy Bypass -File synthetic/unity/run_s0b_windows.ps1 -InstallIfMissing
```

The installer path prefers the standalone Unity CLI and runs:

```text
unity install 6000.3.18f1 -c 5ebeb53e4c07
```

If the Unity CLI is unavailable but Unity Hub exists, it falls back to the Hub headless install command. Unity documents the Hub CLI as deprecated from Hub 3.18, so the standalone Unity CLI is preferred for new automation.

If the editor is already installed elsewhere, pass its exact executable:

```powershell
powershell -ExecutionPolicy Bypass -File synthetic/unity/run_s0b_windows.ps1 `
  -UnityExe "D:\Unity\6000.3.18f1\Editor\Unity.exe"
```

The script runs the Editor exporter, runs the authoritative Python comparator and fails unless the summary is contract-valid **and** `unity_runtime_verified: true`.

### Local licensing

Unity Personal is normally activated by signing into Unity Hub and activating a license under **Settings > Licenses**. The launcher checks the standard Windows serial/named-user license locations and warns if neither is visible; it never reads, prints or uploads license contents.

## Optional GitHub Actions runtime gate

`.github/workflows/s0b-unity-runtime.yml` probes only for the **presence** of usable Unity CI credentials. It never prints secret values.

The runtime step executes only when one of these supported credential sets already exists in repository Actions secrets:

- Personal: `UNITY_LICENSE` + `UNITY_EMAIL` + `UNITY_PASSWORD`;
- Professional: `UNITY_SERIAL` + `UNITY_EMAIL` + `UNITY_PASSWORD`.

When credentials are absent, the GameCI Unity step, comparator and evidence upload are skipped, and the workflow explicitly leaves `unity_runtime_verified` false. A green skipped probe is therefore **not** runtime evidence.

When credentials exist, GameCI runs the same pinned Editor project with the custom static build method, writes `s0b-unity.json`, executes the authoritative comparator, and uploads the runtime export/summary only if that path is attempted.

## Manual batch export

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

The default round-trip tolerance is `5e-5`, chosen only to accommodate Unity float32 versus Python float64 representation. At image coordinates around 300 px, one float32 ULP is already on the order of `3e-5` px. This is a serialization/runtime-convention tolerance, not an allowed pose-estimation error.

A zero-mismatch report sets `unity_runtime_verified: true`.

## CI boundary

The ordinary S0 Python matrix does **not** claim to launch Unity. It validates the Python comparator using `python_mock_unity_contract`, mutation/failure cases, project pinning and static exporter invariants. Mock exports require the comparator's explicit `--allow-mock` flag and can never produce `unity_runtime_verified: true`.

The optional licensed runtime workflow is a separate gate and is interpreted only by whether its actual Unity/comparator steps executed successfully.

Until a real Editor or licensed CI run produces a zero-mismatch report, S0B remains runtime-unverified.

## Scientific boundary

This proves only that the Unity exporter follows the frozen synthetic annotation convention. All resulting observations remain X1 synthetic exact. It does not establish feline pose accuracy, real-world uncertainty, behavioural inference or M1 eligibility.