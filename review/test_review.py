from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from review.common import CONDITIONS, METHOD_FOR_PART, PARTS, VERDICTS, load_clips
from review.score import load_reviews, render_markdown, score
from review.template import COLUMNS, rows_for_clip, write_template

CLIP = {"clip_id": "clip-a", "manifest": "x", "sample_fps": 2.0, "max_seconds": 1.0, "tail_seed": {}}
CLIP_NO_TAIL = {"clip_id": "clip-b", "manifest": "x", "sample_fps": 2.0, "max_seconds": 1.0}
MANIFEST = {
    "frames": [
        {"frame_index": 0, "timestamp_s": 0.0},
        {"frame_index": 1, "timestamp_s": 0.5},
    ]
}


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def _row(clip: str, frame: int, part: str, verdict: str, condition: str = "", note: str = "") -> dict[str, str]:
    return {
        "clip_id": clip,
        "frame_index": str(frame),
        "timestamp_s": "0.0",
        "part": part,
        "method": METHOD_FOR_PART[part],
        "verdict": verdict,
        "condition": condition,
        "note": note,
    }


class ConfigTests(unittest.TestCase):
    def test_review_set_is_loadable_and_seeds_are_consistent(self) -> None:
        clips = load_clips()
        self.assertGreaterEqual(len(clips), 2)
        for clip in clips:
            seed = clip.get("tail_seed")
            if seed:
                self.assertAlmostEqual(
                    seed["review_frame_index"] / clip["sample_fps"],
                    seed["fixture_timestamp_s"],
                    places=6,
                )

    def test_vocabularies_are_disjoint_and_complete(self) -> None:
        self.assertEqual(set(METHOD_FOR_PART), set(PARTS))
        self.assertIn("ok", VERDICTS)
        self.assertIn("none", CONDITIONS)


class TemplateTests(unittest.TestCase):
    def test_rows_cover_every_frame_and_part(self) -> None:
        rows = rows_for_clip(CLIP, MANIFEST)
        self.assertEqual(len(rows), 2 * len(PARTS))
        self.assertTrue(all(row["verdict"] == "" for row in rows))

    def test_tail_rows_skipped_without_seed(self) -> None:
        rows = rows_for_clip(CLIP_NO_TAIL, MANIFEST)
        self.assertEqual(len(rows), 2 * (len(PARTS) - 1))
        self.assertNotIn("tail_curve", {row["part"] for row in rows})

    def test_template_round_trips_through_loader(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "t.csv"
            count = write_template(path, [CLIP], {"clip-a": MANIFEST})
            self.assertEqual(count, 2 * len(PARTS))
            self.assertEqual(load_reviews(path), {})  # nothing filled in yet


class ScoreTests(unittest.TestCase):
    def test_percent_ok_excludes_not_visible(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "alice.csv"
            _write_csv(
                path,
                [
                    _row("clip-a", 0, "head", "ok"),
                    _row("clip-a", 1, "head", "wrong", "blur", "eyes on ear"),
                    _row("clip-a", 0, "tail_curve", "not_visible"),
                    _row("clip-a", 1, "tail_curve", "ok"),
                ],
            )
            result = score([path])
            totals = {(t["method"], t["part"]): t for t in result["reviewers"]["alice"]["totals"]}
            self.assertEqual(totals[("body", "head")]["pct_ok_of_visible"], 50.0)
            self.assertEqual(totals[("body", "head")]["wrong_by_condition"], {"blur": 1})
            self.assertEqual(totals[("tail", "tail_curve")]["n_visible"], 1)
            self.assertEqual(totals[("tail", "tail_curve")]["pct_ok_of_visible"], 100.0)
            self.assertEqual(result["reviewers"]["alice"]["failures"][0]["note"], "eyes on ear")
            self.assertIn("| body | head | 2 | 1 | 1 | 0 | 50.0 | blur 1 |", render_markdown(result))

    def test_invalid_vocabulary_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.csv"
            _write_csv(path, [_row("clip-a", 0, "head", "fine")])
            with self.assertRaises(ValueError):
                load_reviews(path)
            _write_csv(path, [_row("clip-a", 0, "head", "ok", "rainy")])
            with self.assertRaises(ValueError):
                load_reviews(path)
            _write_csv(path, [_row("clip-a", 0, "head", "ok"), _row("clip-a", 0, "head", "ok")])
            with self.assertRaises(ValueError):
                load_reviews(path)

    def test_two_reviewers_report_agreement_and_disagreements(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            a = Path(tmp) / "a.csv"
            b = Path(tmp) / "b.csv"
            _write_csv(a, [_row("clip-a", 0, "head", "ok"), _row("clip-a", 1, "head", "ok")])
            _write_csv(b, [_row("clip-a", 0, "head", "ok"), _row("clip-a", 1, "head", "wrong", "occlusion")])
            result = score([a, b])
            self.assertEqual(result["agreement"]["n_shared"], 2)
            self.assertEqual(result["agreement"]["pct_agree"], 50.0)
            self.assertEqual(result["agreement"]["disagreements"][0]["frame_index"], 1)
            json.dumps(result)  # serialisable


if __name__ == "__main__":
    unittest.main()
