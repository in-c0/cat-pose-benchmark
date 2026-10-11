"""Score HR1: reviewer agreement, human consensus truth, and v1/v3 against it.

Inputs (one file per reviewer; the file stem is the reviewer id):

    review/hr1/submissions/stage_a/<reviewer>.csv
    review/hr1/submissions/stage_b/<reviewer>.csv
    review/hr1/key.json        (published with Stage B, after every Stage A is locked)

Everything the analysis does was written down in review/hr1/README.md before any label
existed. In short:

* agreement: Krippendorff's alpha (nominal) over all reviewers and Cohen's kappa per pair,
  on Stage A (positive / negative / cannot_tell) and Stage B (on_tail / not_on_tail /
  cannot_tell);
* human truth per frame is unanimous or it is ``uncertain`` — a disagreement is never
  resolved toward either reviewer, or toward the model;
* a method's assertion is judged by the unanimous Stage B verdict on its curve;
* precision / recall use the same definitions as ``review/score_truth.py``, with a clip-level
  bootstrap interval, and are set next to the model-truth numbers (as frozen and
  adjudicated) from ``review/truth/methods/aggregate.json``.

    python -m review.hr1.score --output-md review/hr1/results.md --output-json review/hr1/results.json
"""

from __future__ import annotations

import argparse
import hashlib
import csv
import json
import random
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from review.hr1.agreement import krippendorff_alpha_nominal, pairwise
from review.score_truth import TRUTH, frame_class, load_overrides, load_truth

HERE = Path(__file__).resolve().parent
SUBMISSIONS = HERE / "submissions"

STAGE_A_VALUES = {"visible", "partial", "not_visible", "cannot_tell"}
STAGE_B_VALUES = {"on_tail", "not_on_tail", "cannot_tell"}
COLLAPSE_A = {"visible": "positive", "partial": "positive", "not_visible": "negative", "cannot_tell": "cannot_tell"}
SET_TRUTH = {"holdout1": "holdout_frames.csv", "holdout2": "holdout2_frames.csv"}
SET_TAG = {"holdout1": "+holdout", "holdout2": "+holdout2"}
RELIABLE, TENTATIVE = 0.80, 0.667
SEED, REPS = 20261011, 10000


def _read(path: Path, id_cols: tuple[str, ...], value_col: str, allowed: set[str]) -> dict[Any, str]:
    out: dict[Any, str] = {}
    errors = []
    with path.open(newline="", encoding="utf-8-sig") as h:
        for line, row in enumerate(csv.DictReader(h), start=2):
            v = (row.get(value_col) or "").strip().lower()
            key = tuple(int(row[c]) if c == "frame_index" else row[c].strip() for c in id_cols)
            key = key[0] if len(key) == 1 else key
            if not v:
                errors.append(f"line {line}: {value_col} is blank (use cannot_tell)")
                continue
            if v not in allowed:
                errors.append(f"line {line}: {v!r} not in {sorted(allowed)}")
                continue
            if key in out:
                errors.append(f"line {line}: duplicate {key}")
            out[key] = v
    if errors:
        raise ValueError(f"{path}: " + "; ".join(errors[:10]) + (" ..." if len(errors) > 10 else ""))
    return out


def load_stage_a(path: Path) -> dict[tuple[str, int], str]:
    return _read(path, ("clip_id", "frame_index"), "tail", STAGE_A_VALUES)


def load_stage_b(path: Path) -> dict[str, str]:
    return _read(path, ("item_id",), "on_tail", STAGE_B_VALUES)


def unanimous(labels: list[str]) -> str:
    return labels[0] if labels and all(x == labels[0] for x in labels) else "uncertain"


def _band(alpha: float | None) -> str:
    if alpha is None:
        return "undefined"
    return "reliable" if alpha >= RELIABLE else ("tentative" if alpha >= TENTATIVE else "unreliable")


def _pr(c: dict[str, int]) -> tuple[float | None, float | None]:
    a = c["TP"] + c["FPv"] + c["FPn"]
    v = c["TP"] + c["FPv"] + c["FN"]
    return (c["TP"] / a if a else None, c["TP"] / v if v else None)


