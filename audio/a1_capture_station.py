from __future__ import annotations

import argparse
import io
import json
import math
import re
import threading
import time
import uuid
import wave
import webbrowser
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from context.ct1_capture_cli import (
    build_lock,
    build_started_event,
    default_lock_path,
    finalize_event,
)
from fusion.m1_cohort_manifest import SENSOR_EVIDENCE_CUTOFF_MS, build_manifest
from fusion.m1_sensor_sidecar import (
    build_reservation,
    compose_enriched_event,
    seal_sidecar,
)

STATION_VERSION = "A1.2-browser-capture-v0"
STATIC_ROOT = Path(__file__).with_name("capture_station")
MAX_JSON_BYTES = 64 * 1024
MAX_WAV_BYTES = 8 * 1024 * 1024
SAFE_ID = re.compile(r"^[A-Za-z0-9._+-]{1,128}$")
ALLOWED_HOSTS = {"127.0.0.1", "localhost", "::1"}
AUDIO_SCHEMA_REF = "audio/A1-naturalistic-wav-v0"


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _atomic_json(path: Path, payload: Any, *, exclusive: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if exclusive and path.exists():
        raise FileExistsError(f"refusing to overwrite existing file: {path}")
    temp = path.with_name(path.name + f".tmp-{uuid.uuid4().hex[:8]}")
    temp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if exclusive and path.exists():
        temp.unlink(missing_ok=True)
        raise FileExistsError(f"refusing to overwrite existing file: {path}")
    temp.replace(path)


def _safe_id(value: str, field: str) -> str:
    if not isinstance(value, str) or not SAFE_ID.fullmatch(value):
        raise ValueError(
            f"{field} must contain only letters, digits, '.', '_', '+', '-' and be <=128 characters"
        )
    return value


def _event_id_from_t0(t0: datetime) -> str:
    token = uuid.uuid4().hex[:10]
    stamp = t0.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return f"a1-{stamp}-{token}"


def _client_epoch_to_datetime(epoch_ms: float) -> datetime:
    if not isinstance(epoch_ms, (int, float)) or not math.isfinite(float(epoch_ms)):
        raise ValueError("client_t0_epoch_ms must be finite numeric")
    # Reject timestamps that cannot plausibly be from the local browser session.
    server_now_ms = time.time() * 1000.0
    if abs(float(epoch_ms) - server_now_ms) > 5 * 60 * 1000:
        raise ValueError("client_t0_epoch_ms differs from local server wall time by more than 5 minutes")
    return datetime.fromtimestamp(float(epoch_ms) / 1000.0, tz=timezone.utc).astimezone()


def _trim_pcm16_mono_wav(data: bytes, duration_seconds: float) -> tuple[bytes, dict[str, Any]]:
    if duration_seconds <= 0:
        raise ValueError("requested WAV duration must be positive")
    try:
        with wave.open(io.BytesIO(data), "rb") as source:
            channels = source.getnchannels()
            width = source.getsampwidth()
            rate = source.getframerate()
            compression = source.getcomptype()
            available_frames = source.getnframes()
            if channels != 1:
                raise ValueError("browser A1 WAV must be mono")
            if width != 2:
                raise ValueError("browser A1 WAV must be PCM16")
            if compression != "NONE":
                raise ValueError("browser A1 WAV must be uncompressed PCM")
            if rate <= 0:
                raise ValueError("browser A1 WAV sample rate must be positive")
            required_frames = int(round(rate * duration_seconds))
            if available_frames < required_frames:
                raise ValueError(
                    f"browser WAV has {available_frames} frames but {required_frames} are required"
                )
            frames = source.readframes(required_frames)
    except (wave.Error, EOFError) as exc:
        raise ValueError(f"uploaded A1 bytes are not a readable WAV: {exc}") from exc

    output = io.BytesIO()
    with wave.open(output, "wb") as target:
        target.setnchannels(1)
        target.setsampwidth(2)
        target.setframerate(rate)
        target.writeframes(frames)
    trimmed = output.getvalue()
    return trimmed, {
        "sample_rate_hz": rate,
        "frames": required_frames,
        "duration_seconds": required_frames / rate,
        "source_frames_received": available_frames,
    }


class CaptureStore:
    """Local-only CT1+A1 state machine. No model fitting or network upload."""

    def __init__(
        self,
        root: Path,
        *,
        subject_id: str,
        household_id: str,
        session_id: str,
    ) -> None:
        self.root = root.resolve()
        self.subject_id = _safe_id(subject_id, "subject_id")
        self.household_id = _safe_id(household_id, "household_id")
        self.session_id = _safe_id(session_id, "session_id")
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def event_path(self, event_id: str) -> Path:
        return self.root / f"{_safe_id(event_id, 'event_id')}.json"

    def lock_path(self, event_id: str) -> Path:
        return default_lock_path(self.event_path(event_id))

    def sidecar_path(self, event_id: str) -> Path:
        return self.root / f"{_safe_id(event_id, 'event_id')}.a1-sidecar.json"

    def wav_path(self, event_id: str) -> Path:
        return self.root / f"{_safe_id(event_id, 'event_id')}.a1.wav"

    def enriched_path(self, event_id: str) -> Path:
        return self.root / f"{_safe_id(event_id, 'event_id')}.a1.m1.json"

    def readiness_path(self, event_id: str) -> Path:
        return self.root / f"{_safe_id(event_id, 'event_id')}.a1.readiness.json"

    def start_episode(
        self,
        *,
        context: dict[str, Any],
        client_t0_epoch_ms: float,
        client_clock_uncertainty_ms: float = 25.0,
    ) -> dict[str, Any]:
        if not isinstance(context, dict):
            raise ValueError("context must be a JSON object")
        if not isinstance(client_clock_uncertainty_ms, (int, float)) or not math.isfinite(
            float(client_clock_uncertainty_ms)
        ):
            raise ValueError("client_clock_uncertainty_ms must be finite numeric")
        uncertainty = max(5.0, min(float(client_clock_uncertainty_ms), 1000.0))
        started = _client_epoch_to_datetime(float(client_t0_epoch_ms))
        event_id = _event_id_from_t0(started)

        with self._lock:
            event = build_started_event(
                context=context,
                subject_id=self.subject_id,
                household_id=self.household_id,
                session_id=self.session_id,
                event_id=event_id,
                started_at=started,
                clock_uncertainty_ms=uncertainty,
            )
            event["time"]["clock_source"] = "browser-performance.timeOrigin+performance.now"
            snapshot = event["observations"][0]["features"]
            snapshot["provenance"]["notes"] = (
                "Prediction-time context anchored to browser high-resolution epoch supplied by the loopback A1.2 capture station."
            )
            snapshot.setdefault("uncertainty", {})["browser_server_clock_uncertainty_ms"] = uncertainty
            event["provenance"]["lineage"].append(
                "A1.2 localhost capture station browser-t0 start"
            )
            event["provenance"]["software_versions"]["a1_capture_station"] = STATION_VERSION
            lock = build_lock(event)

            _atomic_json(self.event_path(event_id), event, exclusive=True)
            _atomic_json(self.lock_path(event_id), lock, exclusive=True)

        return {
            "event_id": event_id,
            "episode_id": event["episode_id"],
            "start_time": event["time"]["start_time"],
            "target_horizon_ms": 60_000,
            "sensor_cutoff_ms": SENSOR_EVIDENCE_CUTOFF_MS,
        }

    def reserve_audio(
        self,
        event_id: str,
        *,
        first_audio_offset_ms: int,
        human_audio_may_be_present: bool,
    ) -> dict[str, Any]:
        _safe_id(event_id, "event_id")
        if not isinstance(first_audio_offset_ms, int):
            raise ValueError("first_audio_offset_ms must be an integer")
        if not 0 <= first_audio_offset_ms < SENSOR_EVIDENCE_CUTOFF_MS:
            raise ValueError("first_audio_offset_ms must fall inside 0-5000 ms")
        if not isinstance(human_audio_may_be_present, bool):
            raise ValueError("human_audio_may_be_present must be boolean")

        with self._lock:
            sidecar_path = self.sidecar_path(event_id)
            if sidecar_path.exists():
                raise FileExistsError("A1 sidecar already exists for this event")
            event = _load_json(self.event_path(event_id))
            lock = _load_json(self.lock_path(event_id))
            sidecar = build_reservation(
                event,
                lock,
                modality="audio_vocalisation",
                schema_ref=AUDIO_SCHEMA_REF,
                human_content="audio" if human_audio_may_be_present else "none",
                start_offset_ms=first_audio_offset_ms,
                end_offset_ms=SENSOR_EVIDENCE_CUTOFF_MS,
                reserved_at=datetime.now().astimezone(),
                observation_ref=f"a1-browser:{event_id}",
                record_id=f"a1-browser-record:{event_id}",
            )
            sidecar["capture_station"] = {
                "version": STATION_VERSION,
                "alignment_method": "browser_audio_context_first_frame_relative_to_click_t0",
                "first_audio_offset_ms": first_audio_offset_ms,
            }
            # capture_station is intentionally outside the reservation projection;
            # the authoritative frozen timing is already stored in start/end offsets.
            _atomic_json(sidecar_path, sidecar, exclusive=True)

        return {
            "event_id": event_id,
            "first_audio_offset_ms": first_audio_offset_ms,
            "reserved_end_offset_ms": SENSOR_EVIDENCE_CUTOFF_MS,
            "required_wav_duration_ms": SENSOR_EVIDENCE_CUTOFF_MS - first_audio_offset_ms,
        }

    def save_audio(self, event_id: str, wav_bytes: bytes) -> dict[str, Any]:
        _safe_id(event_id, "event_id")
        if not isinstance(wav_bytes, (bytes, bytearray)):
            raise ValueError("WAV payload must be bytes")
        if len(wav_bytes) > MAX_WAV_BYTES:
            raise ValueError(f"WAV payload exceeds {MAX_WAV_BYTES} byte limit")
        if len(wav_bytes) < 44:
            raise ValueError("WAV payload is too small")

        with self._lock:
            sidecar_path = self.sidecar_path(event_id)
            sidecar = _load_json(sidecar_path)
            if sidecar.get("state") != "reserved":
                raise FileExistsError("A1 sidecar is already sealed")
            wav_path = self.wav_path(event_id)
            if wav_path.exists():
                raise FileExistsError("A1 WAV already exists for this event")

            duration_s = (
                sidecar["end_offset_ms"] - sidecar["start_offset_ms"]
            ) / 1000.0
            trimmed, trim_metadata = _trim_pcm16_mono_wav(bytes(wav_bytes), duration_s)
            wav_path.write_bytes(trimmed)
            try:
                sealed = seal_sidecar(sidecar, wav_path)
            except Exception:
                wav_path.unlink(missing_ok=True)
                raise
            sealed["capture_station"]["trim"] = trim_metadata
            _atomic_json(sidecar_path, sealed)

        return {
            "event_id": event_id,
            "state": "sealed",
            "sha256": sealed["seal"]["file_sha256"],
            "byte_length": sealed["seal"]["byte_length"],
            "media_metadata": sealed["seal"]["media_metadata"],
        }

    def finalize(self, event_id: str, outcome: str) -> dict[str, Any]:
        _safe_id(event_id, "event_id")
        if outcome not in {"terminated", "continued", "unknown"}:
            raise ValueError("outcome must be terminated, continued, or unknown")
        terminated = {
            "terminated": True,
            "continued": False,
            "unknown": None,
        }[outcome]

        with self._lock:
            event_path = self.event_path(event_id)
            event = _load_json(event_path)
            lock_path = self.lock_path(event_id)
            lock = _load_json(lock_path)
            finalized, finalized_lock = finalize_event(event, lock, terminated=terminated)
            _atomic_json(event_path, finalized)
            _atomic_json(lock_path, finalized_lock)

            enriched_path = self.enriched_path(event_id)
            readiness_event = finalized
            enriched_written = False
            sidecar_path = self.sidecar_path(event_id)
            if sidecar_path.exists():
                sidecar = _load_json(sidecar_path)
                if sidecar.get("state") == "sealed":
                    if enriched_path.exists():
                        raise FileExistsError("derived A1 event already exists")
                    enriched = compose_enriched_event(finalized, finalized_lock, [sidecar])
                    _atomic_json(enriched_path, enriched, exclusive=True)
                    readiness_event = enriched
                    enriched_written = True

            manifest = build_manifest([readiness_event])
            row = manifest["events"][0]
            readiness = {
                "event_id": event_id,
                "outcome": outcome,
                "a1_enriched_event_written": enriched_written,
                "support": row["support"],
                "primary_cohort_eligible": row["primary_cohort_eligible"],
                "exclusion_reasons": row["exclusion_reasons"],
                "performance_analysis_performed": False,
            }
            _atomic_json(self.readiness_path(event_id), readiness)
            return readiness

    def status(self) -> dict[str, Any]:
        rows: list[dict[str, Any]] = []
        for path in sorted(self.root.glob("a1-*.json")):
            if any(
                suffix in path.name
                for suffix in (".a1-sidecar.json", ".a1.m1.json", ".a1.readiness.json", ".ct1-lock.json")
            ):
                continue
            try:
                event = _load_json(path)
                event_id = _safe_id(event["event_id"], "event_id")
                lock = _load_json(self.lock_path(event_id))
                sidecar_path = self.sidecar_path(event_id)
                sidecar_state = None
                if sidecar_path.exists():
                    sidecar_state = _load_json(sidecar_path).get("state")
                rows.append(
                    {
                        "event_id": event_id,
                        "start_time": event["time"]["start_time"],
                        "finalized": lock.get("finalized") is True,
                        "audio_state": sidecar_state,
                        "derived_audio_event": self.enriched_path(event_id).exists(),
                    }
                )
            except Exception as exc:
                rows.append({"file": path.name, "integrity_error": str(exc)})
        return {
            "station_version": STATION_VERSION,
            "performance_analysis_performed": False,
            "events": rows,
        }


class CaptureHandler(BaseHTTPRequestHandler):
    server_version = "A1CaptureStation/0"
    store: CaptureStore

    def log_message(self, format: str, *args: Any) -> None:
        print(f"[a1-capture] {self.address_string()} {format % args}")

    def _common_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")

    def _json(self, status: int, payload: Any) -> None:
        data = json.dumps(payload, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self._common_headers()
        self.end_headers()
        self.wfile.write(data)

    def _error(self, status: int, message: str) -> None:
        self._json(status, {"ok": False, "error": message})

    def _read_body(self, limit: int) -> bytes:
        raw_length = self.headers.get("Content-Length")
        if raw_length is None:
            raise ValueError("Content-Length is required")
        try:
            length = int(raw_length)
        except ValueError as exc:
            raise ValueError("invalid Content-Length") from exc
        if length < 0 or length > limit:
            raise ValueError(f"request body exceeds {limit} byte limit")
        return self.rfile.read(length)

    def _read_json_body(self) -> dict[str, Any]:
        raw = self._read_body(MAX_JSON_BYTES)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"invalid JSON request: {exc}") from exc
        if not isinstance(payload, dict):
            raise ValueError("JSON request body must be an object")
        return payload

    def do_OPTIONS(self) -> None:
        self._error(HTTPStatus.METHOD_NOT_ALLOWED, "cross-origin/preflight requests are not supported")

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/config":
            self._json(
                HTTPStatus.OK,
                {
                    "station_version": STATION_VERSION,
                    "subject_id": self.store.subject_id,
                    "household_id": self.store.household_id,
                    "session_id": self.store.session_id,
                    "sensor_cutoff_ms": SENSOR_EVIDENCE_CUTOFF_MS,
                    "target_horizon_ms": 60_000,
                    "performance_analysis_performed": False,
                },
            )
            return
        if path == "/api/status":
            self._json(HTTPStatus.OK, self.store.status())
            return

        static = {
            "/": ("index.html", "text/html; charset=utf-8"),
            "/app.js": ("app.js", "text/javascript; charset=utf-8"),
            "/recorder-worklet.js": ("recorder-worklet.js", "text/javascript; charset=utf-8"),
        }.get(path)
        if static is None:
            self._error(HTTPStatus.NOT_FOUND, "not found")
            return
        filename, content_type = static
        target = STATIC_ROOT / filename
        try:
            data = target.read_bytes()
        except FileNotFoundError:
            self._error(HTTPStatus.INTERNAL_SERVER_ERROR, "capture station static asset missing")
            return
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; connect-src 'self'; media-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'",
        )
        self._common_headers()
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        try:
            if path == "/api/start":
                payload = self._read_json_body()
                result = self.store.start_episode(
                    context=payload.get("context"),
                    client_t0_epoch_ms=payload.get("client_t0_epoch_ms"),
                    client_clock_uncertainty_ms=payload.get("client_clock_uncertainty_ms", 25.0),
                )
                self._json(HTTPStatus.CREATED, {"ok": True, **result})
                return

            match = re.fullmatch(r"/api/reserve-audio/([^/]+)", path)
            if match:
                event_id = _safe_id(unquote(match.group(1)), "event_id")
                payload = self._read_json_body()
                result = self.store.reserve_audio(
                    event_id,
                    first_audio_offset_ms=payload.get("first_audio_offset_ms"),
                    human_audio_may_be_present=payload.get("human_audio_may_be_present"),
                )
                self._json(HTTPStatus.CREATED, {"ok": True, **result})
                return

            match = re.fullmatch(r"/api/audio/([^/]+)", path)
            if match:
                event_id = _safe_id(unquote(match.group(1)), "event_id")
                wav_bytes = self._read_body(MAX_WAV_BYTES)
                result = self.store.save_audio(event_id, wav_bytes)
                self._json(HTTPStatus.CREATED, {"ok": True, **result})
                return

            match = re.fullmatch(r"/api/finalize/([^/]+)", path)
            if match:
                event_id = _safe_id(unquote(match.group(1)), "event_id")
                payload = self._read_json_body()
                result = self.store.finalize(event_id, payload.get("outcome"))
                self._json(HTTPStatus.OK, {"ok": True, **result})
                return

            self._error(HTTPStatus.NOT_FOUND, "not found")
        except FileNotFoundError as exc:
            self._error(HTTPStatus.NOT_FOUND, str(exc))
        except FileExistsError as exc:
            self._error(HTTPStatus.CONFLICT, str(exc))
        except (ValueError, KeyError, TypeError) as exc:
            self._error(HTTPStatus.BAD_REQUEST, str(exc))
        except Exception as exc:  # fail closed without a browser traceback
            self._error(HTTPStatus.INTERNAL_SERVER_ERROR, f"capture station error: {exc}")


