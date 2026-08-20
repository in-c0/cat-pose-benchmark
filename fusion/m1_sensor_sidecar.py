from __future__ import annotations

import argparse
import copy
import hashlib
import json
import uuid
import wave
from datetime import datetime
from pathlib import Path
from typing import Any

from context.ct1_capture import validate_capture_event
from context.ct1_capture_cli import (
    action_log_fingerprint,
    default_lock_path,
    predictor_fingerprint,
)
from fusion.m1_cohort_manifest import SENSOR_EVIDENCE_CUTOFF_MS, build_manifest
from fusion.v1_pose_package import (
    POSE_PACKAGE_SCHEMA_REF,
    pose_package_metadata,
    validate_pose_package,
)
from programme.validate_intent_event import validate_instance

SIDECAR_VERSION = "M1.3-sensor-sidecar-v0"
ALLOWED_MODALITIES = {
    "audio_vocalisation": "wav_audio",
    "visual_pose": "pose_features_json",
}
HUMAN_CONTENT_CHOICES = {"none", "audio", "image", "both"}


def _canonical_json(payload: Any) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _sha256_payload(payload: Any) -> str:
    return hashlib.sha256(_canonical_json(payload)).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _parse_time(value: str) -> datetime:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("event/reservation timestamps must be timezone-aware")
    return dt


def _human_flags(value: str) -> tuple[bool, bool]:
    if value not in HUMAN_CONTENT_CHOICES:
        raise ValueError(f"human_content must be one of {sorted(HUMAN_CONTENT_CHOICES)}")
    return value in {"audio", "both"}, value in {"image", "both"}


def _reservation_projection(sidecar: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "sidecar_version",
        "event_id",
        "episode_id",
        "base_predictor_fingerprint_sha256",
        "modality",
        "artifact_kind",
        "observation_ref",
        "schema_ref",
        "record_id",
        "start_offset_ms",
        "end_offset_ms",
        "reserved_at",
        "reserved_at_offset_ms",
        "contains_human_audio",
        "contains_human_image",
    )
    return {key: sidecar[key] for key in keys}


def reservation_fingerprint(sidecar: dict[str, Any]) -> str:
    return _sha256_payload(_reservation_projection(sidecar))


def _verify_open_ct1(event: dict[str, Any], lock: dict[str, Any]) -> None:
    if lock.get("event_id") != event.get("event_id"):
        raise ValueError("CT1 lock event_id does not match event")
    if lock.get("finalized") is True:
        raise ValueError("sensor reservation must occur before CT1 finalization")
    if lock.get("predictor_fingerprint_sha256") != predictor_fingerprint(event):
        raise ValueError("CT1 t0 predictor fingerprint changed before sensor reservation")
    if lock.get("action_log_fingerprint_sha256") != action_log_fingerprint(event):
        raise ValueError("CT1 action-log fingerprint changed before sensor reservation")
    if lock.get("action_count") != len(event.get("human_actions", [])):
        raise ValueError("CT1 action count changed before sensor reservation")
    errors = validate_capture_event(event)
    if errors:
        raise ValueError("CT1 event is not prospective-valid: " + "; ".join(errors))


def _verify_finalized_ct1(event: dict[str, Any], lock: dict[str, Any]) -> None:
    if lock.get("event_id") != event.get("event_id"):
        raise ValueError("CT1 lock event_id does not match finalized event")
    if lock.get("finalized") is not True:
        raise ValueError("CT1 event must be finalized before sensor composition")
    if lock.get("predictor_fingerprint_sha256") != predictor_fingerprint(event):
        raise ValueError("finalized CT1 t0 predictor fingerprint does not match lock")
    if lock.get("action_log_fingerprint_sha256") != action_log_fingerprint(event):
        raise ValueError("finalized CT1 action-log fingerprint does not match lock")
    if lock.get("action_count") != len(event.get("human_actions", [])):
        raise ValueError("finalized CT1 action count does not match lock")
    completed_hash = _sha256_payload(event)
    if lock.get("completed_event_sha256") != completed_hash:
        raise ValueError("finalized CT1 completed-event hash does not match lock")
    errors = validate_capture_event(event)
    if errors:
        raise ValueError("finalized CT1 event is invalid: " + "; ".join(errors))


