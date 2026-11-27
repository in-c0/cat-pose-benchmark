"""Check that nothing in the public tree lets a reviewer recover the Stage B key early.

What must stay private, and until when (review/hr1/README.md, "Withholding"):

- until at least two reviewers have locked Stage A: the Stage B images and template
  (``review/hr1/package/stage_b/``);
- until every reviewer who locked Stage A has also locked Stage B: the key
  (``review/hr1/key.json``), the per-method outputs (``review/hr1/outputs/``), the manifest of
  digests with its shuffle salt (``stage_b_manifest.json``), any ``SECRET`` file, and results.

"Locked" means a digest in ``review/hr1/submissions/locks.json``. The committed
``stage_b_commitment.json`` may hold counts and one root digest, nothing per item.

When the private build exists locally (``review/work/hr1``), the check also scans every tracked
text file for the salt and for every curve key in the private key, so a value pasted into a note
or a CSV is caught too.

    python -m review.hr1.withholding                   # check the tracked tree (CI runs this via the tests)
    python -m review.hr1.withholding --verify-release  # after release: published files match the commitment
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import subprocess
from pathlib import Path
from typing import Any, Callable

from review.common import REPO_ROOT

STAGE_B_WORK = REPO_ROOT / "review" / "work" / "hr1" / "stage_b"
SALT_PATH = STAGE_B_WORK.parent / "SECRET-salt.txt"
MANIFEST_PATH = STAGE_B_WORK.parent / "stage_b_manifest.json"

HR1 = "review/hr1/"
COMMITMENT = HR1 + "package/stage_b_commitment.json"
LOCKS = HR1 + "submissions/locks.json"
STAGE_B_PUBLIC = HR1 + "package/stage_b/"
COMMITMENT_KEYS = {"note", "scheme", "n_items", "n_repeats", "root_sha256"}
TEXT_SUFFIXES = {".md", ".csv", ".json", ".py", ".txt", ".yml", ".yaml", ".toml", ".cfg", ".tex", ".html"}


def shuffle_rng(salt: str) -> random.Random:
    """Stage B item order. Seeded from the private salt, so the public code alone cannot rebuild the key."""
    return random.Random(int.from_bytes(hashlib.sha256(b"hr1-stage-b|" + salt.encode()).digest(), "big"))


def manifest_root(manifest: dict[str, Any]) -> str:
    """SHA-256 of the canonical manifest JSON: the only Stage B value committed before release."""
    return hashlib.sha256(json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _is_after_stage_b(path: str) -> bool:
    name = path.rsplit("/", 1)[-1]
    return (
        path == HR1 + "key.json"
        or path.startswith(HR1 + "outputs/")
        or path.startswith(HR1 + "results.")
        or name == "stage_b_manifest.json"
        or "SECRET" in name.upper()
    )


def lockers(locks: dict[str, str], stage: str) -> set[str]:
    """Reviewer handles with a lock for ``stage`` ('a' or 'b'); a ``-r2`` resubmission is the same reviewer."""
    out = set()
    for name in locks:
        m = re.fullmatch(rf"stage_{stage}/stage-{stage}-(.+?)(?:-r\d+)?\.csv", name)
        if m:
            out.add(m.group(1).lower())
    return out


def phase(locks: dict[str, str]) -> str:
    a, b = lockers(locks, "a"), lockers(locks, "b")
    if len(a) >= 2 and a <= b:
        return "stage_b_locked"
    if len(a) >= 2:
        return "stage_a_locked"
    return "collecting_stage_a"


def check(files: list[str], read: Callable[[str], bytes], private: dict[str, Any] | None = None) -> list[str]:
    """Return a list of problems; empty means the tree withholds what it should for its phase."""
    errors: list[str] = []
    locks = json.loads(read(LOCKS)) if LOCKS in files else {}
    ph = phase(locks)
    for path in files:
        if path.startswith("review/work/"):
            errors.append(f"{path}: the private working set is tracked")
        if path.startswith(STAGE_B_PUBLIC) and ph == "collecting_stage_a":
            errors.append(f"{path}: Stage B material is public before two reviewers have locked Stage A")
        if _is_after_stage_b(path) and ph != "stage_b_locked":
            errors.append(f"{path}: published before every reviewer has locked Stage B (phase {ph})")
    if COMMITMENT in files:
        extra = set(json.loads(read(COMMITMENT))) - COMMITMENT_KEYS
        if extra:
            errors.append(f"{COMMITMENT}: fields beyond counts and the root digest: {sorted(extra)}")
    else:
        errors.append(f"{COMMITMENT}: missing")
    if private and ph != "stage_b_locked":
        needles = {private["salt"]: "the shuffle salt"}
        needles.update({ck: f"curve key of {item}" for item, ck in private["curve_keys"].items()})
        for path in files:
            if Path(path).suffix.lower() not in TEXT_SUFFIXES:
                continue
            text = read(path).decode("utf-8", errors="ignore")
            for needle, what in needles.items():
                if needle in text:
                    errors.append(f"{path}: contains {what}")
                    break
    return errors


def private_values(work: Path = STAGE_B_WORK) -> dict[str, Any] | None:
    key_path, salt_path = work / "key.json", work.parent / SALT_PATH.name
    if not (key_path.exists() and salt_path.exists()):
        return None
    key = json.loads(key_path.read_text(encoding="utf-8"))
    return {"salt": salt_path.read_text(encoding="utf-8").strip(),
            "curve_keys": {i: v["curve_key"] for i, v in key["items"].items() if v.get("curve_key")}}


def tracked_files(root: Path = REPO_ROOT) -> list[str]:
    out = subprocess.run(["git", "ls-files", "-z"], cwd=root, capture_output=True, check=True).stdout
    return [p for p in out.decode("utf-8").split("\0") if p]


def check_repo(root: Path = REPO_ROOT, scan_private: bool = True) -> list[str]:
    files = tracked_files(root)
    return check(files, lambda p: (root / p).read_bytes(), private_values() if scan_private else None)


def verify_release(manifest: dict[str, Any], commitment: dict[str, Any], files: dict[str, Path]) -> list[str]:
    """After release: the published manifest hashes to the committed root, and each published file matches it.

    ``files`` maps a manifest entry ('key', 'template', 'images/B001.jpg', 'outputs/<name>.json') to a path.
    """
    errors = []
    if manifest_root(manifest) != commitment["root_sha256"]:
        errors.append("manifest does not hash to the committed root_sha256")
    expected = {"key": manifest["key_sha256"], "template": manifest["template_sha256"]}
    expected.update({f"images/{k}": v for k, v in manifest["images"].items()})
    expected.update({f"outputs/{k}": v for k, v in manifest["outputs"].items()})
    for name, digest in expected.items():
        path = files.get(name)
        if path is None:
            errors.append(f"{name}: not published")
        elif hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            errors.append(f"{name}: digest differs from the manifest")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description="Check HR1 Stage B withholding.")
    parser.add_argument("--verify-release", action="store_true",
                        help="check the published manifest, key, outputs and images against the committed root")
    args = parser.parse_args()
    if args.verify_release:
        hr1 = REPO_ROOT / "review" / "hr1"
        manifest = json.loads((hr1 / "stage_b_manifest.json").read_text(encoding="utf-8"))
        commitment = json.loads((REPO_ROOT / COMMITMENT).read_text(encoding="utf-8"))
        files = {"key": hr1 / "key.json", "template": hr1 / "package" / "stage_b" / "stage-b-TEMPLATE.csv"}
        files.update({f"images/{p.name}": p for p in (hr1 / "package" / "stage_b" / "items").glob("*.jpg")})
        files.update({f"outputs/{p.name}": p for p in (hr1 / "outputs").glob("*.json")})
        errors = verify_release(manifest, commitment, files)
    else:
        errors = check_repo()
    for e in errors:
        print(e)
    if errors:
        raise SystemExit(1)
    print("ok" + ("" if args.verify_release else f" (phase {phase(_locks())}, private scan {'on' if private_values() else 'off'})"))


def _locks() -> dict[str, str]:
    p = REPO_ROOT / LOCKS
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


if __name__ == "__main__":
    main()
