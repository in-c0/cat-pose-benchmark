"""BH1 tests. Synthetic data only: nothing here reads a human label, because none exists."""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from behaviour import baselines, build, sample_pool, score, synthetic
from behaviour import withholding as wh
from behaviour.common import CLASSES, FRAMES_PER_SEGMENT, HERE, TEMPLATE_COLUMNS, n_segments, read_csv, write_csv

REPS = 1000


def _preds(runs: dict[str, list[dict]]) -> dict[str, dict[str, dict]]:
    return {n: {r["segment_id"]: {"pred": r["pred"], "prob_max": r["prob_max"], "cat_seen_in_training": str(r["cat_seen_in_training"])} for r in rows}
            for n, rows in runs.items()}


def _synthetic_result(mode: str, seed: int = 1) -> tuple[dict, dict]:
    d = synthetic.make(mode=mode, seed=seed)
    segs = d["segments"]
    X = np.stack([baselines.motion_features(d["frames"][s]) for s in segs])
    runs = baselines.run(segs, X, [d["truth"][s] for s in segs], d["clip_of"], d["cat_of"])
    # two labellers who agree everywhere, so the truth is the synthetic label
    labels = {"a": dict(d["truth"]), "b": dict(d["truth"])}
    for clip in d["key"]["clips"].values():
        clip["identity_confidence"] = "sure"
    return score.score(labels, d["key"], _preds(runs), reps=REPS), d


class ProtocolFreezeTests(unittest.TestCase):
    def test_frozen_text_unchanged(self):
        text = (HERE / "PROTOCOL.md").read_text(encoding="utf-8").replace("\r\n", "\n")
        frozen = text.split("\n## Amendments\n")[0]
        record = json.loads((HERE / "protocol_freeze.json").read_text(encoding="utf-8"))
        self.assertEqual(hashlib.sha256(frozen.encode("utf-8")).hexdigest(), record["sha256"],
                         "PROTOCOL.md changed above 'Amendments'; add a dated amendment instead")

    def test_protocol_names_every_label(self):
        text = (HERE / "PROTOCOL.md").read_text(encoding="utf-8")
        for label in CLASSES + ("cannot_tell",):
            self.assertIn(f"`{label}`", text)


class SegmentTests(unittest.TestCase):
    def test_whole_segments_in_first_twenty_seconds(self):
        self.assertEqual(n_segments(4.0), 2)
        self.assertEqual(n_segments(5.9), 2)
        self.assertEqual(n_segments(19.99), 9)
        self.assertEqual(n_segments(20.0), 10)
        self.assertEqual(n_segments(300.0), 10)
        self.assertEqual(n_segments(None), 0)


class PoolTests(unittest.TestCase):
    def test_walk_is_breadth_first_and_depth_limited(self):
        tree = {"Root": ["A", "B"], "A": ["C"], "B": ["A2"], "A2": ["C"], "C": ["D"], "D": []}
        files = {"Root": ["f0"], "A": ["f1"], "B": [], "A2": [], "C": ["f2"], "D": ["f3"]}

        def members(cat, kind):
            return tree.get(cat, []) if kind == "subcat" else files.get(cat, [])

        depth, found = sample_pool.walk_categories("Root", 2, members)
        self.assertEqual(depth, {"Root": 0, "A": 1, "B": 1, "C": 2, "A2": 2})
        self.assertEqual(set(found), {"f0", "f1", "f2"})  # D is depth 3, never listed

    def test_classify_records_by_sa_without_selecting_it(self):
        base = {"title": "File:x.webm", "mime": "video/webm", "duration_s": 10, "height": 720, "uploader": "u", "artist": "", "description": ""}
        sa = sample_pool.classify({**base, "licence": "CC BY-SA 4.0"})
        self.assertEqual((sa["licence_class"], sa["eligible"], sa["eligible_if_by_sa"], sa["reason"]), ("by_sa", False, True, "ok_if_by_sa_allowed"))
        ok = sample_pool.classify({**base, "licence": "CC BY 3.0"})
        self.assertEqual((ok["licence_class"], ok["eligible"]), ("licence_ok", True))
        nc = sample_pool.classify({**base, "licence": "CC BY-NC 4.0"})
        self.assertEqual((nc["licence_class"], nc["eligible"], nc["eligible_if_by_sa"]), ("other", False, False))
        self.assertIsNone(ok["cat_id"])

    def test_select_respects_cap_and_licence(self):
        files = {f"t{i}": {"eligible": i % 3 != 0, "eligible_if_by_sa": True, "uploader": "big" if i < 6 else f"u{i}", "licence": "x", "duration_s": 8} for i in range(12)}
        order = sample_pool.frozen_order(list(files), 7)
        self.assertEqual(order, sample_pool.frozen_order(list(files), 7))
        sel = sample_pool.select(files, order, cap=2, include_by_sa=False)
        self.assertLessEqual(sum(s["uploader"] == "big" for s in sel), 2)
        self.assertTrue(all(files[s["title"]]["eligible"] for s in sel))
        self.assertGreater(len(sample_pool.select(files, order, cap=2, include_by_sa=True)), len(sel))

    def test_committed_pool_is_consistent(self):
        files, drawn = sample_pool.load_pool()
        self.assertEqual(drawn["seed"], sample_pool.SEED)
        self.assertEqual(sorted(drawn["shuffled_order"]), sorted(files))
        self.assertEqual(drawn["shuffled_order"], sample_pool.frozen_order(list(files), drawn["seed"]))
        self.assertTrue(all(f["cat_id"] is None for f in files.values()), "cat_id is filled only by the identity pass")
        self.assertFalse(any(f["eligible"] and f["licence_class"] != "licence_ok" for f in files.values()))
        self.assertEqual(sample_pool.scenarios(files, drawn["shuffled_order"]), drawn["scenarios"])
        self.assertFalse((sample_pool.POOL_DIR / "selection.json").exists(), "selection waits for the owner's ruling")


