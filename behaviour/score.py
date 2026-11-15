"""Score BH1: labeller agreement, unanimous human truth, and every method's out-of-fold predictions.

Everything here implements behaviour/PROTOCOL.md section 7, written before any label existed.
The tests in test_bh1.py check each rule on synthetic data. Nothing in this repository has been
scored on real labels.

Inputs, all published only after every registered labeller has locked:

    behaviour/submissions/labels/labels-<handle>.csv   one per labeller, digests in locks.json
    behaviour/key.json                                 opaque clip -> Commons title, uploader, cat_id
    behaviour/predictions/<method>--<regime>.csv       from baselines.py, or any candidate method

    python -m behaviour.score --output-md behaviour/results.md --output-json behaviour/results.json
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

from behaviour.common import (ABSTAIN_BELOW, BOOT_REPS, BOOT_SEED, CANNOT_TELL, CLASSES, DROP_MATERIAL, HERE, LABELS, MIN_CATS,
                              MIN_CLIPS, MIN_COVERAGE, MIN_LABELLERS, RELIABLE, SUBMISSIONS, TENTATIVE, read_csv)
from review.hr1.agreement import krippendorff_alpha_nominal, pairwise
from review.hr1.score import check_locks

REGIMES = ("clip_disjoint", "cat_disjoint")
BASELINE = "majority"
REFERENCE = "motion_lr"
K = len(CLASSES)
IDX = {c: i for i, c in enumerate(CLASSES)}


# ---------------------------------------------------------------- labels


def load_labels(path: Path, template_ids: list[str]) -> dict[str, str]:
    """Rule 1: a blank, unknown, duplicate, missing or extra row rejects the whole file. No label is inferred."""
    out: dict[str, str] = {}
    errors = []
    for line, row in enumerate(read_csv(path), start=2):
        sid = (row.get("segment_id") or "").strip()
        v = (row.get("behaviour") or "").strip().lower()
        if not v:
            errors.append(f"line {line}: behaviour is blank (use cannot_tell)")
        elif v not in LABELS:
            errors.append(f"line {line}: {v!r} not in {list(LABELS)}")
        elif sid in out:
            errors.append(f"line {line}: duplicate {sid}")
        else:
            out[sid] = v
    want = set(template_ids)
    if missing := want - set(out):
        errors.append(f"{len(missing)} template segments without a label, e.g. {sorted(missing)[:3]}")
    if extra := set(out) - want:
        errors.append(f"segments not in the template: {sorted(extra)[:3]}")
    if errors:
        raise ValueError(f"{path}: " + "; ".join(errors[:10]) + (" ..." if len(errors) > 10 else ""))
    return out


def latest_per_labeller(paths: list[Path]) -> dict[str, Path]:
    """A correction ``labels-<handle>-r2.csv`` replaces the earlier file for scoring; both stay in the repository."""
    best: dict[str, tuple[int, Path]] = {}
    for p in paths:
        m = re.fullmatch(r"labels-(.+?)(?:-r(\d+))?", p.stem)
        if not m:
            continue
        handle, rev = m.group(1).lower(), int(m.group(2) or 1)
        if handle not in best or rev > best[handle][0]:
            best[handle] = (rev, p)
    return {h: p for h, (_, p) in sorted(best.items())}


def _band(alpha: float | None) -> str:
    if alpha is None:
        return "undefined"
    return "reliable" if alpha >= RELIABLE else ("tentative" if alpha >= TENTATIVE else "unreliable")


def _r(x: float | None, n: int = 3) -> float | None:
    return None if x is None or (isinstance(x, float) and np.isnan(x)) else round(float(x), n)


def agreement(labels: dict[str, dict[str, str]]) -> dict[str, Any]:
    """Rule 2. The band is set by the lower of the six-label alpha and the five-class alpha."""
    a6 = krippendorff_alpha_nominal(labels)
    five = {r: {k: v for k, v in lab.items() if v != CANNOT_TELL} for r, lab in labels.items()}
    a5 = krippendorff_alpha_nominal(five)
    gate = None if a6 is None or a5 is None else min(a6, a5)
    per_class = {}
    for c in CLASSES:
        binary = {r: {k: ("yes" if v == c else "no") for k, v in lab.items()} for r, lab in five.items()}
        per_class[c] = _r(krippendorff_alpha_nominal(binary))
    return {
        "alpha_six_labels": _r(a6), "alpha_five_classes": _r(a5), "alpha_gate": _r(gate), "band": _band(gate),
        "per_class_alpha": per_class,
        "pairs": pairwise(labels),
        "cannot_tell_rate": {r: _r(sum(v == CANNOT_TELL for v in lab.values()) / len(lab)) for r, lab in labels.items()},
        "label_counts": {r: dict(Counter(lab.values())) for r, lab in labels.items()},
    }


def consensus(labels: dict[str, dict[str, str]]) -> dict[str, str]:
    """Rule 3. A segment's truth is the label every labeller gave; any disagreement is ``uncertain``."""
    segs = sorted(set().union(*labels.values())) if labels else []
    out = {}
    for s in segs:
        vals = [lab.get(s) for lab in labels.values()]
        out[s] = vals[0] if all(v == vals[0] for v in vals) and vals[0] is not None else "uncertain"
    return out


