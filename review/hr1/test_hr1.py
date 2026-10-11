from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from review.hr1.agreement import cohen_kappa, krippendorff_alpha_nominal, pairwise
import hashlib

from review.hr1.score import check_locks, load_stage_a, load_stage_b, score, unanimous
from review.hr1 import withholding as wh


def _two_raters(yy: int, yn: int, ny: int, nn: int) -> tuple[dict, dict]:
    a, b, i = {}, {}, 0
    for la, lb, n in (("y", "y", yy), ("y", "n", yn), ("n", "y", ny), ("n", "n", nn)):
        for _ in range(n):
            a[i], b[i] = la, lb
            i += 1
    return a, b


class AgreementTests(unittest.TestCase):
    def test_textbook_kappa_and_alpha(self):
        # po = 0.70; Cohen pe = 0.25*... = 0.50 -> kappa 0.40.
        # Krippendorff: n = 100 pairable values, Do = 30, De = 2*55*45/99 = 50 -> alpha 0.40.
        a, b = _two_raters(20, 5, 10, 15)
        self.assertAlmostEqual(cohen_kappa(a, b), 0.40, places=6)
        self.assertAlmostEqual(krippendorff_alpha_nominal({"a": a, "b": b}), 0.40, places=6)

    def test_perfect_agreement(self):
        a = {1: "x", 2: "y", 3: "x"}
        self.assertEqual(cohen_kappa(a, dict(a)), 1.0)
        self.assertEqual(krippendorff_alpha_nominal({"a": a, "b": dict(a), "c": dict(a)}), 1.0)

    def test_missing_items_are_dropped(self):
        a = {1: "x", 2: "y", 3: "x"}
        b = {1: "x", 2: "y"}
        self.assertEqual(krippendorff_alpha_nominal({"a": a, "b": b}), 1.0)
        self.assertEqual(pairwise({"a": a, "b": b})[0]["n_shared"], 2)

    def test_single_category_is_undefined(self):
        a = {1: "x", 2: "x"}
        self.assertIsNone(cohen_kappa(a, dict(a)))


class ConsensusTests(unittest.TestCase):
    def test_unanimous_or_uncertain(self):
        self.assertEqual(unanimous(["positive", "positive"]), "positive")
        self.assertEqual(unanimous(["positive", "negative"]), "uncertain")