def build_reservation(
    event: dict[str, Any],
    lock: dict[str, Any],
    *,
    modality: str,
    schema_ref: str,
    human_content: str,
    start_offset_ms: int = 0,
    end_offset_ms: int = SENSOR_EVIDENCE_CUTOFF_MS,
    reserved_at: datetime | None = None,
    observation_ref: str | None = None,
    record_id: str | None = None,
) -> dict[str, Any]:
    _verify_open_ct1(event, lock)
    if modality not in ALLOWED_MODALITIES:
        raise ValueError(f"unsupported M1 sidecar modality: {modality}")
    if not schema_ref.strip():
        raise ValueError("schema_ref must not be empty")
    if modality == "visual_pose" and schema_ref != POSE_PACKAGE_SCHEMA_REF:
        raise ValueError(
            f"visual_pose sidecars must use schema_ref {POSE_PACKAGE_SCHEMA_REF}"
        )
    if not 0 <= start_offset_ms < end_offset_ms <= SENSOR_EVIDENCE_CUTOFF_MS:
        raise ValueError(
            f"sensor evidence must stay inside frozen 0-{SENSOR_EVIDENCE_CUTOFF_MS} ms window"
        )

    now = reserved_at or datetime.now().astimezone()
    if now.tzinfo is None:
        raise ValueError("reserved_at must be timezone-aware")
    event_start = _parse_time(event["time"]["start_time"])
    elapsed_ms = int(round((now - event_start).total_seconds() * 1000))
    if not 0 <= elapsed_ms <= end_offset_ms:
        raise ValueError(
            "sensor sidecar must be reserved prospectively during its declared evidence window"
        )

    contains_human_audio, contains_human_image = _human_flags(human_content)
    token = uuid.uuid4().hex[:10]
    observation_ref = observation_ref or f"sensor:{modality}:{event['event_id']}:{token}"
    record_id = record_id or f"sensor-record:{modality}:{event['event_id']}:{token}"

    sidecar: dict[str, Any] = {
        "sidecar_version": SIDECAR_VERSION,
        "state": "reserved",
        "event_id": event["event_id"],
        "episode_id": event["episode_id"],
        "base_predictor_fingerprint_sha256": lock["predictor_fingerprint_sha256"],
        "modality": modality,
        "artifact_kind": ALLOWED_MODALITIES[modality],
        "observation_ref": observation_ref,
        "schema_ref": schema_ref,
        "record_id": record_id,
        "start_offset_ms": start_offset_ms,
        "end_offset_ms": end_offset_ms,
        "reserved_at": now.isoformat(),
        "reserved_at_offset_ms": elapsed_ms,
        "contains_human_audio": contains_human_audio,
        "contains_human_image": contains_human_image,
    }
    sidecar["reservation_sha256"] = reservation_fingerprint(sidecar)
    return sidecar


def verify_reservation(sidecar: dict[str, Any]) -> None:
    if sidecar.get("sidecar_version") != SIDECAR_VERSION:
        raise ValueError("unsupported M1 sensor sidecar version")
    if sidecar.get("state") not in {"reserved", "sealed"}:
        raise ValueError("sidecar state must be reserved or sealed")
    if sidecar.get("modality") not in ALLOWED_MODALITIES:
        raise ValueError("sidecar modality is not supported")
    if sidecar.get("artifact_kind") != ALLOWED_MODALITIES[sidecar["modality"]]:
        raise ValueError("sidecar artifact_kind does not match modality")
    if (
        sidecar.get("modality") == "visual_pose"
        and sidecar.get("schema_ref") != POSE_PACKAGE_SCHEMA_REF
    ):
        raise ValueError(
            f"visual_pose sidecar schema_ref must be {POSE_PACKAGE_SCHEMA_REF}"
        )
    start = sidecar.get("start_offset_ms")
    end = sidecar.get("end_offset_ms")
    if not isinstance(start, int) or not isinstance(end, int):
        raise ValueError("sidecar evidence offsets must be integers")
    if not 0 <= start < end <= SENSOR_EVIDENCE_CUTOFF_MS:
        raise ValueError("sidecar evidence interval exceeds frozen M1 sensor window")
    if sidecar.get("reservation_sha256") != reservation_fingerprint(sidecar):
        raise ValueError("sensor sidecar reservation fingerprint changed")