# ---------------------------------------------------------------- metrics


def load_predictions(path: Path) -> dict[str, dict[str, Any]]:
    out = {}
    for row in read_csv(path):
        pred = row["pred"].strip()
        if pred not in CLASSES:
            raise ValueError(f"{path}: prediction {pred!r} not in {CLASSES}")
        out[row["segment_id"]] = {"pred": pred, "prob_max": float(row.get("prob_max") or 1.0),
                                  "cat_seen_in_training": row.get("cat_seen_in_training", "")}
    return out


def _confusions(truth: dict[str, str], preds: dict[str, dict[str, Any]], cat_of: dict[str, str], cats: list[str]) -> tuple[np.ndarray, np.ndarray]:
    """Per-cat confusion matrices. Forced choice: (cats, K, K). Selective: (cats, K, K+1), last column abstain."""
    ci = {c: i for i, c in enumerate(cats)}
    forced = np.zeros((len(cats), K, K))
    sel = np.zeros((len(cats), K, K + 1))
    for s, t in truth.items():
        p = preds[s]
        i, j = IDX[t], IDX[p["pred"]]
        forced[ci[cat_of[s]], i, j] += 1
        sel[ci[cat_of[s]], i, K if p["prob_max"] < ABSTAIN_BELOW else j] += 1
    return forced, sel


def metrics_from(conf: np.ndarray) -> dict[str, np.ndarray]:
    """Metrics from confusion matrices of shape (..., K, K), or (..., K, K+1) with an abstain column.

    * ``ba``: balanced accuracy, the mean recall over the classes present in the truth. Any
      predictor that ignores the input, the majority baseline included, has an expected balanced
      accuracy of 1/(classes present), whatever mix of labels it outputs. That makes it the decision
      metric (PROTOCOL.md section 7.5).
    * ``macro_f1``: mean F1 over the classes present in the truth. Reported, not decided on: a
      predictor that spreads its guesses scores about twice the majority baseline by chance.
    * ``f1`` per class, and ``f1_excess``: F1 minus the F1 that a predictor with the same prediction
      rate but no information would get on average, 2pq/(p+q).

    A class absent from the truth has no recall or F1 (nan) and does not enter the means."""
    tp = np.diagonal(conf[..., :K], axis1=-2, axis2=-1)
    pred_tot = conf[..., :K].sum(axis=-2)
    true_tot = conf.sum(axis=-1)
    n = true_tot.sum(axis=-1, keepdims=True)
    present = true_tot > 0
    with np.errstate(invalid="ignore", divide="ignore"):
        recall = np.where(present, tp / true_tot, np.nan)
        f1 = np.where(present, 2 * tp / (pred_tot + true_tot), np.nan)
        p, q = true_tot / n, pred_tot / n
        chance = np.where(present, 2 * p * q / (p + q), np.nan)
        n_present = present.sum(axis=-1)
        ba = np.nansum(np.where(present, recall, 0), axis=-1) / n_present
        macro = np.nansum(np.where(present, f1, 0), axis=-1) / n_present
    return {"ba": ba, "macro_f1": macro, "f1": f1, "f1_excess": f1 - chance}


