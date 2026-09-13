from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
CLIPS_PATH = REPO_ROOT / "review" / "clips.json"
WORK_ROOT = REPO_ROOT / "review" / "work"

# Reviewer vocabulary. Anything outside these sets is rejected by the scorer.
PARTS = ["head", "spine", "front_paws", "hind_paws", "tail_curve", "tail_curve_anchored"]
METHOD_FOR_PART = {
    "head": "body",
    "spine": "body",
    "front_paws": "body",
    "hind_paws": "body",
    "tail_curve": "tail",
    "tail_curve_anchored": "tail_anchored",
}
VERDICTS = ["ok", "wrong", "not_visible"]
CONDITIONS = ["none", "blur", "occlusion", "out_of_frame", "dark", "small", "multi_cat"]

# Body keypoints below this score are drawn hollow and are not to be judged.
BODY_SCORE_THRESHOLD = 0.3


def load_clips(path: Path = CLIPS_PATH) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return list(payload["clips"])


def clip_workdir(clip_id: str) -> Path:
    return WORK_ROOT / clip_id


def frames_dir(clip_id: str) -> Path:
    return clip_workdir(clip_id) / "frames"


def frames_manifest_path(clip_id: str) -> Path:
    return clip_workdir(clip_id) / "frames.json"


def load_frames_manifest(clip_id: str) -> dict[str, Any]:
    return json.loads(frames_manifest_path(clip_id).read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