class LabelFileTests(unittest.TestCase):
    def _load(self, rows):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "labels-x.csv"
            write_csv(p, TEMPLATE_COLUMNS, [{"segment_id": s, "behaviour": v} for s, v in rows])
            return score.load_labels(p, ["A-S00", "A-S01"])

    def test_valid_file(self):
        self.assertEqual(self._load([("A-S00", "walk"), ("A-S01", "Cannot_Tell")]), {"A-S00": "walk", "A-S01": "cannot_tell"})

    def test_rejections(self):
        for rows in ([("A-S00", "walk"), ("A-S01", "")],
                     [("A-S00", "walk"), ("A-S01", "happy")],
                     [("A-S00", "walk"), ("A-S00", "walk"), ("A-S01", "jump")],
                     [("A-S00", "walk")],
                     [("A-S00", "walk"), ("A-S01", "walk"), ("B-S00", "walk")]):
            with self.assertRaises(ValueError):
                self._load(rows)

    def test_latest_revision_is_scored(self):
        paths = [Path("labels-ann.csv"), Path("labels-ann-r2.csv"), Path("labels-bo.csv")]
        self.assertEqual({h: p.name for h, p in score.latest_per_labeller(paths).items()}, {"ann": "labels-ann-r2.csv", "bo": "labels-bo.csv"})


class AgreementTests(unittest.TestCase):
    def test_perfect_agreement_is_reliable(self):
        lab = {f"s{i}": CLASSES[i % 5] for i in range(50)}
        a = score.agreement({"a": lab, "b": dict(lab)})
        self.assertEqual((a["alpha_gate"], a["band"]), (1.0, "reliable"))

    def test_gate_is_the_lower_alpha(self):
        # agree on cannot_tell often, disagree on the classes: the six-label alpha flatters them
        rng = np.random.default_rng(3)
        a, b = {}, {}
        for i in range(200):
            if i < 120:
                a[i] = b[i] = "cannot_tell"
            else:
                a[i], b[i] = CLASSES[rng.integers(5)], CLASSES[rng.integers(5)]
        r = score.agreement({"a": a, "b": b})
        self.assertGreater(r["alpha_six_labels"], r["alpha_five_classes"])
        self.assertEqual(r["alpha_gate"], r["alpha_five_classes"])
        self.assertEqual(r["band"], "unreliable")

    def test_consensus_is_unanimous_or_uncertain(self):
        t = score.consensus({"a": {"x": "walk", "y": "walk", "z": "cannot_tell"}, "b": {"x": "walk", "y": "jump", "z": "cannot_tell"}})
        self.assertEqual(t, {"x": "walk", "y": "uncertain", "z": "cannot_tell"})


