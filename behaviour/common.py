"""BH1 constants shared by the builder, the baselines and the scorer.

Every value here is fixed by behaviour/PROTOCOL.md. Changing one after the protocol freeze is an
amendment (PROTOCOL.md, "Amendments"), not an edit.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
WORK = HERE / "work"  # git-ignored: media, frames, salt, private key and manifest
PACKAGE = HERE / "package"
SUBMISSIONS = HERE / "submissions"

# PROTOCOL.md section 2. Order is the column order of every confusion matrix.
CLASSES = ("walk", "sit_lie", "groom", "jump", "play_other")
CANNOT_TELL = "cannot_tell"
LABELS = CLASSES + (CANNOT_TELL,)

# PROTOCOL.md section 3: the labelling unit.
SEGMENT_S = 2.0
MAX_SECONDS = 20.0
SAMPLE_FPS = 4
FRAMES_PER_SEGMENT = int(SEGMENT_S * SAMPLE_FPS)

# PROTOCOL.md section 7: analysis constants.
RELIABLE, TENTATIVE = 0.80, 0.667
BOOT_SEED, BOOT_REPS = 20261017, 10000
ABSTAIN_BELOW = 0.5
MIN_CATS, MIN_CLIPS, MIN_LABELLERS = 10, 100, 2
DROP_MATERIAL = 0.10
MIN_COVERAGE = 0.5

TEMPLATE_COLUMNS = ["segment_id", "clip_id", "segment", "t_start_s", "t_end_s", "sheet", "behaviour", "note"]


def n_segments(duration_s: float | None) -> int:
    """Whole 2 s segments in the first 20 s of a clip. A trailing part segment is dropped."""
    if not duration_s or duration_s <= 0:
        return 0
    return int(math.floor(min(duration_s, MAX_SECONDS) / SEGMENT_S + 1e-9))


def segment_id(clip_id: str, k: int) -> str:
    return f"{clip_id}-S{k:02d}"


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def write_csv(path: Path, columns: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as h:
        w = csv.DictWriter(h, fieldnames=columns)
        w.writeheader()
        w.writerows(rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as h:
        return list(csv.DictReader(h))
