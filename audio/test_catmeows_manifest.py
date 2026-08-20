from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from audio.catmeows_manifest import build_manifest, parse_filename, write_csv
from audio.group_splits import leave_one_group_out, read_manifest, validate_folds


class CatMeowsManifestTests(unittest.TestCase):
    def test_parse_declared_filename_convention(self) -> None:
        record = parse_filename(Path("F_ABC01_EU_FN_OWNER_203.wav"))
        self.assertEqual("waiting_for_food", record.context)
        self.assertEqual("ABC01", record.cat_id)
        self.assertEqual("european_shorthair", record.breed)
        self.assertEqual("female_neutered", record.sex)
        self.assertEqual("OWNER", record.owner_id)
        self.assertEqual(2, record.session)
        self.assertEqual(3, record.vocalisation_index)
        self.assertEqual("ABC01:2", record.sequence_group)

    def test_invalid_filename_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            parse_filename(Path("mystery-cat.wav"))

    def test_manifest_and_leave_one_cat_out_have_no_cat_leakage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            names = [
                "B_CAT01_EU_FN_OWN01_101.wav",
                "F_CAT01_EU_FN_OWN01_102.wav",
                "I_CAT01_EU_FN_OWN01_201.wav",
                "B_CAT02_MC_MI_OWN02_101.wav",
                "F_CAT02_MC_MI_OWN02_201.wav",
                "I_CAT02_MC_MI_OWN02_202.wav",
                "B_CAT03_EU_MN_OWN03_101.wav",
                "F_CAT03_EU_MN_OWN03_201.wav",
                "I_CAT03_EU_MN_OWN03_301.wav",
            ]
            for name in names:
                (root / name).touch()

            records = build_manifest(root)
            self.assertEqual(len(names), len(records))

            manifest_path = root / "manifest.csv"
            write_csv(records, manifest_path)
            rows = read_manifest(manifest_path)
            folds = leave_one_group_out(rows, "cat_id")
            self.assertEqual(3, len(folds))
            self.assertEqual([], validate_folds(rows, folds, "cat_id"))

            by_path = {row["path"]: row for row in rows}
            for fold in folds:
                held_out = fold["held_out_group"]
                self.assertTrue(all(by_path[path]["cat_id"] == held_out for path in fold["test_paths"]))
                self.assertTrue(all(by_path[path]["cat_id"] != held_out for path in fold["train_paths"]))

    def test_owner_folds_are_supported(self) -> None:
        rows = [
            {"path": "a.wav", "cat_id": "cat-a", "owner_id": "owner-1", "sequence_group": "cat-a:1"},
            {"path": "b.wav", "cat_id": "cat-b", "owner_id": "owner-1", "sequence_group": "cat-b:1"},
            {"path": "c.wav", "cat_id": "cat-c", "owner_id": "owner-2", "sequence_group": "cat-c:1"},
        ]
        folds = leave_one_group_out(rows, "owner_id")
        self.assertEqual(2, len(folds))
        self.assertEqual([], validate_folds(rows, folds, "owner_id"))

    def test_csv_contains_grouping_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            wav = root / "B_CAT01_MC_FI_OWN01_101.wav"
            wav.touch()
            output = root / "manifest.csv"
            write_csv(build_manifest(root), output)
            with output.open(newline="", encoding="utf-8") as handle:
                row = next(csv.DictReader(handle))
            for field in ("cat_id", "owner_id", "session", "sequence_group", "context"):
                self.assertIn(field, row)


if __name__ == "__main__":
    unittest.main()