class MetricTests(unittest.TestCase):
    def test_metrics_match_sklearn(self):
        from sklearn.metrics import balanced_accuracy_score, f1_score

        rng = np.random.default_rng(0)
        y = rng.choice(CLASSES[:4], 300)  # one class absent from the truth
        p = np.where(rng.random(300) < 0.6, y, rng.choice(CLASSES, 300))
        conf = np.zeros((5, 5))
        for t, q in zip(y, p):
            conf[score.IDX[t], score.IDX[q]] += 1
        m = score.metrics_from(conf)
        self.assertAlmostEqual(float(m["ba"]), balanced_accuracy_score(y, p), places=10)
        self.assertAlmostEqual(float(m["macro_f1"]), f1_score(y, p, labels=list(CLASSES[:4]), average="macro"), places=10)
        self.assertTrue(np.isnan(m["f1"][4]))

    def test_uninformed_predictors_score_chance_on_balanced_accuracy(self):
        # the reason balanced accuracy, not macro-F1, is the decision metric
        rng = np.random.default_rng(1)
        y = rng.choice(CLASSES, 20000)
        majority = np.full_like(y, "walk")
        spread = rng.choice(CLASSES, 20000)
        def m(p):
            conf = np.zeros((5, 5))
            np.add.at(conf, ([score.IDX[t] for t in y], [score.IDX[q] for q in p]), 1)
            return score.metrics_from(conf)
        self.assertAlmostEqual(float(m(majority)["ba"]), 0.2, delta=0.01)
        self.assertAlmostEqual(float(m(spread)["ba"]), 0.2, delta=0.01)
        self.assertGreater(float(m(spread)["macro_f1"]), 1.5 * float(m(majority)["macro_f1"]))
        self.assertTrue(np.all(np.abs(m(spread)["f1_excess"]) < 0.02))

    def test_bootstrap_is_paired_and_by_cat(self):
        truth = {f"c{c}-S{k:02d}": CLASSES[(c + k) % 5] for c in range(12) for k in range(10)}
        cat_of = {s: s.split("-")[0] for s in truth}
        same = {s: {"pred": "walk", "prob_max": 1.0, "cat_seen_in_training": "0"} for s in truth}
        ev = score.evaluate(truth, {"majority--cat_disjoint": same, "copy--cat_disjoint": same}, cat_of, cat_of, reps=REPS)
        self.assertEqual(ev["comparisons"]["copy - majority (cat_disjoint)"], {"point": 0.0, "ci": [0.0, 0.0]})
        self.assertEqual(ev["chance_balanced_accuracy"], 0.2)

    def test_missing_prediction_is_an_error(self):
        truth = {"c1-S00": "walk", "c1-S01": "jump"}
        with self.assertRaises(ValueError):
            score.evaluate(truth, {"m--cat_disjoint": {"c1-S00": {"pred": "walk", "prob_max": 1.0, "cat_seen_in_training": ""}}}, {s: "c1" for s in truth}, {s: "c1" for s in truth}, reps=10)

    def test_blank_cat_id_refuses_to_score(self):
        with self.assertRaises(ValueError):
            score.score({"a": {"BH1-C001-S00": "walk"}, "b": {"BH1-C001-S00": "walk"}}, {"clips": {"BH1-C001": {"cat_id": "", "uploader": "u"}}}, {}, reps=10)