def _bootstrap(per_clip: dict[str, dict[str, int]], rng: random.Random) -> dict[str, Any]:
    clips = list(per_clip.values())
    ps, rs = [], []
    for _ in range(REPS):
        s = [rng.choice(clips) for _ in clips]
        tot = {k: sum(c[k] for c in s) for k in ("TP", "FPv", "FN", "FPn")}
        p, r = _pr(tot)
        if p is not None:
            ps.append(p)
        if r is not None:
            rs.append(r)
    ci = lambda xs: (round(sorted(xs)[int(0.025 * len(xs))], 3), round(sorted(xs)[int(0.975 * len(xs)) - 1], 3)) if xs else None
    return {"precision_ci": ci(ps), "recall_ci": ci(rs)}


def judge_method(key: dict, method: str, truth_a: dict[tuple[str, int], str], truth_b: dict[str, str]) -> tuple[dict, list]:
    """Per-set, per-clip confusion counts for one method against human consensus."""
    counts: dict[str, dict[str, Counter]] = defaultdict(lambda: defaultdict(Counter))
    rows = []
    for f in key["frames"]:
        clip, idx, s = f["clip_id"], f["frame_index"], f["set"]
        rec = f["methods"][method]
        h = truth_a.get((clip, idx), "uncertain")
        c = counts[s][clip]
        if h in ("uncertain", "cannot_tell"):
            outcome = "excluded_frame"
        elif not rec["asserted"]:
            outcome = "FN" if h == "positive" else "TN"
        else:
            b = truth_b.get(rec.get("item_id") or "", "uncertain")
            if b in ("uncertain", "cannot_tell"):
                outcome = "excluded_assertion"
            elif h == "positive":
                outcome = "TP" if b == "on_tail" else "FPv"
            else:
                # the tail was judged hidden in Stage A; a line judged on a tail in Stage B
                # contradicts that and is excluded and listed, never counted as correct
                outcome = "conflict" if b == "on_tail" else "FPn"
        c[outcome] += 1
        rows.append({"set": s, "clip_id": clip, "frame_index": idx, "method": method, "human_frame": h,
                     "item_id": rec.get("item_id"), "outcome": outcome})
    return counts, rows


