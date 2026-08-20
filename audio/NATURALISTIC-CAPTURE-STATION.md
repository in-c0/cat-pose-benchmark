# A1.2 localhost naturalistic capture station

Status: prospective acquisition tooling for the A1.2 household pilot. No model inference is performed by this station.

## Purpose

The manual M1 sensor-sidecar workflow can prove that a file was reserved and later sealed, but an external recording file still depends on the operator for alignment. The A1.2 capture station closes that gap for vocal audio by controlling episode timing and PCM capture from one localhost browser interface.

The station:

1. keeps the microphone explicitly permission-gated and armed by the user;
2. starts a CT1 event from the browser's high-resolution click timestamp;
3. measures the first actual AudioWorklet input frame relative to that click;
4. reserves A1 from the measured start offset through 5,000 ms;
5. records five seconds of mono PCM in the worklet;
6. sends WAV bytes only to the loopback Python server;
7. trims/seals the WAV so the A1 artifact ends at the frozen 5,000 ms M1 cutoff;
8. leaves the CT1 outcome open until the 60-second observation window;
9. writes a separate A1-enriched event after CT1 finalization.

The original CT1 event and lock remain the canonical prospective context/outcome record.

## Browser requirements

The UI uses:

- `navigator.mediaDevices.getUserMedia()` for explicit microphone permission;
- `AudioWorklet` for off-main-thread PCM acquisition;
- `performance.timeOrigin + performance.now()` for the browser high-resolution epoch anchor.

Serve the page through the included localhost server. Do not open the HTML directly from an arbitrary remote host.

## Start the station

Use the same-origin-hardened launcher from the repository root:

```bash
python -m audio.a1_capture_station_secure \
  --output-dir local-data/a1-naturalistic \
  --subject-id cat-01 \
  --household-id hh-01 \
  --session-id session-001 \
  --open-browser
```

Default URL:

```text
http://127.0.0.1:8765/
```

The first implementation rejects non-loopback bind addresses. The lower-level `audio.a1_capture_station` module contains the tested capture state machine and core HTTP implementation; the documented operator entry point is the hardened wrapper above.

## Before an episode

Keep the page open and:

1. set the current location/object/social/environment context;
2. explicitly choose whether human audio may be present;
3. click **Arm microphone** and grant browser permission.

Arming does not create an event and does not begin episode recording. It keeps a live microphone stream available so an episode can be started without a permission-dialog delay.

## At a naturally occurring episode

Click:

**Start episode + capture first 5 s**

Do not induce hunger, deny ordinary access, startle, restrain, or otherwise manufacture signalling for the study.

At the click:

- the browser snapshots `t0`;
- the worklet begins capturing at its next input frame;
- the loopback server writes the CT1 event and lock;
- the first-worklet-frame offset is measured rather than assumed to be zero;
- A1 is reserved from that measured offset through 5,000 ms;
- exactly five seconds of PCM are collected in the browser;
- the server retains only the portion needed to end the sealed evidence at 5,000 ms.

The page then displays only capture integrity/status. It does not display an intent guess.

## At the 60-second outcome boundary

The three outcome controls become active:

- `terminated` — signalling had terminated by 60 seconds;
- `continued` — signalling was still occurring at 60 seconds;
- `unknown` — the state could not be observed reliably.

After selection, the server finalizes the original CT1 record. When audio sealed successfully, it also writes a separate `.a1.m1.json` derived event using the M1.3 sidecar composition contract.

## Local files

For an event such as `a1-...`, the output directory can contain:

- `<event>.json` — canonical finalized CT1 event;
- `<event>.json.ct1-lock.json` — CT1 integrity lock;
- `<event>.a1-sidecar.json` — local A1 reservation/seal record;
- `<event>.a1.wav` — local trimmed WAV artifact;
- `<event>.a1.m1.json` — derived audio-enriched #18 event;
- `<event>.a1.readiness.json` — performance-blind M1 support/readiness summary.

These local household files are not intended for the public repository.

## Privacy and network boundary

- server binds to loopback only;
- the documented launcher validates the HTTP `Host` header against loopback names and the actual bound port;
- every state-changing request requires a matching same-origin `Origin` header;
- cross-site `Sec-Fetch-Site` values are rejected when supplied by the browser;
- JSON endpoints require `application/json`, and audio upload requires a WAV media type, preventing simple cross-origin form/text POSTs from reaching mutation handlers;
- `OPTIONS`/preflight requests are not enabled as an alternate cross-origin path;
- no cloud upload path is implemented;
- no permissive CORS endpoint is implemented;
- microphone permission is controlled by the browser and must be explicitly granted;
- request sizes are bounded;
- event IDs and configured pseudonymous IDs are path-sanitized;
- the A1 sidecar records whether human audio may be present;
- raw local file paths are removed from the derived M1 event by the sidecar composer;
- `restricted`/`private_household` is not silently upgraded to research consent.

Loopback binding by itself is not treated as a browser security boundary. The same-origin wrapper exists because browsers can issue some requests to localhost even when CORS prevents them from reading responses, and DNS rebinding can make Host validation relevant.

## Clock interpretation

The browser click time and AudioContext frame clock are used for within-machine synchronization. The first audio frame is allowed to occur slightly after `t0`; that measured delay becomes A1's actual `start_offset_ms`.

The server does not claim sub-millisecond absolute synchronization. The CT1 record retains a conservative browser/server clock-uncertainty value, and the first programme experiment uses a coarse 0–5 s evidence window rather than relying on exact millisecond behavioural semantics.

## Recovery

If the page reloads while an episode is open, use **Refresh status** and **Resume latest open episode**. This resumes only the 60-second outcome annotation state; it cannot retroactively recreate missing audio. An episode with missing audio remains a valid CT1 record but will not qualify as A1/M1-complete.

## Claims boundary

A synchronized audio episode provides prospective acoustic evidence associated with an observable event. It does not by itself establish:

- a universal meow meaning;
- an English-language translation;
- emotion/pain/disease;
- cross-cat generalisation;
- causal interpretation of ordinary human actions.