def prf(conf: np.ndarray) -> dict[str, dict[str, float | None]]:
    tp = np.diagonal(conf[:, :K])
    pred_tot = conf[:, :K].sum(axis=0)
    true_tot = conf.sum(axis=1)
    out = {}
    for c, i in IDX.items():
        p = tp[i] / pred_tot[i] if pred_tot[i] else None
        r = tp[i] / true_tot[i] if true_tot[i] else None
        f = 2 * tp[i] / (pred_tot[i] + true_tot[i]) if true_tot[i] else None
        out[c] = {"precision": _r(p), "recall": _r(r), "f1": _r(f), "support": int(true_tot[i]), "predicted": int(pred_tot[i])}
    return out


def _ci(x: np.ndarray) -> list[float | None]:
    x = x[~np.isnan(x)]
    if not len(x):
        return [None, None]
    lo, hi = np.percentile(x, [2.5, 97.5])
    return [_r(lo), _r(hi)]


def evaluate(truth_all: dict[str, str], preds: dict[str, dict[str, dict[str, Any]]], cat_of: dict[str, str], clip_of: dict[str, str],
             uploader_of: dict[str, str] | None = None, reps: int = BOOT_REPS, seed: int = BOOT_SEED) -> dict[str, Any]:
    """Rules 4-6. ``preds`` maps '<method>--<regime>' to per-segment predictions.

    Intervals resample cats with replacement, taking all of a cat's segments, and keep the
    out-of-fold predictions fixed (no refit). One set of resamples is drawn and reused for every
    method and regime, so gains and drops are paired differences."""
    truth = {s: t for s, t in truth_all.items() if t in CLASSES}
    cats = sorted({cat_of[s] for s in truth})
    for name, p in preds.items():
        if missing := set(truth) - set(p):
            raise ValueError(f"{name}: no prediction for {len(missing)} decided segments, e.g. {sorted(missing)[:3]}")
    rng = np.random.default_rng(seed)
    w = rng.multinomial(len(cats), [1 / len(cats)] * len(cats), size=reps).astype(float) if cats else np.zeros((reps, 0))
    prevalence = Counter(truth.values())
    out: dict[str, Any] = {
        "n_segments_decided": len(truth), "n_cats": len(cats), "n_clips": len({clip_of[s] for s in truth}),
        "truth_counts": {c: prevalence.get(c, 0) for c in CLASSES}, "methods": {},
        # what any predictor that ignores the video scores in expectation (rule R2's reference)
        "chance_balanced_accuracy": _r(1 / len(prevalence)) if prevalence else None,
    }
    boot: dict[str, np.ndarray] = {}
    for name, p in sorted(preds.items()):
        forced, sel = _confusions(truth, p, cat_of, cats)
        mb = metrics_from(np.einsum("rc,cij->rij", w, forced))
        mp = metrics_from(forced.sum(axis=0))
        sel_tot = sel.sum(axis=0)
        coverage = sel_tot[:, :K].sum() / sel_tot.sum() if sel_tot.sum() else None
        seen = [p[s]["cat_seen_in_training"] for s in truth if p[s]["cat_seen_in_training"] in ("0", "1")]
        boot[name] = mb["ba"]
        per_class = prf(forced.sum(axis=0))
        for c, i in IDX.items():
            per_class[c]["f1_ci"] = _ci(mb["f1"][:, i])
            per_class[c]["f1_excess_over_chance"] = _r(mp["f1_excess"][i])
            per_class[c]["f1_excess_ci"] = _ci(mb["f1_excess"][:, i])
            lo = per_class[c]["f1_excess_ci"][0]
            per_class[c]["recognised"] = bool(lo is not None and lo > 0)  # rule R5
        entry = {
            "balanced_accuracy": _r(mp["ba"]), "balanced_accuracy_ci": _ci(mb["ba"]),
            "macro_f1": _r(mp["macro_f1"]), "macro_f1_ci": _ci(mb["macro_f1"]), "per_class": per_class,
            "coverage": _r(coverage),
            "selective_balanced_accuracy": _r(metrics_from(sel_tot[:, :K])["ba"]) if coverage and coverage >= MIN_COVERAGE else None,
            "cat_seen_in_training": _r(sum(x == "1" for x in seen) / len(seen)) if seen else None,
        }
        if uploader_of:
            top = Counter(uploader_of[clip_of[s]] for s in truth).most_common(1)[0][0]
            keep = {s: t for s, t in truth.items() if uploader_of[clip_of[s]] != top}
            if keep:
                f2, _ = _confusions(keep, p, cat_of, sorted({cat_of[s] for s in keep}))
                entry["without_largest_uploader"] = {"uploader": top, "segments": len(keep), "balanced_accuracy": _r(metrics_from(f2.sum(axis=0))["ba"])}
        out["methods"][name] = entry

    def diff(a: str, b: str) -> dict[str, Any]:
        point = out["methods"][a]["balanced_accuracy"] - out["methods"][b]["balanced_accuracy"]
        return {"point": _r(point), "ci": _ci(boot[a] - boot[b])}

    comps = {}
    chance = out["chance_balanced_accuracy"]
    for name in boot:
        method, regime = name.split("--")
        if chance is not None:
            comps[f"{method} - chance ({regime})"] = {"point": _r(out["methods"][name]["balanced_accuracy"] - chance), "ci": _ci(boot[name] - chance)}
        if method != BASELINE and f"{BASELINE}--{regime}" in boot:
            comps[f"{method} - {BASELINE} ({regime})"] = diff(name, f"{BASELINE}--{regime}")
        if method not in (BASELINE, REFERENCE) and f"{REFERENCE}--{regime}" in boot:
            comps[f"{method} - {REFERENCE} ({regime})"] = diff(name, f"{REFERENCE}--{regime}")
        if regime == "clip_disjoint" and f"{method}--cat_disjoint" in boot:
            comps[f"{method}: clip_disjoint - cat_disjoint"] = diff(name, f"{method}--cat_disjoint")
    out["comparisons"] = comps
    return out


