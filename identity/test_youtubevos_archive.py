from __future__ import annotations

import json
import tempfile
import unittest
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image

from identity import youtubevos_archive as ya


class YouTubeVOSArchiveTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _build_archive(
        self,
        *,
        mismatch: bool = False,
        unsafe_meta: bool = False,
        overlap: bool = False,
    ) -> Path:
        frames = ["00000", "00005", "00010"]
        meta = {
            "videos": {
                "vidcat": {
                    "objects": {
                        "1": {"category": "cat", "frames": ["00000", "00010"]},
                        "2": {"category": "cat", "frames": frames},
                        "3": {"category": "dog", "frames": frames},
                    }
                },
                "onecat": {
                    "objects": {
                        "1": {"category": "cat", "frames": frames},
                    }
                },
            }
        }
        archive = self.root / "train.zip"
        with zipfile.ZipFile(archive, "w", allowZip64=True) as zf:
            meta_name = "../meta.json" if unsafe_meta else "train/meta.json"
            zf.writestr(meta_name, json.dumps(meta))
            for video_id in ("vidcat", "onecat"):
                for idx, frame in enumerate(frames):
                    arr = np.full((8, 12, 3), 40 + idx, dtype=np.uint8)
                    img_path = self.root / f"{video_id}-{frame}.jpg"
                    Image.fromarray(arr).save(img_path)
                    zf.write(img_path, f"train/JPEGImages/{video_id}/{frame}.jpg")
                    label = np.zeros((8, 12), dtype=np.uint8)
                    if video_id == "vidcat":
                        if frame != "00005":
                            label[1:4, 1:4] = 1
                        label[1:4, 7:10] = 2
                        label[5:7, 4:6] = 3
                        if overlap and frame == "00010":
                            label[1:4, 3:6] = 1
                            label[2:5, 5:8] = 2
                        if mismatch and frame == "00010":
                            label[label == 1] = 0
                    else:
                        label[1:4, 1:4] = 1
                    mask_path = self.root / f"{video_id}-{frame}.png"
                    Image.fromarray(label).save(mask_path)
                    zf.write(mask_path, f"train/Annotations/{video_id}/{frame}.png")
        return archive

    def test_materialize_vos_layout_with_stable_ids(self):
        archive = self._build_archive()
        result = ya.materialize_selected_sequence(
            archive_path=archive,
            output_root=self.root / "out",
            source_uri="fixture://train.zip",
        )
        selection = result["selection"]
        manifest = result["davis_manifest"]
        self.assertEqual(selection["dataset"], "YouTube-VOS-2019")
        self.assertEqual(selection["selected"]["video_id"], "vidcat")
        self.assertEqual(selection["selected"]["cat_instance_count"], 2)
        self.assertEqual(selection["selected"]["co_visible_frames"], 2)
        self.assertEqual(selection["selected"]["max_internal_gap_frames"], 1)
        self.assertEqual(manifest["stable_id_by_source_object_id"], {"1": 1, "2": 2})
        self.assertEqual(manifest["frame_count"], 3)
        middle = np.asarray(
            Image.open(self.root / "out/davis/annotations/frame_000001.png")
        )
        self.assertEqual(set(np.unique(middle).tolist()), {0, 2})
        meta = json.loads((self.root / "out/davis/meta.json").read_text())
        self.assertEqual(meta["source_dataset"], "YouTube-VOS-2019")
        self.assertEqual(meta["frame_names"][0], "frame_000000.jpg")

    def test_bbox_overlap_is_computed_from_indexed_masks(self):
        archive = self._build_archive(overlap=True)
        with zipfile.ZipFile(archive, "r") as zf:
            members = ya._member_index(zf)
            meta_member = ya.locate_meta_member(zf)
            meta = ya.read_meta_from_archive(zf, meta_member)
            stats = ya.candidate_stats(
                zf,
                meta=meta,
                meta_member=meta_member,
                members=members,
                video_id="vidcat",
            )
        self.assertGreaterEqual(stats["bbox_overlap_frames"], 1)

    def test_metadata_mask_mismatch_rejects_candidate(self):
        archive = self._build_archive(mismatch=True)
        with self.assertRaisesRegex(
            ya.YouTubeVOSArchiveError, "no source video has at least 2 consistent"
        ):
            ya.materialize_selected_sequence(
                archive_path=archive,
                output_root=self.root / "out",
            )

    def test_unsafe_meta_path_fails_closed(self):
        archive = self._build_archive(unsafe_meta=True)
        with zipfile.ZipFile(archive, "r") as zf:
            with self.assertRaisesRegex(ya.YouTubeVOSArchiveError, "unsafe ZIP member"):
                ya.locate_meta_member(zf)


if __name__ == "__main__":
    unittest.main()
