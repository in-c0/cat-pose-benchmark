from __future__ import annotations

import argparse
import csv
import re
from dataclasses import asdict, dataclass
from pathlib import Path

PATTERN = re.compile(
    r"^(?P<context>[BFI])_(?P<cat_id>[^_]+)_(?P<breed>MC|EU)_(?P<sex>FI|FN|MI|MN)_"
    r"(?P<owner_id>[^_]+)_(?P<session>[123])(?P<vocalisation_index>\d{2})$"
)

CONTEXTS = {
    "B": "brushing",
    "F": "waiting_for_food",
    "I": "isolation_unfamiliar_environment",
}

SEX = {
    "FI": "female_intact",
    "FN": "female_neutered",
    "MI": "male_intact",
    "MN": "male_neutered",
}

BREEDS = {
    "MC": "maine_coon",
    "EU": "european_shorthair",
}


@dataclass(frozen=True)
class CatMeowsRecord:
    path: str
    filename: str
    context_code: str
    context: str
    cat_id: str
    breed_code: str
    breed: str
    sex_code: str
    sex: str
    owner_id: str
    session: int
    vocalisation_index: int
    sequence_group: str


def parse_filename(path: Path, root: Path | None = None) -> CatMeowsRecord:
    if path.suffix.lower() != ".wav":
        raise ValueError(f"expected .wav file: {path}")

    match = PATTERN.fullmatch(path.stem)
    if not match:
        raise ValueError(f"filename does not match CatMeows convention: {path.name}")

    fields = match.groupdict()
    relative = path.relative_to(root) if root is not None else path
    session = int(fields["session"])

    return CatMeowsRecord(
        path=relative.as_posix(),
        filename=path.name,
        context_code=fields["context"],
        context=CONTEXTS[fields["context"]],
        cat_id=fields["cat_id"],
        breed_code=fields["breed"],
        breed=BREEDS[fields["breed"]],
        sex_code=fields["sex"],
        sex=SEX[fields["sex"]],
        owner_id=fields["owner_id"],
        session=session,
        vocalisation_index=int(fields["vocalisation_index"]),
        sequence_group=f"{fields['cat_id']}:{session}",
    )


def build_manifest(root: Path) -> list[CatMeowsRecord]:
    wav_files = sorted(path for path in root.rglob("*.wav") if path.is_file())
    if not wav_files:
        raise ValueError(f"no .wav files found under {root}")

    records = [parse_filename(path, root) for path in wav_files]
    seen_paths: set[str] = set()
    for record in records:
        if record.path in seen_paths:
            raise ValueError(f"duplicate manifest path: {record.path}")
        seen_paths.add(record.path)
    return records


def write_csv(records: list[CatMeowsRecord], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(asdict(records[0]).keys())
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(asdict(record) for record in records)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a metadata-only CatMeows manifest")
    parser.add_argument("root", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    records = build_manifest(args.root.resolve())
    write_csv(records, args.output)
    print(f"wrote {len(records)} records to {args.output}")


if __name__ == "__main__":
    main()