# ---------------------------------------------------------------- decision rules


def decide(n_labellers: int, agree: dict[str, Any], ev: dict[str, Any], human: dict[str, Any]) -> dict[str, Any]:
    """PROTOCOL.md section 8, applied mechanically. Text verdicts only; nothing is tuned here."""
    d: dict[str, Any] = {}
    d["R0_preconditions"] = {
        "labellers": n_labellers, "cats": ev["n_cats"], "clips": ev["n_clips"],
        "met": n_labellers >= MIN_LABELLERS and ev["n_cats"] >= MIN_CATS and ev["n_clips"] >= MIN_CLIPS,
    }
    d["R1_labels"] = agree["band"]
    d["R1_unreliable_classes"] = [c for c, a in agree["per_class_alpha"].items() if a is None or a < TENTATIVE]
    usable = d["R0_preconditions"]["met"] and agree["band"] in ("reliable", "tentative")
    comps = ev["comparisons"]
    methods = sorted({n.split("--")[0] for n in ev["methods"]} - {BASELINE})
    r2, r3, r4 = {}, {}, {}
    for m in methods:
        g = comps.get(f"{m} - chance (cat_disjoint)")
        r2[m] = "not assessed" if not usable or g is None else ("above chance on unseen cats" if g["ci"][0] is not None and g["ci"][0] > 0 else "not shown")
        if m != REFERENCE:
            g = comps.get(f"{m} - {REFERENCE} (cat_disjoint)")
            r3[m] = "not assessed" if not usable or g is None else ("adds to motion energy" if g["ci"][0] is not None and g["ci"][0] > 0 else "not shown")
        g = comps.get(f"{m}: clip_disjoint - cat_disjoint")
        seen = ev["methods"].get(f"{m}--clip_disjoint", {}).get("cat_seen_in_training")
        if not usable or g is None:
            r4[m] = "not assessed"
        elif seen is None or seen < 0.5:
            r4[m] = f"not assessed: only {seen} of clip-disjoint test segments have their cat in training"
        else:
            r4[m] = "identity-dependent" if g["point"] >= DROP_MATERIAL and g["ci"][0] is not None and g["ci"][0] > 0 else "no material drop shown"
    d["R2_unseen_cats"], d["R3_beyond_motion"], d["R4_seen_to_unseen"] = r2, r3, r4
    d["R5_recognised_classes"] = {m: [c for c, v in ev["methods"].get(f"{m}--cat_disjoint", {}).get("per_class", {}).items() if v["recognised"]] if usable else "not assessed" for m in methods}
    d["R6_abstention"] = {"human_undecided_fraction": human["undecided_fraction"], "flag": human["undecided_fraction"] is not None and human["undecided_fraction"] > 0.4,
                          "model_coverage": {n: v["coverage"] for n, v in ev["methods"].items()}}
    if not d["R0_preconditions"]["met"]:
        outcome = "not run: preconditions unmet; report counts only"
    elif agree["band"] == "unreliable":
        outcome = "labels unreliable: revise the definitions in PROTOCOL.md section 2, not the method"
    elif not any(v == "above chance on unseen cats" for v in r2.values()):
        outcome = "kill at this scale: no method recognises observable behaviour above chance on unseen cats"
    elif any(r2[m] == "above chance on unseen cats" and r4[m] == "identity-dependent" for m in methods):
        outcome = "pivot: recognition on unseen cats exists but depends materially on having seen the cat"
    else:
        outcome = "continue: recognition above chance on unseen cats without a material seen-to-unseen drop"
    d["outcome"] = outcome + (" (labels tentative)" if agree["band"] == "tentative" and "not run" not in outcome else "")
    return d