def _inspect_wav(path: Path) -> dict[str, Any]:
    try:
        with wave.open(str(path), "rb") as handle:
            frames = int(handle.getnframes())
            sample_rate = int(handle.getframerate())
            channels = int(handle.getnchannels())
            sample_width = int(handle.getsampwidth())
    except (wave.Error, EOFError) as exc:
        raise ValueError(f"A1 sidecar file is not a readable WAV: {exc}") from exc
    if sample_rate <= 0:
        raise ValueError("WAV sample rate must be positive")
    duration_s = frames / sample_rate
    return {
        "container": "wav",
        "duration_seconds": duration_s,
        "sample_rate_hz": sample_rate,
        "channels": channels,
        "sample_width_bytes": sample_width,
        "frames": frames,
    }


def _inspect_pose_json(path: Path, sidecar: dict[str, Any]) -> dict[str, Any]:
    try:
        payload = _load_json(path)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError(f"V1 pose package must be valid JSON: {exc}") from exc
    errors = validate_pose_package(payload, sidecar=sidecar)
    if errors:
        raise ValueError("V1 pose package is invalid: " + "; ".join(errors))
    return pose_package_metadata(payload)


def seal_sidecar(sidecar: dict[str, Any], artifact_path: Path) -> dict[str, Any]:
    verify_reservation(sidecar)
    if sidecar.get("state") != "reserved":
        raise ValueError("sidecar has already been sealed")
    if not artifact_path.is_file():
        raise FileNotFoundError(f"sensor artifact does not exist: {artifact_path}")

    if sidecar["modality"] == "audio_vocalisation":
        media_metadata = _inspect_wav(artifact_path)
        reserved_duration_s = (
            sidecar["end_offset_ms"] - sidecar["start_offset_ms"]
        ) / 1000.0
        if media_metadata["duration_seconds"] + 1e-9 < reserved_duration_s:
            raise ValueError(
                "WAV duration is shorter than the reserved evidence interval"
            )
    else:
        media_metadata = _inspect_pose_json(artifact_path, sidecar)

    sealed = copy.deepcopy(sidecar)
    sealed["state"] = "sealed"
    sealed["seal"] = {
        "local_file_path": str(artifact_path.resolve()),
        "file_sha256": _sha256_file(artifact_path),
        "byte_length": artifact_path.stat().st_size,
        "media_metadata": media_metadata,
    }
    sealed["sealed_record_sha256"] = _sha256_payload(
        {
            "reservation_sha256": sealed["reservation_sha256"],
            "file_sha256": sealed["seal"]["file_sha256"],
            "byte_length": sealed["seal"]["byte_length"],
            "media_metadata": sealed["seal"]["media_metadata"],
        }
    )
    return sealed


def verify_sealed_sidecar(sidecar: dict[str, Any], event: dict[str, Any], lock: dict[str, Any]) -> None:
    verify_reservation(sidecar)
    if sidecar.get("state") != "sealed":
        raise ValueError("sensor sidecar is not sealed")
    if sidecar.get("event_id") != event.get("event_id"):
        raise ValueError("sensor sidecar event_id does not match CT1 event")
    if sidecar.get("episode_id") != event.get("episode_id"):
        raise ValueError("sensor sidecar episode_id does not match CT1 event")
    if sidecar.get("base_predictor_fingerprint_sha256") != lock.get(
        "predictor_fingerprint_sha256"
    ):
        raise ValueError("sensor sidecar was reserved against a different CT1 predictor fingerprint")

    seal = sidecar.get("seal")
    if not isinstance(seal, dict):
        raise ValueError("sealed sidecar is missing seal metadata")
    path_value = seal.get("local_file_path")
    if not isinstance(path_value, str) or not path_value:
        raise ValueError("sealed sidecar is missing its local file path")
    path = Path(path_value)
    if not path.is_file():
        raise FileNotFoundError(f"sealed sensor artifact is no longer available: {path}")
    if _sha256_file(path) != seal.get("file_sha256"):
        raise ValueError("sealed sensor artifact hash changed after sealing")
    if path.stat().st_size != seal.get("byte_length"):
        raise ValueError("sealed sensor artifact byte length changed after sealing")

    if sidecar["modality"] == "visual_pose":
        try:
            payload = _load_json(path)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ValueError(f"sealed V1 pose package is no longer readable JSON: {exc}") from exc
        pose_errors = validate_pose_package(payload, sidecar=sidecar, event=event)
        if pose_errors:
            raise ValueError(
                "sealed V1 pose package does not match CT1 event: " + "; ".join(pose_errors)
            )
        if seal.get("media_metadata") != pose_package_metadata(payload):
            raise ValueError("sealed V1 pose package metadata no longer matches artifact")

    expected_sealed_record_hash = _sha256_payload(
        {
            "reservation_sha256": sidecar["reservation_sha256"],
            "file_sha256": seal["file_sha256"],
            "byte_length": seal["byte_length"],
            "media_metadata": seal["media_metadata"],
        }
    )
    if sidecar.get("sealed_record_sha256") != expected_sealed_record_hash:
        raise ValueError("sealed sensor sidecar metadata fingerprint changed")


