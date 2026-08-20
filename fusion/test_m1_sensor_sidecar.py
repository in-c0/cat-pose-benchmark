from __future__ import annotations

import copy
import json
import tempfile
import unittest
import wave
from datetime import datetime, timedelta, timezone
from pathlib import Path

from context.ct1_capture import validate_capture_event
from context.ct1_capture_cli import (
    action_log_fingerprint,
    build_lock,
    build_started_event,
    finalize_event,
    predictor_fingerprint,
)
from fusion.m1_cohort_manifest import build_manifest
from fusion.m1_sensor_sidecar import (
    build_reservation,
    compose_enriched_event,
    seal_sidecar,
    verify_sealed_sidecar,
)
from fusion.v1_pose_package import POSE_PACKAGE_SCHEMA_REF
from programme.validate_intent_event import validate_instance


SYNTHETIC_CONTEXT = {
    "location": "hallway",
    "objects": [
        {
            "object_id": "door-example",
            "object_type": "door",
            "state": {"open": False},
            "relation_to_subject": "subject-facing",
        }
    ],
    "social": [],
    "environment": {"synthetic": True},
}


def build_open_event() -> tuple[dict, dict, datetime]:
    started = datetime(2026, 8, 21, 8, 0, tzinfo=timezone.utc)
    event = build_started_event(
        context=SYNTHETIC_CONTEXT,
        subject_id="cat-test",
        household_id="hh-test",
        session_id="session-test",
        event_id="m1-sidecar-test",
        started_at=started,
        clock_uncertainty_ms=10,
    )
    return event, build_lock(event), started


def write_wav(path: Path, duration_seconds: float = 5.0) -> None:
    rate = 8_000
    frames = int(rate * duration_seconds)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(b"\x00\x00" * frames)


def build_pose_package(
    event: dict,
    *,
    subject_id: str | None = None,
    event_id: str | None = None,
    episode_id: str | None = None,
    sequence_id: str = "synthetic-v1-sequence",
    observation_sequence_id: str | None = None,
    sample_offset_ms: float = 0.0,
    evidence_tier: str = "S2",
    include_uncertainty: bool = True,
    producer_kind: str = "learned_model",
    include_weights: bool = True,
    start_offset_ms: int = 0,
    end_offset_ms: int = 5_000,
) -> dict:
    subject = subject_id or event["subject_id"]
    producer = {
        "kind": producer_kind,
        "name": "synthetic-v1-test-producer",
        "version": "0.0-test",
        "code_revision": "synthetic-test-revision",
    }
    if producer_kind == "learned_model":
        producer["model_family"] = "synthetic-test-family"
        if include_weights:
            producer["weights_sha256"] = "b" * 64

    observation = {
        "observation_id": "synthetic-v1-frame-000-nose",
        "sequence_id": observation_sequence_id or sequence_id,
        "frame_index": 0,
        "subject_id": subject,
        "observation_class": "surface_landmark",
        "semantic_name": "nose",
        "coordinate_space": "image",
        "units": "pixels",
        "mean": [100.0, 80.0],
        "visibility": ["visible"],
        "evidence_tier": evidence_tier,
        "quality": "bronze" if evidence_tier == "S2" else "silver",
        "source_ids": ["synthetic-camera-record"],
        "lineage": ["synthetic-v1-package-test"],
    }
    if include_uncertainty:
        observation["covariance"] = [[4.0, 0.0], [0.0, 4.0]]

    return {
        "package_version": "V1-M1-pose-package-v0",
        "event_id": event_id or event["event_id"],
        "episode_id": episode_id or event["episode_id"],
        "sequence_id": sequence_id,
        "subject_id": subject,
        "evidence_window_ms": {
            "start_offset_ms": start_offset_ms,
            "end_offset_ms": end_offset_ms,
        },
        "producer": producer,
        "source_media": [
            {
                "record_id": "synthetic-video-record",
                "sha256": "a" * 64,
                "media_type": "video/webm",
                "width_px": 640,
                "height_px": 480,
                "frame_rate_hz": 30.0,
            }
        ],
        "samples": [
            {
                "event_offset_ms": sample_offset_ms,
                "frame_index": 0,
                "observations": [observation],
            }
        ],
        "notes": "software-only synthetic V1/M1 contract fixture",
    }