def _write(path: Path, cols: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as h:
        w = csv.DictWriter(h, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)


class ScoreTests(unittest.TestCase):
    """A four-frame synthetic key on a real holdout clip id; labels are test fixtures."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        clip = "holdout-larry-nails"
        self.key = {
            "methods": ["tail_grounded_v1", "tail_grounded_v3"],
            "items": {"B001": {"clip_id": clip, "frame_index": 0}, "B002": {"clip_id": clip, "frame_index": 1}, "B003": {"clip_id": clip, "frame_index": 2}},
            "repeat_of": {"B004": "B001"},
            "frames": [
                {"set": "holdout1", "clip_id": clip, "frame_index": 0, "methods": {m: {"asserted": True, "item_id": "B001"} for m in ("tail_grounded_v1", "tail_grounded_v3")}},
                {"set": "holdout1", "clip_id": clip, "frame_index": 1, "methods": {m: {"asserted": True, "item_id": "B002"} for m in ("tail_grounded_v1", "tail_grounded_v3")}},
                {"set": "holdout1", "clip_id": clip, "frame_index": 2, "methods": {"tail_grounded_v1": {"asserted": False, "item_id": None}, "tail_grounded_v3": {"asserted": True, "item_id": "B003"}}},
                {"set": "holdout1", "clip_id": clip, "frame_index": 3, "methods": {m: {"asserted": False, "item_id": None} for m in ("tail_grounded_v1", "tail_grounded_v3")}},
            ],
        }
        (self.tmp / "key.json").write_text(json.dumps(self.key), encoding="utf-8")
        a_cols = ["clip_id", "frame_index", "timestamp_s", "sheet", "tail", "note"]
        a1 = ["visible", "visible", "partial", "not_visible"]
        a2 = ["visible", "visible", "visible", "cannot_tell"]
        for name, labels in (("r1", a1), ("r2", a2)):
            _write(self.tmp / "stage_a" / f"{name}.csv", a_cols, [{"clip_id": clip, "frame_index": i, "timestamp_s": "0", "sheet": "s", "tail": v, "note": ""} for i, v in enumerate(labels)])
        b1 = {"B001": "on_tail", "B002": "not_on_tail", "B003": "on_tail", "B004": "on_tail"}
        b2 = {"B001": "on_tail", "B002": "not_on_tail", "B003": "cannot_tell", "B004": "not_on_tail"}
        for name, labels in (("r1", b1), ("r2", b2)):
            _write(self.tmp / "stage_b" / f"{name}.csv", ["item_id", "on_tail", "note"], [{"item_id": k, "on_tail": v, "note": ""} for k, v in labels.items()])

    def test_end_to_end(self):
        r = score(sorted((self.tmp / "stage_a").glob("*.csv")), sorted((self.tmp / "stage_b").glob("*.csv")), self.tmp / "key.json")
        # frames 0-2 positive by both (partial and visible collapse), frame 3 disagrees -> uncertain
        self.assertEqual(r["stage_a"]["consensus_counts"], {"positive": 3, "uncertain": 1})
        v1 = r["methods"]["tail_grounded_v1"]["holdout1"]
        self.assertEqual((v1["TP"], v1["FPv"], v1["FN"], v1["FPn"], v1["excluded_frame"]), (1, 1, 1, 0, 1))
        v3 = r["methods"]["tail_grounded_v3"]["holdout1"]
        # frame 2's curve is disputed in Stage B -> excluded, not counted either way
        self.assertEqual((v3["TP"], v3["FPv"], v3["FN"], v3["excluded_assertion"]), (1, 1, 0, 1))
        self.assertEqual(r["stage_b"]["self_consistency"]["r1"], {"n": 1, "same": 1})
        self.assertEqual(r["stage_b"]["self_consistency"]["r2"], {"n": 1, "same": 0})

    def test_lock_check(self):
        p = self.tmp / "stage_a" / "r1.csv"
        good = hashlib.sha256(p.read_bytes()).hexdigest()
        check_locks([p], {"stage_a/r1.csv": good})
        with self.assertRaises(SystemExit):
            check_locks([p], {"stage_a/r1.csv": "0" * 64})
        with self.assertRaises(SystemExit):
            check_locks([p], {})

    def test_blank_label_is_an_error(self):
        p = self.tmp / "bad.csv"
        _write(p, ["clip_id", "frame_index", "tail"], [{"clip_id": "c", "frame_index": 0, "tail": ""}])
        with self.assertRaises(ValueError):
            load_stage_a(p)

    def test_unknown_label_is_an_error(self):
        p = self.tmp / "bad_b.csv"
        _write(p, ["item_id", "on_tail"], [{"item_id": "B001", "on_tail": "maybe"}])
        with self.assertRaises(ValueError):
            load_stage_b(p)


class WithholdingTests(unittest.TestCase):
    """The public tree must not let a reviewer rebuild the Stage B key, outputs or mapping early.

    Each rule has a negative control: a tree that breaks it on purpose must be reported.
    """

    COMMIT = {"note": "", "scheme": "", "n_items": 3, "n_repeats": 1, "root_sha256": "0" * 64}
    SALT = "ab" * 32

    def _check(self, files: dict[str, object], private=None) -> list[str]:
        blobs = {k: v if isinstance(v, bytes) else json.dumps(v).encode() for k, v in files.items()}
        blobs.setdefault(wh.COMMITMENT, json.dumps(self.COMMIT).encode())
        return wh.check(sorted(blobs), blobs.__getitem__, private)

    def _locks(self, a: list[str], b: list[str]) -> dict:
        return {**{f"stage_a/stage-a-{h}.csv": "1" * 64 for h in a}, **{f"stage_b/stage-b-{h}.csv": "2" * 64 for h in b}}

    def test_repository_withholds_now(self):
        # the real tracked tree; also scans for the salt and curve keys when the private build is present
        self.assertEqual(wh.check_repo(), [])

    def test_key_outputs_manifest_before_stage_b_lock_are_reported(self):
        for path in ("review/hr1/key.json", "review/hr1/outputs/x--tail_grounded_v3.json",
                     "review/hr1/stage_b_manifest.json", "review/hr1/SECRET-salt.txt", "review/hr1/results.md"):
            for locks in ({}, self._locks(["r1", "r2"], []), self._locks(["r1", "r2"], ["r1"])):
                with self.subTest(path=path, locks=sorted(locks)):
                    self.assertTrue(self._check({path: b"{}", wh.LOCKS: locks}))
        self.assertEqual(self._check({"review/hr1/key.json": b"{}", wh.LOCKS: self._locks(["r1", "r2"], ["r1", "r2-r2"])}), [])

    def test_stage_b_images_need_two_stage_a_locks(self):
        img = wh.STAGE_B_PUBLIC + "items/B001.jpg"
        self.assertTrue(self._check({img: b"x", wh.LOCKS: self._locks(["r1"], [])}))
        self.assertEqual(self._check({img: b"x", wh.LOCKS: self._locks(["r1", "r2"], [])}), [])

    def test_commitment_may_not_carry_per_item_or_seed_fields(self):
        for extra in ({"seed": 20261011}, {"images": {"B001.jpg": "0" * 64}}, {"key_sha256": "0" * 64}):
            with self.subTest(extra=extra):
                self.assertTrue(self._check({wh.COMMITMENT: {**self.COMMIT, **extra}}))

    def test_salt_or_curve_key_in_any_tracked_text_is_reported(self):
        private = {"salt": self.SALT, "curve_keys": {"B001": "0123456789abcdef"}}
        self.assertEqual(self._check({"notes.md": b"nothing here"}, private), [])
        self.assertTrue(self._check({"notes.md": f"salt {self.SALT}".encode()}, private))
        self.assertTrue(self._check({"x.csv": b"B001,0123456789abcdef"}, private))

    def test_private_working_set_must_not_be_tracked(self):
        self.assertTrue(self._check({"review/work/hr1/stage_b/key.json": b"{}"}))

    def test_order_depends_on_the_secret_salt(self):
        order = lambda salt: [wh.shuffle_rng(salt).random() for _ in range(3)]
        self.assertEqual(order(self.SALT), order(self.SALT))
        self.assertNotEqual(order(self.SALT), order("cd" * 32))

    def test_release_verification_detects_tampering(self):
        tmp = Path(tempfile.mkdtemp())
        (tmp / "key.json").write_text("{}", encoding="utf-8")
        (tmp / "t.csv").write_text("item_id,on_tail,note\n", encoding="utf-8")
        (tmp / "B001.jpg").write_bytes(b"img")
        sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
        manifest = {"salt": self.SALT, "n_items": 1, "n_repeats": 0, "key_sha256": sha(tmp / "key.json"),
                    "template_sha256": sha(tmp / "t.csv"), "images": {"B001.jpg": sha(tmp / "B001.jpg")}, "outputs": {}}
        commitment = {**self.COMMIT, "root_sha256": wh.manifest_root(manifest)}
        files = {"key": tmp / "key.json", "template": tmp / "t.csv", "images/B001.jpg": tmp / "B001.jpg"}
        self.assertEqual(wh.verify_release(manifest, commitment, files), [])
        (tmp / "key.json").write_text('{"changed": 1}', encoding="utf-8")
        self.assertTrue(wh.verify_release(manifest, commitment, files))
        self.assertTrue(wh.verify_release({**manifest, "salt": "cd" * 32}, commitment, files))


if __name__ == "__main__":
    unittest.main()
