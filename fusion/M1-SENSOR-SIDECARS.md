# M1.3 sealed local sensor sidecars

Status: acquisition/integration tooling for A1.2 + M1. It does not record media itself and does not produce a feline-behaviour result.

## Why this is separate from CT1 capture

CT1.3 deliberately freezes the prediction-time context and `observations` at `t0`. The resulting `.ct1-lock.json` protects that record from retrospective editing. Appending A1/V1 observations directly into the CT1 event would invalidate that guarantee.

M1.3 therefore keeps two provenance streams separate:

1. the original CT1 event and lock;
2. one or more local sensor sidecars reserved during the M1 sensor-evidence window.

After CT1 finalization, `compose` verifies both streams and writes a **new derived event**. It never edits the original CT1 JSON or lock.

## Frozen evidence window

For the first M1 experiment from #44, A1/V1 evidence must fall inside:

`0 <= start_offset_ms < end_offset_ms <= 5000`

A sidecar reservation itself must also be created prospectively while its declared evidence window is still open. A reservation attempted after that interval is rejected.

This tooling does **not** infer acquisition timing from file creation/modification timestamps. Those timestamps are not a reliable scientific clock. The operator/capture backend remains responsible for ensuring the sealed artifact truly corresponds to the reserved interval.

## Supported artifact types

### A1 vocal audio

- event modality: `audio_vocalisation`
- artifact kind: `wav_audio`
- sealed artifact must be a readable WAV;
- WAV duration must cover the reserved interval;
- sample rate, channels, sample width, frame count and duration are retained as metadata.

### V1 pose

- event modality: `visual_pose`
- artifact kind: `pose_features_json`
- required sidecar schema ref: `fusion/v1_pose_package.schema.json`;
- sealed artifact must satisfy the V1→M1 pose-package schema and semantic validator;
- package event/episode and evidence window must match the reservation exactly;
- package samples must contain real pose/motion observations valid under `schemas/observation.schema.json`;
- every observation must retain value, uncertainty, visibility, evidence tier, quality, source IDs and lineage;
- learned-model producers must identify their model family and exact weights SHA-256;
- composition rechecks the package subject against the actual finalized CT1 event.

Raw video is **not** accepted as `visual_pose`. A camera recording is not automatically a pose observation; it must first be converted to the V1 representation under its own provenance. Synthetic X1 and unlabelled U0 observations also do not count as prospective real V1 evidence for the initial M1 comparison.

See `fusion/V1-POSE-PACKAGE-CONTRACT.md` for the full boundary.

## Privacy declaration

Every reservation requires an explicit `--human-content` choice:

- `none`
- `audio`
- `image`
- `both`

The derived event ORs these flags into `privacy.contains_human_audio` / `privacy.contains_human_image`. This does not change a `restricted` household record into `consented_research`; consent/data-class status remains whatever the base CT1 event already declared.

Raw files stay local. The composed event includes only:

- a pseudonymous record ID;
- SHA-256;
- byte length;
- non-path media metadata;
- reservation/seal provenance hashes.

The local artifact path is intentionally absent.

## Lifecycle

### 1. Start CT1 normally

Use the existing CT1.3 capture command. It produces the immutable event and sidecar lock.

### 2. Reserve sensor evidence prospectively

Immediately while the declared evidence window is open:

```bash
python -m fusion.m1_sensor_sidecar reserve \
  --event local-data/h0/episode-001.json \
  --output local-data/h0/episode-001.a1-sidecar.json \
  --modality audio_vocalisation \
  --schema-ref audio/A1-naturalistic-wav-v0 \
  --human-content audio
```

For a V1 pose artifact:

```bash
python -m fusion.m1_sensor_sidecar reserve \
  --event local-data/h0/episode-001.json \
  --output local-data/h0/episode-001.v1-sidecar.json \
  --modality visual_pose \
  --schema-ref fusion/v1_pose_package.schema.json \
  --human-content none
```

The default evidence interval is 0–5000 ms. A narrower interval can be supplied using `--start-offset-ms` and `--end-offset-ms`, but it must remain within the frozen 5-second window and the V1 package must declare the same exact interval.

## 3. Seal the actual local artifacts

After the acquisition backend has produced the artifact:

```bash
python -m fusion.m1_sensor_sidecar seal \
  --sidecar local-data/h0/episode-001.a1-sidecar.json \
  --artifact local-data/media/episode-001.wav
```

and/or:

```bash
python -m fusion.m1_sensor_sidecar seal \
  --sidecar local-data/h0/episode-001.v1-sidecar.json \
  --artifact local-data/pose/episode-001.json
```

`seal` records the artifact hash and metadata. A valid V1 seal also records package/sample/observation counts, evidence-tier and quality counts, the evidence window and producer fingerprint. These are provenance summaries, not pose-performance scores. If the local artifact is edited afterwards, composition fails.

## 4. Finalize CT1 outcome

Use the existing CT1 command after the frozen 60-second outcome window:

```bash
python -m context.ct1_capture_cli finalize \
  --event local-data/h0/episode-001.json \
  --outcome terminated
```

The original event is still the canonical CT1 record.

## 5. Compose a derived M1 event

```bash
python -m fusion.m1_sensor_sidecar compose \
  --event local-data/h0/episode-001.json \
  --sidecar local-data/h0/episode-001.a1-sidecar.json \
  --sidecar local-data/h0/episode-001.v1-sidecar.json \
  --output local-data/m1/episode-001.m1.json \
  --readiness local-data/m1/episode-001.readiness.json
```

Before writing the derived record, composition verifies:

- CT1 finalization and completed-event SHA-256;
- original `t0` predictor fingerprint;
- append-only CT1 action log;
- sidecar event/episode/fingerprint identity;
- reservation integrity;
- frozen 0–5 s offsets;
- sealed media hash and size;
- V1 package subject/event/episode/timing/provenance consistency where applicable;
- unique observation refs;
- #18 event validity;
- CT1.2 context validity.

It then prints M1.2 readiness. A single A1 sidecar may make A1 available without making the episode primary M1-ready; primary readiness requires B0 + V1 + A1 + a valid termination target on the same episode.

## Scientific boundary

A reservation is prospective provenance, not proof that an external recorder was synchronized correctly. Until a capture backend writes a trusted acquisition timestamp/clock directly, the operator must ensure the artifact genuinely corresponds to the reservation. Do not backfill unrelated media into a reserved sidecar.

A V1 package passing its validator is also not proof of pose accuracy. It means only that the estimate is non-empty, temporally scoped, provenance-bearing and uncertainty-aware enough to enter the future held-out M1 comparison.

This layer does not:

- capture audio/video in the background;
- infer an intent;
- convert raw video into pose;
- validate V1 pose accuracy;
- upload private media;
- modify the original CT1 event;
- turn a one-household record into population evidence.