class SyntheticEndToEndTests(unittest.TestCase):
    """The decision rules on three synthetic worlds, including two negative controls."""

    def test_signal_is_recognised_on_unseen_cats(self):
        r, _ = _synthetic_result("signal")
        d = r["decisions"]
        self.assertTrue(d["R0_preconditions"]["met"])
        self.assertEqual(d["R2_unseen_cats"]["motion_lr"], "above chance on unseen cats")
        self.assertEqual(d["R4_seen_to_unseen"]["motion_lr"], "no material drop shown")
        self.assertTrue(d["outcome"].startswith("continue"))
        self.assertGreaterEqual(len(d["R5_recognised_classes"]["motion_lr"]), 3)

    def test_null_labels_are_not_recognised(self):
        # negative control: labels independent of the video must not pass R2 or R5
        r, _ = _synthetic_result("null")
        d = r["decisions"]
        self.assertEqual(d["R2_unseen_cats"]["motion_lr"], "not shown")
        self.assertEqual(d["R5_recognised_classes"]["motion_lr"], [])
        self.assertTrue(d["outcome"].startswith("kill at this scale"))

    def test_identity_shortcut_is_caught(self):
        # negative control: a model that learns "this cat -> this label" looks good only on seen cats
        r, _ = _synthetic_result("identity")
        d = r["decisions"]
        self.assertEqual(d["R4_seen_to_unseen"]["motion_lr"], "identity-dependent")
        self.assertNotEqual(d["R2_unseen_cats"]["motion_lr"], "above chance on unseen cats")
        cl = r["evaluation"]["methods"]["motion_lr--clip_disjoint"]
        ca = r["evaluation"]["methods"]["motion_lr--cat_disjoint"]
        self.assertGreater(cl["balanced_accuracy"] - ca["balanced_accuracy"], 0.2)
        self.assertEqual(ca["cat_seen_in_training"], 0.0)
        # the cross-validated majority baseline falls below chance here, so "gain over majority"
        # would pass; R2 is judged against chance for that reason
        self.assertLess(r["evaluation"]["methods"]["majority--cat_disjoint"]["balanced_accuracy"], 0.15)

    def test_too_few_cats_is_not_run(self):
        d = synthetic.make(n_cats=6, clips_per_cat=3, mode="signal", seed=2)
        segs = d["segments"]
        X = np.stack([baselines.motion_features(d["frames"][s]) for s in segs])
        runs = baselines.run(segs, X, [d["truth"][s] for s in segs], d["clip_of"], d["cat_of"])
        r = score.score({"a": dict(d["truth"]), "b": dict(d["truth"])}, d["key"], _preds(runs), reps=100)
        self.assertFalse(r["decisions"]["R0_preconditions"]["met"])
        self.assertEqual(r["decisions"]["R2_unseen_cats"]["motion_lr"], "not assessed")
        self.assertTrue(r["decisions"]["outcome"].startswith("not run"))
        self.assertIn("BH1 results", score.render(r))


class FeatureTests(unittest.TestCase):
    def test_still_video_has_zero_motion(self):
        f = baselines.motion_features(np.full((8, 20, 30), 0.3))
        self.assertEqual(len(f), len(baselines.FEATURE_NAMES))
        self.assertTrue(np.all(np.isfinite(f)))
        self.assertEqual(f[0], 0.0)

    def test_cross_validation_regimes(self):
        X = np.random.default_rng(0).normal(size=(40, 3))
        y = [CLASSES[i % 2] for i in range(40)]
        clips = [f"k{i // 2}" for i in range(40)]
        cats = [f"c{i // 8}" for i in range(40)]
        cat_rows = baselines.cross_validate(X, y, cats, cats, "majority")
        self.assertTrue(all(r["cat_seen_in_training"] == 0 for r in cat_rows))
        clip_rows = baselines.cross_validate(X, y, clips, cats, "motion_lr")
        for i, r in enumerate(clip_rows):
            fold_of_clip = {clips[j]: clip_rows[j]["fold"] for j in range(40)}
            self.assertEqual(fold_of_clip[clips[i]], r["fold"])
            seen = any(cats[j] == cats[i] and clip_rows[j]["fold"] != r["fold"] for j in range(40))
            self.assertEqual(r["cat_seen_in_training"], int(seen))
        self.assertTrue(all(r["pred"] in CLASSES for r in clip_rows))


