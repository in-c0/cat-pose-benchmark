# CT1.3 local capture CLI

Status: capture-support tooling for the preregistered first-household pilot in #37.

This CLI is designed to reduce manual editing during the H0 instrumentation tranche. It records structured context only; it does **not** record audio, video, health data, or infer an intent.

## Capture model

Each episode has two operations:

1. `start` — freezes the prediction-time context snapshot at `t0`, fixes the 60 s outcome window, writes the #18/CT1.2 event, and writes a sidecar SHA-256 lock over all current-event predictor/identity fields.
2. `finalize` — verifies that the frozen fingerprint still matches, then appends only the end-of-window termination outcome as `terminated`, `continued`, or `unknown`.

If any frozen field was edited after `start`, finalization fails closed.

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
- `episode-001.json.ct1-lock.json` containing the frozen predictor fingerprint.

The 60 s window is fixed at start time. The event is already strict-valid before an outcome exists.

## Finalize after the frozen window

If signalling had stopped by the end of the window:

```bash
python -m context.ct1_capture_cli finalize \
  --event local-data/h0/episode-001.json \
  --outcome terminated
```

If it had not stopped:

```bash
python -m context.ct1_capture_cli finalize \
  --event local-data/h0/episode-001.json \
  --outcome continued
```

If the state could not be observed reliably:

```bash
python -m context.ct1_capture_cli finalize \
  --event local-data/h0/episode-001.json \
  --outcome unknown
```

`unknown` is preferable to retrospectively guessing.

## H0 audit

After the first 10 eligible strict-valid episodes, put the event objects into one JSON array and run:

```bash
python -m context.ct1_h0_audit h0-events.json --output h0-audit.json
python -m context.ct1_h1_sizing h0-audit.json --output h1-sizing.json
```

The H0 path is intentionally performance-blind. Do not fit CT1 predictors or inspect feature/target associations before the H1 size/split is frozen as required by #37.

## Data handling boundary

- This tool is local-first; generated household data should stay outside the public repo.
- Use pseudonymous subject/household/person IDs.
- Do not manufacture signalling episodes through deprivation, denied access, restraint, startle, or distress.
- Ordinary care takes precedence over completing the 60 s window.
- `unknown`/excluded episodes remain part of the audit trail.
- This instrumentation does not establish literal feline language, emotion, pain, disease, or universal semantics.