def score(labels: dict[str, dict[str, str]], key: dict[str, Any], preds: dict[str, dict[str, dict[str, Any]]], reps: int = BOOT_REPS) -> dict[str, Any]:
    clips = key["clips"]
    clip_of = {s: s.rsplit("-S", 1)[0] for lab in labels.values() for s in lab}
    cat_of = {s: clips[c]["cat_id"] for s, c in clip_of.items()}
    if missing := sorted({c for c in clip_of.values() if not clips.get(c, {}).get("cat_id")}):
        raise ValueError(f"cat_id missing for {missing[:5]}: the identity pass must be complete before scoring")
    agree = agreement(labels)
    truth = consensus(labels)
    counts = Counter(truth.values())
    human = {"consensus_counts": dict(counts), "undecided_fraction": _r((counts["uncertain"] + counts[CANNOT_TELL]) / len(truth)) if truth else None,
             "disagreements": [{"segment_id": s, **{r: lab.get(s) for r, lab in labels.items()}} for s, t in sorted(truth.items()) if t == "uncertain"]}
    ev = evaluate(truth, preds, cat_of, clip_of, {c: v["uploader"] for c, v in clips.items()}, reps=reps)
    sure = {s: t for s, t in truth.items() if clips[clip_of[s]].get("identity_confidence") == "sure"}
    if sure and len(sure) < len(truth):
        ev["identity_sure_only"] = {n: e["balanced_accuracy"] for n, e in evaluate(sure, preds, cat_of, clip_of, reps=1)["methods"].items()}
    return {"labellers": sorted(labels), "agreement": agree, "human_truth": human, "evaluation": ev,
            "decisions": decide(len(labels), agree, ev, human)}


