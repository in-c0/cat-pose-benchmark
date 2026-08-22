from __future__ import annotations

import json
import tempfile
import unittest
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image

from identity import youtubevis_archive as ya


def rle_counts(mask: np.ndarray) -> list[int]:
    flat = np.asarray(mask, dtype=np.uint8).reshape(-1, order="F")
    runs: list[int] = []
    value = 0
    count = 0
    for pixel in flat.tolist():
        pixel = int(pixel)
        if pixel == value:
            count += 1
        else:
            runs.append(count)
            count = 1
            value = pixel
    runs.append(count)
    return runs


def rle(mask: np.ndarray) -> dict:
    return {"size": list(mask.shape), "counts": rle_counts(mask)}


class YouTubeVISArchiveTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _build_archive(self, *, duplicate_frame: bool = False) -> Path:
        width, height, length = 6, 4, 3
        names = [f"abc/{i:05d}.jpg" for i in range(length)]
        masks = []
        for side in (0, 4):
            seq = []
            for _ in range(length):
                mask = np.zeros((height, width), dtype=bool)
                mask[1:3, side : side + 2] = True
                seq.append(rle(mask))
            masks.append(seq)
        data = {
            "videos": [
                {
                    "id": 99,
                    "width": width,
                    "height": height,
                    "length": length,
                    "file_names": names,
                }
            ],
            "categories": [{"id": 17, "name": "cat"}],
            "annotations": [
                {
                    "id": 10,
                    "video_id": 99,
                    "category_id": 17,
                    "segmentations": masks[0],
                    "bboxes": [[0, 1, 2, 2]] * length,
                },
                {
                    "id": 20,
                    "video_id": 99,
                    "category_id": 17,
                    "segmentations": masks[1],
                    "bboxes": [[4, 1, 2, 2]] * length,
                },
            ],
        }
        archive = self.root / "train.zip"
        with zipfile.ZipFile(archive, "w", allowZip64=True) as zf:
            zf.writestr("dataset/train.json", json.dumps(data))
            for i, name in enumerate(names):
                arr = np.full((height, width, 3), 30 + i, dtype=np.uint8)
                image_path = self.root / f"frame{i}.jpg"
                Image.fromarray(arr).save(image_path)
                zf.write(image_path, f"train/JPEGImages/{name}")
                if duplicate_frame and i == 0:
                    zf.write(image_path, f"other/JPEGImages/{name}")
        return archive

    def test_materializes_only_selected_sequence_and_converts_to_davis(self):
        archive = self._build_archive()
        result = ya.materialize_selected_sequence(
            archive_path=archive,
            output_root=self.root / "out",
            source_uri="fixture://train.zip",
        )
        self.assertEqual(result["selection"]["selected"]["video_id"], 99)
        self.assertFalse(result["selection"]["remind_scoring_performed"])
        self.assertEqual(
            result["davis_manifest"]["stable_id_by_source_annotation_id"],
            {"10": 1, "20": 2},
        )
        for i in range(3):
            self.assertTrue(
                (self.root / "out" / "source_frames" / "abc" / f"{i:05d}.jpg").is_file()
            )
            self.assertTrue(
                (self.root / "out" / "davis" / "annotations" / f"frame_{i:06d}.png").is_file()
            )

    def test_duplicate_archive_member_suffix_fails_closed(self):
        archive = self._build_archive(duplicate_frame=True)
        with self.assertRaisesRegex(ya.YouTubeVISArchiveError, "exactly one archive member"):
            ya.materialize_selected_sequence(
                archive_path=archive,
                output_root=self.root / "out",
            )

    def test_unsafe_archive_member_fails_closed(self):
        archive = self.root / "train.zip"
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr("../train.json", "{}")
        with zipfile.ZipFile(archive, "r") as zf:
            with self.assertRaisesRegex(ya.YouTubeVISArchiveError, "unsafe ZIP member"):
                ya.locate_annotations_member(zf)

    def test_absolute_archive_member_fails_closed(self):
        archive = self.root / "train.zip"
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr("/train.json", "{}")
        with zipfile.ZipFile(archive, "r") as zf:
            with self.assertRaisesRegex(ya.YouTubeVISArchiveError, "unsafe ZIP member"):
                ya.locate_annotations_member(zf)


if __name__ == "__main__":
    unittest.main()