def _public_observation(sidecar: dict[str, Any]) -> dict[str, Any]:
    seal = sidecar["seal"]
    return {
        "observation_ref": sidecar["observation_ref"],
        "modality": sidecar["modality"],
        "schema_ref": sidecar["schema_ref"],
        "record_ids": [
            sidecar["record_id"],
            f"sha256:{seal['file_sha256']}",
        ],
        "start_offset_ms": sidecar["start_offset_ms"],
        "end_offset_ms": sidecar["end_offset_ms"],
        "features": {
            "sensor_sidecar_version": SIDECAR_VERSION,
            "artifact_kind": sidecar["artifact_kind"],
            "artifact_sha256": seal["file_sha256"],
            "artifact_byte_length": seal["byte_length"],
            "media_metadata": copy.deepcopy(seal["media_metadata"]),
            "reservation_sha256": sidecar["reservation_sha256"],
            "sealed_record_sha256": sidecar["sealed_record_sha256"],
            "reserved_at": sidecar["reserved_at"],
            "reserved_at_offset_ms": sidecar["reserved_at_offset_ms"],
            "local_path_included": False,
        },
    }


def compose_enriched_event(
    event: dict[str, Any],
    lock: dict[str, Any],
    sidecars: list[dict[str, Any]],
) -> dict[str, Any]:
    _verify_finalized_ct1(event, lock)
    if not sidecars:
        raise ValueError("at least one sealed sensor sidecar is required")

    original_hash = _sha256_payload(event)
    for sidecar in sidecars:
        verify_sealed_sidecar(sidecar, event, lock)

    observation_refs = [sidecar["observation_ref"] for sidecar in sidecars]
    if len(observation_refs) != len(set(observation_refs)):
        raise ValueError("sensor sidecars contain duplicate observation_ref values")
    existing_refs = {obs["observation_ref"] for obs in event.get("observations", [])}
    collisions = sorted(existing_refs & set(observation_refs))
    if collisions:
        raise ValueError(f"sensor observation_ref collides with CT1 event: {collisions}")

    enriched = copy.deepcopy(event)
    added_modalities: set[str] = set()
    source_ids: list[str] = []
    contains_human_audio = bool(enriched["privacy"].get("contains_human_audio", False))
    contains_human_image = bool(enriched["privacy"].get("contains_human_image", False))

    for sidecar in sidecars:
        enriched["observations"].append(_public_observation(sidecar))
        added_modalities.add(sidecar["modality"])
        source_ids.append(sidecar["record_id"])
        contains_human_audio = contains_human_audio or bool(sidecar["contains_human_audio"])
        contains_human_image = contains_human_image or bool(sidecar["contains_human_image"])

    enriched["missing_modalities"] = [
        modality
        for modality in enriched["missing_modalities"]
        if modality not in added_modalities
    ]
    provenance = enriched["provenance"]
    provenance["source_ids"] = list(dict.fromkeys(provenance["source_ids"] + source_ids))
    provenance["lineage"] = provenance["lineage"] + [
        f"M1.3 derived sensor composition from immutable CT1 event using {len(sidecars)} sealed sidecar(s)"
    ]
    provenance["annotation_source"] = "mixed"
    software_versions = provenance.setdefault("software_versions", {})
    software_versions["m1_sensor_sidecar"] = SIDECAR_VERSION

    enriched["privacy"]["contains_human_audio"] = contains_human_audio
    enriched["privacy"]["contains_human_image"] = contains_human_image
    enriched["notes"] = (
        (enriched.get("notes") or "")
        + " Derived M1 event adds sealed local sensor evidence; raw/local paths are not embedded."
    ).strip()

    intent_errors = validate_instance(enriched)
    capture_errors = validate_capture_event(enriched)
    errors = intent_errors + capture_errors
    if errors:
        raise ValueError("composed M1 event is invalid: " + "; ".join(errors))

    if _sha256_payload(event) != original_hash:
        raise AssertionError("sensor composition mutated the original CT1 event")
    rendered = json.dumps(enriched, sort_keys=True)
    for sidecar in sidecars:
        local_path = sidecar["seal"]["local_file_path"]
        if local_path in rendered:
            raise AssertionError("local sensor path leaked into composed M1 event")
    return enriched