def score(stage_a_paths: list[Path], stage_b_paths: list[Path], key_path: Path | None) -> dict[str, Any]:
    a_raw = {p.stem: load_stage_a(p) for p in stage_a_paths}
    a_col = {r: {k: COLLAPSE_A[v] for k, v in labels.items()} for r, labels in a_raw.items()}
    result: dict[str, Any] = {"reviewers_stage_a": sorted(a_raw), "thresholds": {"reliable": RELIABLE, "tentative": TENTATIVE}}
    alpha_a = krippendorff_alpha_nominal(a_col)
    result["stage_a"] = {
        "alpha": None if alpha_a is None else round(alpha_a, 3), "band": _band(alpha_a),
        "alpha_raw_four_labels": (lambda x: None if x is None else round(x, 3))(krippendorff_alpha_nominal(a_raw)),
        "pairs": pairwise(a_col),
        "label_counts": {r: dict(Counter(v.values())) for r, v in a_raw.items()},
    }
    frames = sorted(set().union(*[set(v) for v in a_col.values()])) if a_col else []
    truth_a = {k: unanimous([a_col[r][k] for r in a_col if k in a_col[r]]) if sum(k in a_col[r] for r in a_col) == len(a_col) else "uncertain" for k in frames}
    result["stage_a"]["consensus_counts"] = dict(Counter(truth_a.values()))
    result["stage_a"]["disagreements"] = [{"clip_id": k[0], "frame_index": k[1], **{r: a_raw[r].get(k) for r in a_raw}} for k in frames if truth_a[k] == "uncertain"]

    # human consensus vs the model annotator's frozen truth (as frozen, before any amendment
    # is not recoverable for holdout2 f012-f014; the committed truth file is used)
    model = {}
    for s, f in SET_TRUTH.items():
        for k, t in load_truth(f).items():
            model[k] = {"visible": "positive", "not_visible": "negative", "ambiguous": "cannot_tell"}[frame_class(t)]
    shared = {k: v for k, v in truth_a.items() if k in model and v != "uncertain"}
    vs_model = pairwise({"human_consensus": shared, "model_truth": {k: model[k] for k in shared}})[0]
    confusion = Counter((truth_a[k], model[k]) for k in truth_a if k in model)
    result["human_vs_model_truth"] = {**vs_model, "confusion_human_x_model": {f"{h}|{m}": n for (h, m), n in sorted(confusion.items())},
                                      "per_reviewer_kappa": {r: pairwise({r: a_col[r], "model_truth": {k: model[k] for k in a_col[r] if k in model}})[0]["cohen_kappa"] for r in a_col}}

    if not stage_b_paths or key_path is None:
        result["stage_b"] = "not yet collected"
        return result

    key = json.loads(key_path.read_text(encoding="utf-8"))
    b_raw = {p.stem: load_stage_b(p) for p in stage_b_paths}
    repeat_of = key["repeat_of"]
    # self-consistency on the repeated items, then drop repeats from everything else
    self_consistency = {}
    for r, labels in b_raw.items():
        pairs = [(labels.get(rep), labels.get(orig)) for rep, orig in repeat_of.items() if rep in labels and orig in labels]
        self_consistency[r] = {"n": len(pairs), "same": sum(1 for x, y in pairs if x == y)}
    b = {r: {k: v for k, v in labels.items() if k not in repeat_of} for r, labels in b_raw.items()}
    alpha_b = krippendorff_alpha_nominal(b)
    items = sorted(key["items"])
    truth_b = {i: unanimous([b[r][i] for r in b if i in b[r]]) if sum(i in b[r] for r in b) == len(b) else "uncertain" for i in items}
    result["stage_b"] = {
        "reviewers": sorted(b), "alpha": None if alpha_b is None else round(alpha_b, 3), "band": _band(alpha_b),
        "pairs": pairwise(b), "self_consistency": self_consistency,
        "consensus_counts": dict(Counter(truth_b.values())),
        "disagreements": [{"item_id": i, **key["items"][i], **{r: b[r].get(i) for r in b}} for i in items if truth_b[i] == "uncertain"],
    }

    agg = json.loads((TRUTH / "methods" / "aggregate.json").read_text(encoding="utf-8"))
    rng = random.Random(SEED)
    result["methods"] = {}
    all_rows = []
    for method in key["methods"]:
        counts, rows = judge_method(key, method, truth_a, truth_b)
        all_rows += rows
        result["methods"][method] = {}
        pooled_clips: dict[str, dict[str, int]] = {}
        for s in list(SET_TRUTH) + ["holdouts_pooled"]:
            per_clip = {clip: {k: c.get(k, 0) for k in ("TP", "FPv", "FN", "FPn", "TN", "excluded_frame", "excluded_assertion", "conflict")}
                        for clip, c in counts[s].items()} if s != "holdouts_pooled" else pooled_clips
            if s != "holdouts_pooled":
                pooled_clips.update(per_clip)
            tot = {k: sum(c[k] for c in per_clip.values()) for k in ("TP", "FPv", "FN", "FPn", "TN", "excluded_frame", "excluded_assertion", "conflict")}
            p, r = _pr(tot)
            entry = {**tot, "precision": None if p is None else round(p, 3), "recall": None if r is None else round(r, 3), **_bootstrap(per_clip, rng)}
            if s in SET_TRUTH:
                model_block = agg[s][method]
                entry["model_truth"] = {m: {"precision": model_block[m]["pooled"]["precision"], "recall": model_block[m]["pooled"]["recall"]} for m in ("as_frozen", "adjudicated")}
            result["methods"][method][s] = entry

    # which post-inference overrides do the humans uphold?
    overrides = load_overrides()
    by_frame = {(r["clip_id"], r["frame_index"], r["method"]): r["outcome"] for r in all_rows}
    upheld = Counter()
    for (clip, idx, tag), ov in overrides.items():
        for s, suffix in SET_TAG.items():
            if tag.endswith(suffix) and tag.removesuffix(suffix) in key["methods"]:
                outcome = by_frame.get((clip, idx, tag.removesuffix(suffix)))
                if outcome in (None, "excluded_frame", "excluded_assertion", "conflict"):
                    upheld["unresolved"] += 1
                elif (ov["output_status"] in ("correct", "partial")) == (outcome == "TP"):
                    upheld["upheld"] += 1
                else:
                    upheld["overturned"] += 1
    result["overrides_vs_humans"] = dict(upheld)
    result["frame_outcomes"] = all_rows
    return result


