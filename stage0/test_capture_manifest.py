from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from stage0.validate_capture_manifest import sha256, validate


class CaptureManifestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(__file__).parents[1]
        cls.schema = cls.root / "schemas" / "stage0-capture-manifest.schema.json"
        cls.example = Path(__file__).with_name("example-capture-manifest.json")

    def test_example_manifest_is_schema_valid(self) -> None:
        self.assertEqual(validate(self.example, self.schema), [])

    def test_animal_presence_is_rejected(self) -> None:
        manifest = json.loads(self.example.read_text(encoding="utf-8"))
        manifest["animal_present"] = True
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            errors = validate(path, self.schema)
        self.assertTrue(any("animal_present" in error for error in errors))

    def test_file_integrity_verification(self) -> None:
        manifest = json.loads(self.example.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            payload = root / "capture.bin"
            payload.write_bytes(b"catpose-stage0")
            manifest["files"] = [
                {
                    "role": "video",
                    "path": "capture.bin",
                    "sha256": sha256(payload),
                    "byte_count": payload.stat().st_size,
                    "frame_count": 1
                }
            ]
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            self.assertEqual(validate(manifest_path, self.schema, root), [])

            payload.write_bytes(b"modified")
            errors = validate(manifest_path, self.schema, root)
            self.assertTrue(any("byte_count" in error for error in errors))
            self.assertTrue(any("sha256" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
