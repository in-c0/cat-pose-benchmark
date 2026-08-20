from __future__ import annotations

import io
import json
import tempfile
import time
import unittest
import wave
from pathlib import Path

from audio.a1_capture_station import (
    MAX_WAV_BYTES,
    CaptureStore,
    _safe_id,
    _trim_pcm16_mono_wav,
    serve,
)
from context.ct1_capture import validate_capture_event
from context.ct1_capture_cli import action_log_fingerprint, predictor_fingerprint
from fusion.m1_cohort_manifest import build_manifest
from fusion.m1_sensor_sidecar import verify_sealed_sidecar


CONTEXT = {
    "location": "hallway",
    "objects": [
        {
            "object_id": "door-test",
            "object_type": "door",
            "state": {"open": False},
        }
    ],
    "social": [],
    "environment": {"synthetic": True},
}


def make_wav(duration_seconds: float = 5.0, rate: int = 8_000) -> bytes:
    output = io.BytesIO()
    with wave.open(output, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(b"\x00\x00" * int(rate * duration_seconds))
    return output.getvalue()


class A1CaptureStationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.store = CaptureStore(
            self.root,
            subject_id="cat-test",
            household_id="hh-test",
            session_id="session-test",
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def start(self) -> dict:
        return self.store.start_episode(
            context=CONTEXT,
            client_t0_epoch_ms=time.time() * 1000.0,
            client_clock_uncertainty_ms=20.0,
        )

    def test_browser_t0_start_creates_valid_locked_ct1_event(self) -> None:
        started = self.start()
        event = json.loads(self.store.event_path(started["event_id"]).read_text())
        lock = json.loads(self.store.lock_path(started["event_id"]).read_text())
        self.assertEqual([], validate_capture_event(event))
        self.assertEqual(
            "browser-performance.timeOrigin+performance.now",
            event["time"]["clock_source"],
        )
        self.assertEqual(lock["predictor_fingerprint_sha256"], predictor_fingerprint(event))
        self.assertEqual(lock["action_log_fingerprint_sha256"], action_log_fingerprint(event))
        self.assertFalse(lock["finalized"])
        self.assertFalse(self.store.sidecar_path(started["event_id"]).exists())

    def test_measured_audio_offset_reserves_and_upload_seals_trimmed_wav(self) -> None:
        started = self.start()
        event_id = started["event_id"]
        reservation = self.store.reserve_audio(
            event_id,
            first_audio_offset_ms=12,
            human_audio_may_be_present=True,
        )
        self.assertEqual(12, reservation["first_audio_offset_ms"])
        upload = self.store.save_audio(event_id, make_wav())
        self.assertEqual("sealed", upload["state"])
        self.assertAlmostEqual(4.988, upload["media_metadata"]["duration_seconds"], places=3)

        sidecar = json.loads(self.store.sidecar_path(event_id).read_text())
        event = json.loads(self.store.event_path(event_id).read_text())
        lock = json.loads(self.store.lock_path(event_id).read_text())
        verify_sealed_sidecar(sidecar, event, lock)
        self.assertTrue(sidecar["contains_human_audio"])
        self.assertEqual(12, sidecar["start_offset_ms"])
        self.assertEqual(5000, sidecar["end_offset_ms"])

    def test_finalize_preserves_base_and_writes_separate_a1_event(self) -> None:
        started = self.start()
        event_id = started["event_id"]
        self.store.reserve_audio(
            event_id,
            first_audio_offset_ms=5,
            human_audio_may_be_present=False,
        )
        self.store.save_audio(event_id, make_wav())
        result = self.store.finalize(event_id, "terminated")
        self.assertTrue(result["a1_enriched_event_written"])

        base = json.loads(self.store.event_path(event_id).read_text())
        lock = json.loads(self.store.lock_path(event_id).read_text())
        enriched = json.loads(self.store.enriched_path(event_id).read_text())
        self.assertTrue(lock["finalized"])
        self.assertEqual(lock["predictor_fingerprint_sha256"], predictor_fingerprint(base))
        self.assertEqual(lock["action_log_fingerprint_sha256"], action_log_fingerprint(base))
        self.assertNotEqual(base["observations"], enriched["observations"])
        self.assertIn("audio_vocalisation", base["missing_modalities"])
        self.assertNotIn("audio_vocalisation", enriched["missing_modalities"])
        self.assertFalse(build_manifest([base])["events"][0]["support"]["A1_vocal_audio"])
        self.assertTrue(build_manifest([enriched])["events"][0]["support"]["A1_vocal_audio"])
        self.assertFalse(result["performance_analysis_performed"])

    def test_finalize_without_audio_keeps_ct1_valid_and_no_enriched_file(self) -> None:
        started = self.start()
        event_id = started["event_id"]
        result = self.store.finalize(event_id, "unknown")
        self.assertFalse(result["a1_enriched_event_written"])
        self.assertFalse(self.store.enriched_path(event_id).exists())
        base = json.loads(self.store.event_path(event_id).read_text())
        self.assertEqual([], validate_capture_event(base))

    def test_duplicate_audio_upload_is_rejected(self) -> None:
        started = self.start()
        event_id = started["event_id"]
        self.store.reserve_audio(
            event_id,
            first_audio_offset_ms=1,
            human_audio_may_be_present=False,
        )
        wav = make_wav()
        self.store.save_audio(event_id, wav)
        with self.assertRaisesRegex(FileExistsError, "already sealed"):
            self.store.save_audio(event_id, wav)

    def test_duplicate_reservation_is_rejected(self) -> None:
        started = self.start()
        event_id = started["event_id"]
        self.store.reserve_audio(
            event_id,
            first_audio_offset_ms=1,
            human_audio_may_be_present=False,
        )
        with self.assertRaisesRegex(FileExistsError, "already exists"):
            self.store.reserve_audio(
                event_id,
                first_audio_offset_ms=2,
                human_audio_may_be_present=False,
            )

    def test_duplicate_finalization_is_rejected(self) -> None:
        started = self.start()
        event_id = started["event_id"]
        self.store.finalize(event_id, "continued")
        with self.assertRaisesRegex(ValueError, "already been finalized"):
            self.store.finalize(event_id, "continued")

    def test_oversize_wav_is_rejected_before_disk_write(self) -> None:
        started = self.start()
        event_id = started["event_id"]
        self.store.reserve_audio(
            event_id,
            first_audio_offset_ms=1,
            human_audio_may_be_present=False,
        )
        with self.assertRaisesRegex(ValueError, "exceeds"):
            self.store.save_audio(event_id, b"0" * (MAX_WAV_BYTES + 1))
        self.assertFalse(self.store.wav_path(event_id).exists())

    def test_path_traversal_and_non_pseudonymous_ids_are_rejected(self) -> None:
        for value in ("../secret", "a/b", "", "x" * 129):
            with self.assertRaises(ValueError):
                _safe_id(value, "event_id")
        with self.assertRaises(ValueError):
            CaptureStore(
                self.root / "bad",
                subject_id="cat/test",
                household_id="hh",
                session_id="s",
            )

    def test_non_loopback_bind_is_rejected_before_server_start(self) -> None:
        with self.assertRaisesRegex(ValueError, "only to localhost"):
            serve(self.store, host="0.0.0.0", port=8765)

    def test_trim_rejects_non_mono_or_too_short_audio(self) -> None:
        short = make_wav(duration_seconds=1.0)
        with self.assertRaisesRegex(ValueError, "required"):
            _trim_pcm16_mono_wav(short, 4.9)

        output = io.BytesIO()
        with wave.open(output, "wb") as handle:
            handle.setnchannels(2)
            handle.setsampwidth(2)
            handle.setframerate(8000)
            handle.writeframes(b"\x00\x00\x00\x00" * 40000)
        with self.assertRaisesRegex(ValueError, "mono"):
            _trim_pcm16_mono_wav(output.getvalue(), 5.0)

    def test_status_is_performance_blind(self) -> None:
        self.start()
        status = self.store.status()
        self.assertFalse(status["performance_analysis_performed"])
        rendered = json.dumps(status).lower()
        for token in ("log_loss", "balanced_accuracy", "macro_f1", "prediction"):
            self.assertNotIn(token, rendered)


if __name__ == "__main__":
    unittest.main()