def handler_for(store: CaptureStore) -> type[CaptureHandler]:
    class BoundCaptureHandler(CaptureHandler):
        pass

    BoundCaptureHandler.store = store
    return BoundCaptureHandler


def serve(
    store: CaptureStore,
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
    open_browser_window: bool = False,
) -> None:
    if host not in ALLOWED_HOSTS:
        raise ValueError("A1.2 capture station may bind only to localhost/loopback")
    if not 1 <= port <= 65535:
        raise ValueError("port must be in 1..65535")
    server = ThreadingHTTPServer((host, port), handler_for(store))
    url = f"http://{host}:{server.server_address[1]}/"
    print(f"A1.2 capture station: {url}")
    print(f"Local data directory: {store.root}")
    print("No model inference is performed. Keep this page local and explicitly arm the microphone.")
    if open_browser_window:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the localhost-only A1.2 synchronized browser capture station"
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--subject-id", required=True)
    parser.add_argument("--household-id", required=True)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--open-browser", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    store = CaptureStore(
        args.output_dir,
        subject_id=args.subject_id,
        household_id=args.household_id,
        session_id=args.session_id,
    )
    serve(
        store,
        host=args.host,
        port=args.port,
        open_browser_window=args.open_browser,
    )


if __name__ == "__main__":
    main()