def render(r: dict[str, Any]) -> str:
    L = ["# HR1 results (generated by `python -m review.hr1.score`; do not edit)", ""]
    sa = r["stage_a"]
    L += [f"Stage A reviewers: {', '.join(r['reviewers_stage_a'])}.", "",
          f"Stage A agreement (positive / negative / cannot_tell): Krippendorff's alpha **{sa['alpha']}** ({sa['band']}); four-label alpha {sa['alpha_raw_four_labels']}.", ""]
    for p in sa["pairs"]:
        L.append(f"- {p['a']} vs {p['b']}: {p['n_agree']}/{p['n_shared']} agree ({p['pct_agree']}%), kappa {p['cohen_kappa']}")
    L += ["", f"Consensus frames: {sa['consensus_counts']}. Disagreements become `uncertain`: {len(sa['disagreements'])}.", ""]
    hv = r["human_vs_model_truth"]
    L += [f"Human consensus vs the model annotator's truth, on frames both decided: {hv['n_agree']}/{hv['n_shared']} agree, kappa {hv['cohen_kappa']}. "
          f"Per reviewer kappa vs model: {hv['per_reviewer_kappa']}.", "", "Confusion (human | model): " + ", ".join(f"{k} {v}" for k, v in hv["confusion_human_x_model"].items()), ""]
    if isinstance(r["stage_b"], str):
        L.append("Stage B: " + r["stage_b"])
        return "\n".join(L) + "\n"
    sb = r["stage_b"]
    L += [f"Stage B agreement (on_tail / not_on_tail / cannot_tell): alpha **{sb['alpha']}** ({sb['band']}).", ""]
    for p in sb["pairs"]:
        L.append(f"- {p['a']} vs {p['b']}: {p['n_agree']}/{p['n_shared']} agree ({p['pct_agree']}%), kappa {p['cohen_kappa']}")
    L += ["", f"Self-consistency on repeated items: {sb['self_consistency']}. Consensus items: {sb['consensus_counts']}.", "",
          "## v1 and v3 against human consensus", "",
          "| method | set | TP | FPv | FN | FPn | TN | excl. frames | excl. assertions | conflicts | P (95% clips) | R (95% clips) | model truth as frozen P/R | adjudicated P/R |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    ci = lambda x: "—" if not x else f"{x[0]:.2f}–{x[1]:.2f}"
    for m, sets in r["methods"].items():
        for s, e in sets.items():
            mt = e.get("model_truth")
            mts = (f"{mt['as_frozen']['precision']}/{mt['as_frozen']['recall']}", f"{mt['adjudicated']['precision']}/{mt['adjudicated']['recall']}") if mt else ("—", "—")
            L.append(f"| {m.removeprefix('tail_grounded_')} | {s} | {e['TP']} | {e['FPv']} | {e['FN']} | {e['FPn']} | {e['TN']} | {e['excluded_frame']} | {e['excluded_assertion']} | {e['conflict']} | "
                     f"{e['precision']} ({ci(e['precision_ci'])}) | {e['recall']} ({ci(e['recall_ci'])}) | {mts[0]} | {mts[1]} |")
    L += ["", f"Post-inference overrides vs human consensus: {r['overrides_vs_humans']}.", ""]
    return "\n".join(L) + "\n"


def check_locks(paths: list[Path], locks: dict[str, str]) -> None:
    """Refuse any submission whose SHA-256 differs from the digest the reviewer posted.

    ``locks`` maps ``<stage>/<file name>`` to the digest copied from the reviewer's issue
    comment (``submissions/locks.json``)."""
    bad = []
    for p in paths:
        name = f"{p.parent.name}/{p.name}"
        want = locks.get(name)
        got = hashlib.sha256(p.read_bytes()).hexdigest()
        if want is None:
            bad.append(f"{name}: no posted digest")
        elif want.lower().replace(" ", "") != got:
            bad.append(f"{name}: digest {got} does not match the posted {want}")
    if bad:
        raise SystemExit("lock check failed: " + "; ".join(bad))


def main() -> None:
    parser = argparse.ArgumentParser(description="Score HR1 submissions.")
    parser.add_argument("--submissions", type=Path, default=SUBMISSIONS)
    parser.add_argument("--key", type=Path, default=HERE / "key.json")
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--output-md", type=Path)
    args = parser.parse_args()
    a = sorted((args.submissions / "stage_a").glob("*.csv"))
    b = sorted((args.submissions / "stage_b").glob("*.csv"))
    if len(a) < 2:
        raise SystemExit(f"HR1 needs at least two independent Stage A submissions; found {len(a)}")
    locks_path = args.submissions / "locks.json"
    check_locks(a + b, json.loads(locks_path.read_text(encoding="utf-8")) if locks_path.exists() else {})
    r = score(a, b, args.key if args.key.exists() else None)
    if args.output_json:
        args.output_json.write_text(json.dumps(r, indent=1) + "\n", encoding="utf-8")
    md = render(r)
    if args.output_md:
        args.output_md.write_text(md, encoding="utf-8")
    print(md)


if __name__ == "__main__":
    main()