def write_pose_package(path: Path, event: dict, **overrides) -> dict:
    package = build_pose_package(event, **overrides)
    path.write_text(json.dumps(package, indent=2) + "\n", encoding="utf-8")
    return package


def pose_reservation(event: dict, lock: dict, started: datetime, **overrides) -> dict:
    return build_reservation(
        event,
        lock,
        modality="visual_pose",
        schema_ref=POSE_PACKAGE_SCHEMA_REF,
        human_content=overrides.pop("human_content", "none"),
        reserved_at=overrides.pop("reserved_at", started + timedelta(milliseconds=800)),
        start_offset_ms=overrides.pop("start_offset_ms", 0),
        end_offset_ms=overrides.pop("end_offset_ms", 5_000),
        **overrides,
    )


def readiness(event: dict) -> dict:
    return build_manifest([event])["events"][0]


class M1SensorSidecarTests(unittest.TestCase):
    def test_audio_sidecar_changes_only_derived_event_support(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            wav_path = root / "cat.wav"
            write_wav(wav_path)

            open_event, open_lock, started = build_open_event()
            audio = build_reservation(
                open_event,
                open_lock,
                modality="audio_vocalisation",
                schema_ref="audio/A1-naturalistic-wav-v0",
                human_content="none",
                reserved_at=started + timedelta(seconds=1),
            )
            sealed = seal_sidecar(audio, wav_path)
            finalized, finalized_lock = finalize_event(
                open_event, open_lock, terminated=True
            )

            before = readiness(finalized)
            self.assertFalse(before["support"]["A1_vocal_audio"])
            original_json = json.dumps(finalized, sort_keys=True)
            original_predictor = predictor_fingerprint(finalized)
            original_actions = action_log_fingerprint(finalized)

            enriched = compose_enriched_event(finalized, finalized_lock, [sealed])
            after = readiness(enriched)
            self.assertTrue(after["support"]["A1_vocal_audio"])
            self.assertFalse(after["support"]["V1_visual_pose"])
            self.assertFalse(after["primary_cohort_eligible"])

            self.assertEqual(original_json, json.dumps(finalized, sort_keys=True))
            self.assertEqual(original_predictor, predictor_fingerprint(finalized))
            self.assertEqual(original_actions, action_log_fingerprint(finalized))
            self.assertEqual(
                finalized_lock["completed_event_sha256"],
                __import__("hashlib").sha256(
                    json.dumps(
                        finalized,
                        sort_keys=True,
                        separators=(",", ":"),
                        ensure_ascii=False,
                    ).encode("utf-8")
                ).hexdigest(),
            )
            self.assertEqual([], validate_instance(enriched))
            self.assertEqual([], validate_capture_event(enriched))
            self.assertNotIn(str(wav_path.resolve()), json.dumps(enriched))

    def test_audio_plus_valid_pose_package_make_only_derived_event_primary_ready(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            wav_path = root / "cat.wav"
            pose_path = root / "pose.json"
            write_wav(wav_path)

            event, lock, started = build_open_event()
            write_pose_package(pose_path, event)
            audio = seal_sidecar(
                build_reservation(
                    event,
                    lock,
                    modality="audio_vocalisation",
                    schema_ref="audio/A1-naturalistic-wav-v0",
                    human_content="audio",
                    reserved_at=started + timedelta(milliseconds=500),
                ),
                wav_path,
            )
            pose = seal_sidecar(pose_reservation(event, lock, started), pose_path)
            self.assertEqual("V1-M1-pose-package-v0", pose["seal"]["media_metadata"]["package_version"])
            self.assertEqual(1, pose["seal"]["media_metadata"]["sample_count"])
            self.assertEqual(1, pose["seal"]["media_metadata"]["observation_count"])
            self.assertEqual({"S2": 1}, pose["seal"]["media_metadata"]["evidence_tier_counts"])

            finalized, finalized_lock = finalize_event(event, lock, terminated=True)
            self.assertFalse(readiness(finalized)["primary_cohort_eligible"])

            enriched = compose_enriched_event(
                finalized, finalized_lock, [audio, pose]
            )
            row = readiness(enriched)
            self.assertTrue(row["primary_cohort_eligible"])
            self.assertTrue(row["support"]["B0_context_routine"])
            self.assertTrue(row["support"]["V1_visual_pose"])
            self.assertTrue(row["support"]["A1_vocal_audio"])
            self.assertTrue(enriched["privacy"]["contains_human_audio"])
            self.assertFalse(enriched["privacy"]["contains_human_image"])
            self.assertEqual("restricted", enriched["privacy"]["consent_status"])

    def test_visual_pose_reservation_requires_canonical_package_schema(self) -> None:
        event, lock, started = build_open_event()
        with self.assertRaisesRegex(ValueError, "v1_pose_package.schema.json"):
            build_reservation(
                event,
                lock,
                modality="visual_pose",
                schema_ref="schemas/observation.schema.json",
                human_content="none",
                reserved_at=started + timedelta(milliseconds=100),
            )

    def test_empty_json_cannot_be_sealed_as_visual_pose(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "empty.json"
            path.write_text("{}\n", encoding="utf-8")
            event, lock, started = build_open_event()
            with self.assertRaisesRegex(ValueError, "V1 pose package is invalid"):
                seal_sidecar(pose_reservation(event, lock, started), path)

    def test_pose_package_rejects_synthetic_or_unlabelled_evidence(self) -> None:
        for tier in ("X1", "U0"):
            with self.subTest(tier=tier), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "pose.json"
                event, lock, started = build_open_event()
                write_pose_package(path, event, evidence_tier=tier)
                with self.assertRaisesRegex(ValueError, "prospective real V1 evidence"):
                    seal_sidecar(pose_reservation(event, lock, started), path)

    def test_pose_package_requires_uncertainty(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "pose.json"
            event, lock, started = build_open_event()
            write_pose_package(path, event, include_uncertainty=False)
            with self.assertRaisesRegex(ValueError, "uncertainty is required"):
                seal_sidecar(pose_reservation(event, lock, started), path)

    def test_pose_package_requires_versioned_learned_model_weights(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "pose.json"
            event, lock, started = build_open_event()
            write_pose_package(path, event, include_weights=False)
            with self.assertRaisesRegex(ValueError, "weights_sha256"):
                seal_sidecar(pose_reservation(event, lock, started), path)

    def test_pose_package_sample_must_stay_in_reserved_window(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "pose.json"
            event, lock, started = build_open_event()
            write_pose_package(path, event, sample_offset_ms=5_001)
            with self.assertRaisesRegex(ValueError, "5000"):
                seal_sidecar(pose_reservation(event, lock, started), path)

    def test_pose_package_sequence_mismatch_is_rejected_at_seal(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "pose.json"
            event, lock, started = build_open_event()
            write_pose_package(
                path,
                event,
                sequence_id="sequence-a",
                observation_sequence_id="sequence-b",
            )
            with self.assertRaisesRegex(ValueError, "does not match package sequence_id"):
                seal_sidecar(pose_reservation(event, lock, started), path)

    def test_pose_package_subject_mismatch_is_rejected_at_composition(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "pose.json"
            event, lock, started = build_open_event()
            write_pose_package(path, event, subject_id="other-cat")
            pose = seal_sidecar(pose_reservation(event, lock, started), path)
            finalized, finalized_lock = finalize_event(event, lock, terminated=True)
            with self.assertRaisesRegex(ValueError, "does not match CT1 subject"):
                compose_enriched_event(finalized, finalized_lock, [pose])

    def test_pose_package_event_mismatch_is_rejected_at_seal(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "pose.json"
            event, lock, started = build_open_event()
            write_pose_package(path, event, event_id="other-event")
            with self.assertRaisesRegex(ValueError, "does not match reserved sidecar event_id"):
                seal_sidecar(pose_reservation(event, lock, started), path)

    def test_unsealed_sidecar_is_rejected(self) -> None:
        event, lock, started = build_open_event()
        sidecar = build_reservation(
            event,
            lock,
            modality="audio_vocalisation",
            schema_ref="audio/A1-naturalistic-wav-v0",
            human_content="none",
            reserved_at=started + timedelta(seconds=1),
        )
        finalized, finalized_lock = finalize_event(event, lock, terminated=True)
        with self.assertRaisesRegex(ValueError, "not sealed"):
            compose_enriched_event(finalized, finalized_lock, [sidecar])

    def test_reservation_after_sensor_window_is_rejected(self) -> None:
        event, lock, started = build_open_event()
        with self.assertRaisesRegex(ValueError, "reserved prospectively"):
            build_reservation(
                event,
                lock,
                modality="audio_vocalisation",
                schema_ref="audio/A1-naturalistic-wav-v0",
                human_content="none",
                reserved_at=started + timedelta(seconds=6),
            )

    def test_evidence_interval_beyond_five_seconds_is_rejected(self) -> None:
        event, lock, started = build_open_event()
        with self.assertRaisesRegex(ValueError, "frozen 0-5000"):
            build_reservation(
                event,
                lock,
                modality="audio_vocalisation",
                schema_ref="audio/A1-naturalistic-wav-v0",
                human_content="none",
                start_offset_ms=0,
                end_offset_ms=5_001,
                reserved_at=started + timedelta(seconds=1),
            )

    def test_event_episode_and_predictor_mismatch_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            wav_path = Path(directory) / "cat.wav"
            write_wav(wav_path)
            event, lock, started = build_open_event()
            sealed = seal_sidecar(
                build_reservation(
                    event,
                    lock,
                    modality="audio_vocalisation",
                    schema_ref="audio/A1-naturalistic-wav-v0",
                    human_content="none",
                    reserved_at=started + timedelta(seconds=1),
                ),
                wav_path,
            )
            finalized, finalized_lock = finalize_event(event, lock, terminated=True)

            bad_event = copy.deepcopy(sealed)
            bad_event["event_id"] = "other-event"
            bad_event["reservation_sha256"] = __import__(
                "fusion.m1_sensor_sidecar", fromlist=["reservation_fingerprint"]
            ).reservation_fingerprint(bad_event)
            with self.assertRaisesRegex(ValueError, "event_id"):
                verify_sealed_sidecar(bad_event, finalized, finalized_lock)

            bad_episode = copy.deepcopy(sealed)
            bad_episode["episode_id"] = "other-episode"
            bad_episode["reservation_sha256"] = __import__(
                "fusion.m1_sensor_sidecar", fromlist=["reservation_fingerprint"]
            ).reservation_fingerprint(bad_episode)
            with self.assertRaisesRegex(ValueError, "episode_id"):
                verify_sealed_sidecar(bad_episode, finalized, finalized_lock)

            bad_fp = copy.deepcopy(sealed)
            bad_fp["base_predictor_fingerprint_sha256"] = "0" * 64
            bad_fp["reservation_sha256"] = __import__(
                "fusion.m1_sensor_sidecar", fromlist=["reservation_fingerprint"]
            ).reservation_fingerprint(bad_fp)
            with self.assertRaisesRegex(ValueError, "different CT1 predictor"):
                verify_sealed_sidecar(bad_fp, finalized, finalized_lock)

    def test_artifact_changed_after_seal_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            wav_path = Path(directory) / "cat.wav"
            write_wav(wav_path)
            event, lock, started = build_open_event()
            sealed = seal_sidecar(
                build_reservation(
                    event,
                    lock,
                    modality="audio_vocalisation",
                    schema_ref="audio/A1-naturalistic-wav-v0",
                    human_content="none",
                    reserved_at=started + timedelta(seconds=1),
                ),
                wav_path,
            )
            finalized, finalized_lock = finalize_event(event, lock, terminated=True)
            with wav_path.open("ab") as handle:
                handle.write(b"tamper")
            with self.assertRaisesRegex(ValueError, "hash changed"):
                compose_enriched_event(finalized, finalized_lock, [sealed])

    def test_audio_file_must_cover_reserved_interval(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            wav_path = Path(directory) / "short.wav"
            write_wav(wav_path, duration_seconds=1.0)
            event, lock, started = build_open_event()
            reservation = build_reservation(
                event,
                lock,
                modality="audio_vocalisation",
                schema_ref="audio/A1-naturalistic-wav-v0",
                human_content="none",
                reserved_at=started + timedelta(milliseconds=100),
            )
            with self.assertRaisesRegex(ValueError, "shorter than the reserved"):
                seal_sidecar(reservation, wav_path)

    def test_pose_sidecar_requires_json_not_arbitrary_video_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            artifact = Path(directory) / "pose.bin"
            artifact.write_bytes(b"not pose json")
            event, lock, started = build_open_event()
            reservation = pose_reservation(
                event,
                lock,
                started,
                reserved_at=started + timedelta(milliseconds=100),
            )
            with self.assertRaisesRegex(ValueError, "valid JSON"):
                seal_sidecar(reservation, artifact)


if __name__ == "__main__":
    unittest.main()
