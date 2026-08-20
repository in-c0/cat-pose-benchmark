# CT1.3 local capture CLI

Status: capture-support tooling for the preregistered first-household pilot in #37.

This CLI is designed to reduce manual editing during the H0 instrumentation tranche. It records structured context and ordinary timestamped human actions only; it does **not** record audio, video, health data, or infer an intent.

## Capture model

Each episode has three operations:

1. `start` — freezes the prediction-time context snapshot at `t0`, fixes the 60 s outcome window, writes the #18/CT1.2 event, and writes a sidecar SHA-256 lock over all current-event predictor/identity fields.
2. `action` — optionally appends an ordinary human action with an in-window timestamp. Actions are not current-episode CT1 predictors, but they can become routine/history evidence for later episodes. The append log has its own hash so recorded actions cannot be retrospectively rewritten.
3. `finalize` — verifies both the frozen `t0` fingerprint and append-only action-log hash, then appends the end-of-window termination outcome as `terminated`, `continued`, or `unknown`.

If any frozen field or previously recorded action is edited after capture, the next mutation fails closed.

## Context input

Use a local JSON object with these fields:

```json
{
  "location": "hallway",
  "objects": [
    {
      "object_id": "door-balcony",
      "object_type": "door",
      "state": {"open": false},
      "relation_to_subject": "subject-facing"
    }
  ],
  "social": [],
  "environment": {}
}
```

A synthetic example is committed at `context/fixtures/ct1_context_input.example.json`.

Do not commit private household context/event files to the public repository. The CLI defaults generated records to `private_household` + `restricted`, and it records no human audio/image.

## Start an episode

```bash
python -m context.ct1_capture_cli start \
  --output local-data/h0/episode-001.json \
  --context local-data/context-current.json \
  --subject-id cat-01 \
  --household-id hh-01 \
  --session-id 2026-08-21-am
```

The tool writes:

- the prospective event JSON;
- `episode-001.json.ct1-lock.json` containing the frozen predictor fingerprint and action-log fingerprint.

The 60 s window is fixed at start time. The event is already strict-valid before an outcome exists.

## Log an ordinary action during the window

If a relevant ordinary action occurs, log it at the time it happens:

```bash
python -m context.ct1_capture_cli action \
  --event local-data/h0/episode-001.json \
  --action-type open_door \
  --actor-id human-01 \
  --target-id door-balcony
```

If `--offset-ms` is omitted, the CLI calculates elapsed time from the frozen event start. For deterministic import/testing, an explicit offset may be supplied.

Only actions inside the frozen 0–60 s episode window are accepted. Do not create actions for experimental discrimination unless the episode separately follows the prospective I1 protocol in #20.

## Finalize after the frozen window

```bash
python -m context.ct1_capture_cli finalize \
  --event local-data/h0/episode-001.json \
  --outcome terminated
```

Allowed outcomes are `terminated`, `continued`, and `unknown`. `unknown` is preferable to retrospectively guessing.

## Performance-blind collection status

At any point during H0, inspect the local capture directory without fitting a model:

```bash
python -m context.ct1_capture_batch status \
  --directory local-data/h0 \
  --output local-data/h0-status.json
```

The status report checks:

- sidecar lock presence;
- frozen `t0` fingerprint integrity;
- append-only action-log integrity;
- completed-event hash integrity;
- strict CT1.2 validation;
- open/finalized/unknown counts;
- whether the 10 strict-valid finalized H0 target has been reached.

It performs no predictor-performance analysis.

## Bundle H0 events

Once captures are finalized, create the chronological audit bundle and manifest:

```bash
python -m context.ct1_capture_batch bundle \
  --directory local-data/h0 \
  --output local-data/h0-events.json \
  --manifest local-data/h0-manifest.json
```

Bundling fails closed if it finds a duplicate event ID, missing lock, invalid event, or fingerprint/hash mismatch. Valid but still-open episodes are left out of the bundle rather than force-finalized.

Then run the preregistered performance-blind audit and sizing path:

```bash
python -m context.ct1_h0_audit local-data/h0-events.json --output local-data/h0-audit.json
python -m context.ct1_h1_sizing local-data/h0-audit.json --output local-data/h1-sizing.json
```

Do not fit CT1 predictors or inspect feature/target associations before the H1 size/split is frozen as required by #37.

## Data handling boundary

- This tool is local-first; generated household data should stay outside the public repo.
- Use pseudonymous subject/household/person IDs.
- Do not manufacture signalling episodes through deprivation, denied access, restraint, startle, or distress.
- Ordinary care takes precedence over completing the 60 s window.
- `unknown`/excluded episodes remain part of the audit trail.
- Recorded ordinary actions are observational metadata, not evidence that an intervention revealed an intent.
- Status, bundling, H0 audit, and H1 sizing remain performance-blind until the preregistered H1 freeze.
- This instrumentation does not establish literal feline language, emotion, pain, disease, or universal semantics.
