from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

ALLOWED_GROUP_KEYS = {"cat_id", "owner_id", "sequence_group"}


def read_manifest(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError("manifest is empty")
    if "path" not in rows[0]:
        raise ValueError("manifest is missing path column")
    return rows


def leave_one_group_out(rows: list[dict[str, str]], group_key: str) -> list[dict]:
    if group_key not in ALLOWED_GROUP_KEYS:
        raise ValueError(f"unsupported group key: {group_key}")
    if group_key not in rows[0]:
        raise ValueError(f"manifest is missing {group_key} column")

    groups = sorted({row[group_key] for row in rows})
    folds: list[dict] = []
    for index, held_out in enumerate(groups):
        train = [row["path"] for row in rows if row[group_key] != held_out]
        test = [row["path"] for row in rows if row[group_key] == held_out]
        if not train or not test:
            raise ValueError(f"invalid fold for held-out group {held_out}")
        if set(train) & set(test):
            raise ValueError(f"path leakage in fold {held_out}")
        folds.append(
            {
                "fold_id": f"{group_key}-{index:03d}",
                "group_key": group_key,
                "held_out_group": held_out,
                "train_count": len(train),
                "test_count": len(test),
                "train_paths": train,
                "test_paths": test,
            }
        )
    return folds


def validate_folds(rows: list[dict[str, str]], folds: list[dict], group_key: str) -> list[str]:
    errors: list[str] = []
    by_path = {row["path"]: row for row in rows}
    expected_paths = set(by_path)

    for fold in folds:
        train = set(fold["train_paths"])
        test = set(fold["test_paths"])
        held_out = fold["held_out_group"]

        if train & test:
            errors.append(f"{fold['fold_id']}: train/test path overlap")
        if train | test != expected_paths:
            errors.append(f"{fold['fold_id']}: fold does not cover manifest exactly")

        leaked_test = {by_path[path][group_key] for path in test if by_path[path][group_key] != held_out}
        if leaked_test:
            errors.append(f"{fold['fold_id']}: test contains non-held-out groups {sorted(leaked_test)}")

        leaked_train = {path for path in train if by_path[path][group_key] == held_out}
        if leaked_train:
            errors.append(f"{fold['fold_id']}: held-out group appears in training")

    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate leave-one-group-out CatMeows folds")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--group-key", choices=sorted(ALLOWED_GROUP_KEYS), default="cat_id")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    rows = read_manifest(args.manifest)
    folds = leave_one_group_out(rows, args.group_key)
    errors = validate_folds(rows, folds, args.group_key)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        raise SystemExit(1)

    payload = {
        "protocol": "leave-one-group-out-v0.1",
        "group_key": args.group_key,
        "manifest": str(args.manifest),
        "fold_count": len(folds),
        "folds": folds,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(folds)} folds to {args.output}")


if __name__ == "__main__":
    main()