def _sidecar_readiness(event: dict[str, Any]) -> dict[str, Any]:
    manifest = build_manifest([event])
    row = manifest["events"][0]
    return {
        "M1_manifest_version": manifest["manifest_version"],
        "primary_cohort_eligible": row["primary_cohort_eligible"],
        "support": row["support"],
        "eligible_observation_refs": row["eligible_observation_refs"],
        "exclusion_reasons": row["exclusion_reasons"],
    }


def reserve_command(args: argparse.Namespace) -> None:
    event = _load_json(args.event)
    lock_path = args.lock or default_lock_path(args.event)
    lock = _load_json(lock_path)
    if not isinstance(event, dict) or not isinstance(lock, dict):
        raise ValueError("event and lock files must contain JSON objects")
    if args.output.exists():
        raise FileExistsError("refusing to overwrite an existing sensor sidecar")
    sidecar = build_reservation(
        event,
        lock,
        modality=args.modality,
        schema_ref=args.schema_ref,
        human_content=args.human_content,
        start_offset_ms=args.start_offset_ms,
        end_offset_ms=args.end_offset_ms,
    )
    _write_json(args.output, sidecar)
    print(f"reserved {args.modality} sidecar {sidecar['observation_ref']}")
    print(f"sidecar: {args.output}")


def seal_command(args: argparse.Namespace) -> None:
    sidecar = _load_json(args.sidecar)
    if not isinstance(sidecar, dict):
        raise ValueError("sidecar file must contain one JSON object")
    sealed = seal_sidecar(sidecar, args.artifact)
    _write_json(args.sidecar, sealed)
    print(f"sealed sensor sidecar with sha256:{sealed['seal']['file_sha256']}")


def compose_command(args: argparse.Namespace) -> None:
    if args.output.exists():
        raise FileExistsError("refusing to overwrite an existing composed M1 event")
    event = _load_json(args.event)
    lock_path = args.lock or default_lock_path(args.event)
    lock = _load_json(lock_path)
    sidecars = [_load_json(path) for path in args.sidecar]
    if not isinstance(event, dict) or not isinstance(lock, dict):
        raise ValueError("event and lock files must contain JSON objects")
    if not all(isinstance(sidecar, dict) for sidecar in sidecars):
        raise ValueError("each sidecar file must contain one JSON object")
    enriched = compose_enriched_event(event, lock, sidecars)
    _write_json(args.output, enriched)
    readiness = _sidecar_readiness(enriched)
    print(json.dumps(readiness, indent=2, sort_keys=True))
    if args.readiness:
        _write_json(args.readiness, readiness)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Reserve, seal and compose local A1/V1 sensor sidecars without mutating CT1"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    reserve = sub.add_parser("reserve", help="prospectively reserve a 0-5 s sensor evidence sidecar")
    reserve.add_argument("--event", type=Path, required=True)
    reserve.add_argument("--lock", type=Path)
    reserve.add_argument("--output", type=Path, required=True)
    reserve.add_argument("--modality", choices=tuple(sorted(ALLOWED_MODALITIES)), required=True)
    reserve.add_argument("--schema-ref", required=True)
    reserve.add_argument("--human-content", choices=tuple(sorted(HUMAN_CONTENT_CHOICES)), required=True)
    reserve.add_argument("--start-offset-ms", type=int, default=0)
    reserve.add_argument("--end-offset-ms", type=int, default=SENSOR_EVIDENCE_CUTOFF_MS)
    reserve.set_defaults(func=reserve_command)

    seal = sub.add_parser("seal", help="hash and inspect a local artifact into its reserved sidecar")
    seal.add_argument("--sidecar", type=Path, required=True)
    seal.add_argument("--artifact", type=Path, required=True)
    seal.set_defaults(func=seal_command)

    compose = sub.add_parser("compose", help="derive a new M1 event from finalized CT1 + sealed sidecars")
    compose.add_argument("--event", type=Path, required=True)
    compose.add_argument("--lock", type=Path)
    compose.add_argument("--sidecar", type=Path, action="append", required=True)
    compose.add_argument("--output", type=Path, required=True)
    compose.add_argument("--readiness", type=Path)
    compose.set_defaults(func=compose_command)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