class PackageTests(unittest.TestCase):
    def _build(self, tmp: Path):
        selected = [{"title": f"File:Cat grooming {i}.webm", "uploader": f"u{i}", "licence": "CC BY 4.0", "duration_s": 5.0 + 3 * i} for i in range(3)]
        identity = {s["title"]: {"cat_id": f"cat{i}", "target_description": "the grey cat", "identity_confidence": "sure", "n_cats_visible": "1", "checker": "x"}
                    for i, s in enumerate(selected)}

        def frames(title):
            return [(k / 4, Image.new("RGB", (64, 48), (k * 3 % 255, 80, 120))) for k in range(80)]

        salt = "ab" * 32
        c = build.build_package(selected, identity, frames, salt, package_dir=tmp / "package", work=tmp / "work")
        return selected, c, salt

    def test_package_is_blind_and_committed(self):
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            selected, c, salt = self._build(tmp)
            rows = read_csv(tmp / "package" / "label-TEMPLATE.csv")
            self.assertEqual(len(rows), sum(n_segments(s["duration_s"]) for s in selected))
            self.assertEqual(c["n_segments"], len(rows))
            public = "".join(p.read_text(encoding="utf-8") for p in (tmp / "package").glob("*.*"))
            self.assertNotIn("grooming", public)
            self.assertNotIn(salt, public)
            manifest = json.loads((tmp / "work" / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(build.manifest_root(manifest), c["root_sha256"])
            self.assertEqual(set(json.loads((tmp / "package" / "commitment.json").read_text(encoding="utf-8"))), wh.COMMITMENT_KEYS)
            with Image.open(tmp / "work" / "package" / "sheets" / rows[0]["sheet"]) as sheet:
                self.assertGreater(sheet.width, FRAMES_PER_SEGMENT * build.TILE_WIDTH)
            key, tpl = tmp / "work" / "key.json", tmp / "package" / "label-TEMPLATE.csv"
            self.assertEqual(wh.verify_release(manifest, c, key, tpl), [])
            key.write_text(key.read_text(encoding="utf-8").replace("cat0", "cat1"), encoding="utf-8")
            self.assertTrue(wh.verify_release(manifest, c, key, tpl))

    def test_opaque_order_depends_on_salt(self):
        titles = [f"t{i}" for i in range(30)]
        self.assertNotEqual(build.opaque_order(titles, "a" * 64), build.opaque_order(titles, "b" * 64))
        self.assertEqual(build.opaque_order(titles, "a" * 64), build.opaque_order(list(reversed(titles)), "a" * 64))

    def test_identity_must_be_complete(self):
        good = {"title": "t", "cat_id": "c1", "target_description": "grey", "identity_confidence": "sure", "n_cats_visible": "1", "checker": "x"}
        self.assertIn("t", build.validate_identity([good], ["t"]))
        for bad in ({**good, "cat_id": ""}, {**good, "checker": ""}, {**good, "identity_confidence": "maybe"}, {**good, "n_cats_visible": "two"}):
            with self.assertRaises(ValueError):
                build.validate_identity([bad], ["t"])
        with self.assertRaises(ValueError):
            build.validate_identity([good], ["t", "u"])


class WithholdingTests(unittest.TestCase):
    def _check(self, files: dict[str, str], private=None):
        return wh.check(list(files), lambda p: files[p].encode(), private)

    def _base(self, locks=None, roster=("ann", "bo")):
        return {wh.COMMITMENT: json.dumps({k: 1 for k in wh.COMMITMENT_KEYS}), wh.ROSTER: json.dumps({"labellers": list(roster)}),
                wh.LOCKS: json.dumps(locks or {})}

    def test_key_is_private_until_every_labeller_locked(self):
        files = {**self._base({"labels/labels-ann.csv": "x"}), "behaviour/key.json": "{}"}
        self.assertTrue(self._check(files))
        files[wh.LOCKS] = json.dumps({"labels/labels-ann.csv": "x", "labels/labels-bo-r2.csv": "y"})
        self.assertEqual(self._check(files), [])

    def test_one_labeller_is_never_enough(self):
        files = {**self._base({"labels/labels-ann.csv": "x"}, roster=("ann",)), "behaviour/results.md": ""}
        self.assertTrue(self._check(files))

    def test_other_leaks(self):
        self.assertTrue(self._check({**self._base(), "behaviour/work/key.json": "{}"}))
        self.assertTrue(self._check({**self._base(), "behaviour/predictions/m--cat_disjoint.csv": ""}))
        self.assertTrue(self._check({**self._base(), wh.COMMITMENT: json.dumps({"root_sha256": "x", "titles": []})}))
        self.assertTrue(self._check({**self._base({"labels/labels-eve.csv": "x"})}))
        private = {"salt": "f" * 64, "titles": {"BH1-C001": "Cat licking tail.ogv"}}
        self.assertTrue(self._check({**self._base(), "notes.md": "salt " + "f" * 64}, private))
        self.assertTrue(self._check({**self._base(), "notes.md": "BH1-C001 is Cat licking tail.ogv"}, private))
        self.assertEqual(self._check({**self._base(), "notes.md": "BH1-C001 only"}, private), [])

    def test_repository_tree_withholds(self):
        self.assertEqual(wh.check_repo(), [])


if __name__ == "__main__":
    unittest.main()