def render(r: dict[str, Any]) -> str:
    a, ev, d = r["agreement"], r["evaluation"], r["decisions"]
    L = ["# BH1 results (generated by `python -m behaviour.score`; do not edit)", "",
         f"Labellers: {', '.join(r['labellers'])}.", "",
         f"Agreement: alpha over six labels {a['alpha_six_labels']}, over five classes {a['alpha_five_classes']}; "
         f"gate {a['alpha_gate']} (**{a['band']}**). Per-class alpha: {a['per_class_alpha']}.", ""]
    for p in a["pairs"]:
        L.append(f"- {p['a']} vs {p['b']}: {p['n_agree']}/{p['n_shared']} agree ({p['pct_agree']}%), kappa {p['cohen_kappa']}")
    L += ["", f"Human truth: {r['human_truth']['consensus_counts']}; undecided fraction {r['human_truth']['undecided_fraction']}.", "",
          f"Decided segments {ev['n_segments_decided']}, cats {ev['n_cats']}, clips {ev['n_clips']}. Truth counts {ev['truth_counts']}.", "",
          "| method | regime | balanced accuracy (95% cats) | macro-F1 (95% cats) | coverage | cat seen in training | " + " | ".join(f"F1 {c}" for c in CLASSES) + " |",
          "|---|---|---|---|---|---|" + "---|" * K]
    ci = lambda x: "—" if not x or x[0] is None else f"{x[0]:.2f}–{x[1]:.2f}"
    for name, m in ev["methods"].items():
        method, regime = name.split("--")
        L.append(f"| {method} | {regime} | {m['balanced_accuracy']} ({ci(m['balanced_accuracy_ci'])}) | {m['macro_f1']} ({ci(m['macro_f1_ci'])}) | {m['coverage']} | {m['cat_seen_in_training']} | "
                 + " | ".join(f"{m['per_class'][c]['f1']} ({ci(m['per_class'][c]['f1_ci'])})" for c in CLASSES) + " |")
    L += ["", f"Chance balanced accuracy: {ev['chance_balanced_accuracy']}. Differences in balanced accuracy (cat bootstrap, paired):", ""]
    L += [f"- {k}: {v['point']} ({ci(v['ci'])})" for k, v in ev["comparisons"].items()]
    L += ["", "## Decisions (PROTOCOL.md section 8)", ""]
    L += [f"- {k}: {v}" for k, v in d.items() if k != "outcome"]
    L += ["", f"**Outcome: {d['outcome']}**", ""]
    return "\n".join(L) + "\n"


def main() -> None:
    from behaviour.withholding import lockers, phase

    p = argparse.ArgumentParser(description="Score BH1 submissions.")
    p.add_argument("--submissions", type=Path, default=SUBMISSIONS)
    p.add_argument("--key", type=Path, default=HERE / "key.json")
    p.add_argument("--predictions", type=Path, default=HERE / "predictions")
    p.add_argument("--output-json", type=Path)
    p.add_argument("--output-md", type=Path)
    a = p.parse_args()
    paths = sorted((a.submissions / "labels").glob("labels-*.csv"))
    locks_path = a.submissions / "locks.json"
    locks = json.loads(locks_path.read_text(encoding="utf-8")) if locks_path.exists() else {}
    roster = json.loads((a.submissions / "labellers.json").read_text(encoding="utf-8"))["labellers"] if (a.submissions / "labellers.json").exists() else []
    if phase(roster, locks) != "locked" or len(lockers(locks)) < MIN_LABELLERS:
        raise SystemExit("BH1 is not locked: every registered labeller (at least two) must have posted a digest")
    check_locks(paths, locks)
    template = [r["segment_id"] for r in read_csv(HERE / "package" / "label-TEMPLATE.csv")]
    labels = {handle: load_labels(pth, template) for handle, pth in latest_per_labeller(paths).items()}
    key = json.loads(a.key.read_text(encoding="utf-8"))
    preds = {pth.stem: load_predictions(pth) for pth in sorted(a.predictions.glob("*--*.csv"))}
    r = score(labels, key, preds)
    if a.output_json:
        a.output_json.write_text(json.dumps(r, indent=1) + "\n", encoding="utf-8")
    md = render(r)
    if a.output_md:
        a.output_md.write_text(md, encoding="utf-8")
    print(md)


if __name__ == "__main__":
    main()
