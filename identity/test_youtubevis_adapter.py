from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from identity import youtubevis_adapter as yv


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


def encode_compressed_counts(counts: list[int]) -> str:
    chars: list[str] = []
    for i, count in enumerate(counts):
        x = int(count)
        if i > 2:
            x -= int(counts[i - 2])
        more = True
        while more:
            c = x & 0x1F
            x >>= 5
            more = (x != -1) if (c & 0x10) else (x != 0)
            if more:
                c |= 0x20
            chars.append(chr(c + 48))
    return "".join(chars)


def rle(mask: np.ndarray, *, compressed: bool = False) -> dict:
    counts = rle_counts(mask)
    return {
        "size": [int(mask.shape[0]), int(mask.shape[1])],
        "counts": encode_compressed_counts(counts) if compressed else counts,
    }


def build_dataset(root: Path) -> tuple[Path, Path, dict]:
    frames_root = root / "frames_source"
    video_dir = frames_root / "vidA"
    video_dir.mkdir(parents=True)
    width, height, length = 6, 4, 4
    names = []
    for i in range(length):
        name = f"vidA/{i:05d}.jpg"
        names.append(name)
        arr = np.full((height, width, 3), 20 + i, dtype=np.uint8)
        Image.fromarray(arr).save(frames_root / name)

    left = []
    right = []
    for i in range(length):
        m1 = np.zeros((height, width), dtype=bool)
        m2 = np.zeros((height, width), dtype=bool)
        m1[1:3, 0:2] = True
        if i != 2:
            m2[1:3, 4:6] = True
        left.append(rle(m1, compressed=(i % 2 == 1)))
        right.append(None if i == 2 else rle(m2, compressed=(i % 2 == 0)))

    data = {
        "videos": [
            {
                "id": 10,
                "width": width,
                "height": height,
                "length": length,
                "file_names": names,
            },
            {
                "id": 20,
                "width": width,
                "height": height,
                "length": length,
                "file_names": names,
            },
        ],
        "categories": [
            {"id": 7, "name": "dog", "supercategory": "animal"},
            {"id": 42, "name": "cat", "supercategory": "animal"},
        ],
        "annotations": [
            {
                "id": 100,
                "video_id": 10,
                "category_id": 42,
                "segmentations": left,
                "bboxes": [[0, 1, 2, 2]] * length,
            },
            {
                "id": 200,
                "video_id": 10,
                "category_id": 42,
                "segmentations": right,
                "bboxes": [[4, 1, 2, 2], [4, 1, 2, 2], None, [4, 1, 2, 2]],
            },
            {
                "id": 300,
                "video_id": 20,
                "category_id": 42,
                "segmentations": left,
                "bboxes": [[0, 1, 2, 2]] * length,
            },
            {
                "id": 400,
                "video_id": 20,
                "category_id": 42,
                "segmentations": left,
                "bboxes": [[0, 1, 2, 2]] * length,
            },
        ],
    }
    annotations_path = root / "annotations.json"
    annotations_path.write_text(json.dumps(data), encoding="utf-8")
    return annotations_path, frames_root, data


class YouTubeVISAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_category_resolved_by_name_and_candidates_rank_before_scoring(self):
        _, _, data = build_dataset(self.root)
        self.assertEqual(yv.resolve_category_id(data, "CAT"), 42)
        candidates = yv.inspect_candidates(data, category_name="cat", min_instances=2)
        self.assertEqual([row["video_id"] for row in candidates], [20, 10])
        self.assertEqual(candidates[0]["selection_rank"], 1)
        self.assertEqual(candidates[0]["selection_rule_version"], yv.SELECTION_RULE_VERSION)
        self.assertEqual(candidates[1]["max_internal_gap_frames"], 1)
        self.assertIn("short_occlusion_candidate", candidates[1]["stress_stratum_hints"])

    def test_compressed_rle_roundtrip_matches_reference_algorithm(self):
        mask = np.zeros((5, 7), dtype=bool)
        mask[0:2, 1:4] = True
        mask[3:5, 5:7] = True
        counts = rle_counts(mask)
        encoded = encode_compressed_counts(counts)
        self.assertEqual(yv._decode_compressed_counts(encoded), counts)
        decoded = yv.decode_segmentation(
            {"size": [5, 7], "counts": encoded}, height=5, width=7
        )
        np.testing.assert_array_equal(decoded, mask)

    def test_convert_writes_stable_davis_ids_meta_and_provenance(self):
        annotations_path, frames_root, _ = build_dataset(self.root)
        output = self.root / "out"
        manifest = yv.convert_video(
            annotations_path=annotations_path,
            frames_root=frames_root,
            output_dir=output,
            video_id=10,
            category_name="cat",
            source_uri="fixture://ytvis",
        )
        self.assertTrue(manifest["quantitative_ready_for_remind_davis"])
        self.assertFalse(manifest["claims"]["remind_scoring_performed"])
        self.assertEqual(manifest["stable_id_by_source_annotation_id"], {"100": 1, "200": 2})

        meta = json.loads((output / "meta.json").read_text(encoding="utf-8"))
        self.assertEqual(meta["id_to_label"], {"1": "cat_1", "2": "cat_2"})
        self.assertEqual(
            meta["frame_names"],
            [f"frame_{i:06d}.jpg" for i in range(4)],
        )

        mask0 = np.asarray(Image.open(output / "annotations" / "frame_000000.png"))
        self.assertEqual(set(np.unique(mask0).tolist()), {0, 1, 2})
        self.assertTrue(np.all(mask0[1:3, 0:2] == 1))
        self.assertTrue(np.all(mask0[1:3, 4:6] == 2))

        mask2 = np.asarray(Image.open(output / "annotations" / "frame_000002.png"))
        self.assertEqual(set(np.unique(mask2).tolist()), {0, 1})
        self.assertEqual(manifest["masks"][2]["visible_stable_ids"], [1])

    def test_length_mismatch_fails_closed(self):
        _, _, data = build_dataset(self.root)
        data["annotations"][0]["segmentations"] = data["annotations"][0]["segmentations"][:-1]
        with self.assertRaisesRegex(yv.YouTubeVISAdapterError, "segmentations length mismatch"):
            yv.inspect_candidates(data, category_name="cat", min_instances=2)

    def test_overlapping_instance_masks_fail_closed(self):
        annotations_path, frames_root, data = build_dataset(self.root)
        m = np.zeros((4, 6), dtype=bool)
        m[1:3, 1:3] = True
        data["annotations"][1]["segmentations"][1] = rle(m)
        annotations_path.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaisesRegex(yv.YouTubeVISAdapterError, "overlapping instance masks"):
            yv.convert_video(
                annotations_path=annotations_path,
                frames_root=frames_root,
                output_dir=self.root / "out",
                video_id=10,
            )

    def test_frame_path_traversal_fails_closed(self):
        annotations_path, frames_root, data = build_dataset(self.root)
        outside = self.root / "outside.jpg"
        Image.fromarray(np.zeros((4, 6, 3), dtype=np.uint8)).save(outside)
        data["videos"][0]["file_names"][0] = "../outside.jpg"
        annotations_path.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaisesRegex(yv.YouTubeVISAdapterError, "escapes frames root"):
            yv.convert_video(
                annotations_path=annotations_path,
                frames_root=frames_root,
                output_dir=self.root / "out",
                video_id=10,
            )

    def test_existing_nonempty_output_fails_closed(self):
        annotations_path, frames_root, _ = build_dataset(self.root)
        output = self.root / "out"
        output.mkdir()
        (output / "sentinel.txt").write_text("do not overwrite", encoding="utf-8")
        with self.assertRaisesRegex(yv.YouTubeVISAdapterError, "output directory is not empty"):
            yv.convert_video(
                annotations_path=annotations_path,
                frames_root=frames_root,
                output_dir=output,
                video_id=10,
            )


if __name__ == "__main__":
    unittest.main()
