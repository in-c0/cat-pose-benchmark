"""Check that the public tree does not let a labeller learn which Commons clip a segment came from.

The same machinery as review/hr1/withholding.py, for BH1's one blind stage (PROTOCOL.md section 6):

- public from the start: the template, ``media.json``, ``commitment.json`` (counts and one root
  digest, nothing per clip), the roster ``submissions/labellers.json`` and ``submissions/locks.json``;
- private until every registered labeller (at least two) has a lock in ``locks.json``: the key
  (``behaviour/key.json``), the manifest with its salt, the identity pass, any ``SECRET`` file,
  baseline predictions and results.

When the private build exists (``behaviour/work/``), the check also scans every tracked text file
for the salt and for any opaque clip id written next to its Commons title.

    python -m behaviour.withholding                    # check the tracked tree (the tests run this)
    python -m behaviour.withholding --verify-release   # after release: published key and manifest match the commitment
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Any, Callable

from behaviour.build import KEY_PATH, MANIFEST_PATH, SALT_PATH, manifest_root
from behaviour.common import REPO_ROOT, sha256_file

BH1 = "behaviour/"
COMMITMENT = BH1 + "package/commitment.json"
LOCKS = BH1 + "submissions/locks.json"
ROSTER = BH1 + "submissions/labellers.json"
COMMITMENT_KEYS = {"note", "scheme", "n_clips", "n_segments", "root_sha256"}
TEXT_SUFFIXES = {".md", ".csv", ".json", ".py", ".txt", ".yml", ".yaml", ".toml", ".cfg", ".tex", ".html"}


def _is_after_lock(path: str) -> bool:
    if not path.startswith(BH1):
        return False
    name = path.rsplit("/", 1)[-1]
    return (
        path in (BH1 + "key.json", BH1 + "manifest.json", BH1 + "identity.csv")
        or path.startswith(BH1 + "predictions/")
        or path.startswith(BH1 + "results.")
        or "SECRET" in name.upper()
    )


def lockers(locks: dict[str, str]) -> set[str]:
    """Labeller handles with a lock; a ``-r2`` resubmission is the same labeller."""
    out = set()
    for name in locks:
        m = re.fullmatch(r"labels/labels-(.+?)(?:-r\d+)?\.csv", name)
        if m:
            out.add(m.group(1).lower())
    return out


def phase(roster: list[str], locks: dict[str, str]) -> str:
    """``locked`` once at least two labellers are registered and every one of them has locked."""
    r = {h.lower() for h in roster}
    if len(r) >= 2 and r <= lockers(locks):
        return "locked"
    return "collecting"


def check(files: list[str], read: Callable[[str], bytes], private: dict[str, Any] | None = None) -> list[str]:
    errors: list[str] = []
    locks = json.loads(read(LOCKS)) if LOCKS in files else {}
    roster = json.loads(read(ROSTER)).get("labellers", []) if ROSTER in files else []
    ph = phase(roster, locks)
    unregistered = lockers(locks) - {h.lower() for h in roster}
    if unregistered:
        errors.append(f"{LOCKS}: locks from labellers not in the roster: {sorted(unregistered)}")
    for path in files:
        if path.startswith(BH1 + "work/"):
            errors.append(f"{path}: the private working set is tracked")
        if _is_after_lock(path) and ph != "locked":
            errors.append(f"{path}: published before every registered labeller has locked (phase {ph})")
    if COMMITMENT in files:
        extra = set(json.loads(read(COMMITMENT))) - COMMITMENT_KEYS
        if extra:
            errors.append(f"{COMMITMENT}: fields beyond counts and the root digest: {sorted(extra)}")
    if private and ph != "locked":
        for path in files:
            if Path(path).suffix.lower() not in TEXT_SUFFIXES:
                continue
            text = read(path).decode("utf-8", errors="ignore")
            if private["salt"] in text:
                errors.append(f"{path}: contains the clip-order salt")
                continue
            for clip, title in private["titles"].items():
                if clip in text and title in text:
                    errors.append(f"{path}: names {clip} together with its Commons title")
                    break
    return errors


def private_values(key_path: Path = KEY_PATH, salt_path: Path = SALT_PATH) -> dict[str, Any] | None:
    if not (key_path.exists() and salt_path.exists()):
        return None
    key = json.loads(key_path.read_text(encoding="utf-8"))
    return {"salt": salt_path.read_text(encoding="utf-8").strip(),
            "titles": {c: v["title"].removeprefix("File:") for c, v in key["clips"].items()}}


def tracked_files(root: Path = REPO_ROOT) -> list[str]:
    out = subprocess.run(["git", "ls-files", "-z"], cwd=root, capture_output=True, check=True).stdout
    return [p for p in out.decode("utf-8").split("\0") if p]


def check_repo(root: Path = REPO_ROOT, scan_private: bool = True) -> list[str]:
    return check(tracked_files(root), lambda p: (root / p).read_bytes(), private_values() if scan_private else None)


def verify_release(manifest: dict[str, Any], commitment: dict[str, Any], key_path: Path, template_path: Path) -> list[str]:
    errors = []
    if manifest_root(manifest) != commitment["root_sha256"]:
        errors.append("manifest does not hash to the committed root_sha256")
    if sha256_file(key_path) != manifest["key_sha256"]:
        errors.append("key.json differs from the manifest")
    if sha256_file(template_path) != manifest["template_sha256"]:
        errors.append("label-TEMPLATE.csv differs from the manifest")
    return errors


def main() -> None:
    p = argparse.ArgumentParser(description="Check BH1 withholding.")
    p.add_argument("--verify-release", action="store_true")
    a = p.parse_args()
    if a.verify_release:
        bh1 = REPO_ROOT / "behaviour"
        errors = verify_release(json.loads((bh1 / "manifest.json").read_text(encoding="utf-8")),
                                json.loads((REPO_ROOT / COMMITMENT).read_text(encoding="utf-8")),
                                bh1 / "key.json", bh1 / "package" / "label-TEMPLATE.csv")
    else:
        errors = check_repo()
    for e in errors:
        print(e)
    if errors:
        raise SystemExit(1)
    print("ok" + ("" if a.verify_release else f" (private scan {'on' if private_values() else 'off'})"))


if __name__ == "__main__":
    main()
