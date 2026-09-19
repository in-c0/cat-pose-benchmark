"""Score tail methods against frame truth v1 (review/truth/frames.csv).

Derives one method-judgement row per frame (layer 2) from the method's result.json and
the truth reference boxes, applies hand overrides from review/truth/methods/overrides.csv,
writes review/truth/methods/<method>.csv, and prints the confusion counts:

  TP  a tail is visible/partial, method asserted a tail on one of the annotated tails
  FPv a tail is visible/partial, method asserted a tail elsewhere (wrong_part)
  FN  a tail is visible/partial, method produced nothing
  FPn no annotated tail is visible, method asserted a tail
  TN  no annotated tail is visible, method produced nothing
  frames whose only unmatched annotated tail is ``uncertain`` are excluded.

Precision = TP / (TP + FPv + FPn); recall = TP / (TP + FPv + FN).

Truth v1.1 (pass 8) is instance-complete: a frame may carry a second cat's tail
(``alt_*`` columns). The primary metric is instance-agnostic, so an output on ANY
annotated tail is a TP. The association-aware count ``assoc_mismatch`` reports the TPs
that matched the *other* cat's tail while the method's cat box was on the target cat.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from detail.grounded_tail import _iou
from review.common import clip_workdir, load_clips

TRUTH = Path(__file__).resolve().parent / "truth"
IOU_MIN = 0.3


def load_truth() -> dict[tuple[str, int], dict[str, Any]]:
    rows = {}
    with (TRUTH / "frames.csv").open(encoding="utf-8") as h:
        lines = [l for l in h if not l.startswith("#")]
    for r in csv.DictReader(lines):
        ref = [float(v) for v in r["reference_box"].split()] if r["reference_box"] else None
        alt = [float(v) for v in r["alt_reference_box"].split()] if r.get("alt_reference_box") else None
        rows[(r["clip_id"], int(r["frame_index"]))] = {**r, "frame_index": int(r["frame_index"]), "ref": ref, "alt": alt, "alt_vis": r.get("alt_tail_visibility", "")}
    return rows


def load_overrides() -> dict[tuple[str, int, str], dict[str, str]]:
    path = TRUTH / "methods" / "overrides.csv"
    out = {}
    if path.exists():
        with path.open(encoding="utf-8") as h:
            for r in csv.DictReader(h):
                out[(r["clip_id"], int(r["frame_index"]), r["method"])] = r
    return out


def _box_of(frame: dict[str, Any]) -> list[float] | None:
    tail = frame.get("tail")
    if tail and tail.get("box"):
        return tail["box"]
    curve = frame.get("curve")
    if curve and curve.get("samples"):
        xs = [s["x_px"] for s in curve["samples"]]
        ys = [s["y_px"] for s in curve["samples"]]
        return [min(xs), min(ys), max(xs), max(ys)]
    return None


def _same(box: list[float], ref: list[float]) -> bool:
    """IoU >= 0.3, or the method box is no larger than the reference and 80 % of it lies
    inside the reference (a tight curve box inside a looser detector box). Containment is
    one-way on purpose: a whole-cat box that merely contains the tail is not a tail box
    (found on walking f006/f007 in pass 9)."""
    if _iou(box, ref) >= IOU_MIN:
        return True
    x0, y0 = max(box[0], ref[0]), max(box[1], ref[1])
    x1, y1 = min(box[2], ref[2]), min(box[3], ref[3])
    inter = max(0.0, x1 - x0) * max(0.0, y1 - y0)
    area_box = (box[2] - box[0]) * (box[3] - box[1])
    area_ref = (ref[2] - ref[0]) * (ref[3] - ref[1])
    return 0 < area_box <= area_ref and inter / area_box >= 0.8


def frame_class(t: dict[str, Any]) -> str:
    """'visible' if any annotated tail is visible/partial, 'not_visible' if none is and none
    is uncertain, else 'uncertain'."""
    vis = {t["tail_visibility"], t.get("alt_vis", "")} - {""}
    if vis & {"visible", "partial"}:
        return "visible"
    if "uncertain" in vis:
        return "uncertain"
    return "not_visible"


def judge(method: str, run_clip: str, review_clip: str, factor: int, truth: dict, overrides: dict, tag: str | None = None) -> list[dict[str, Any]]:
    tag = tag or method
    result = json.loads((clip_workdir(run_clip) / method / "result.json").read_text(encoding="utf-8"))
    frames = {f["frame_index"]: f for f in result["frames"]}
    rows = []
    for (clip, i), t in truth.items():
        if clip != review_clip:
            continue
        f = frames.get(i * factor)
        if f is None:
            continue
        accepted = f["status"] in ("ok", "propagated")
        row = {"clip_id": clip, "frame_index": i, "method": method, "output_status": "", "wrong_part": "", "box_quality": "", "instance": "", "note": ""}
        if not accepted:
            row["output_status"] = "no_output"
            row["note"] = f["status"]
        else:
            box = _box_of(f)
            tv, av = t["tail_visibility"] in ("visible", "partial"), t.get("alt_vis", "") in ("visible", "partial")
            if tv and t["ref"] and box and _same(box, t["ref"]):
                row["output_status"] = "correct"; row["box_quality"] = "usable"; row["instance"] = "target"
            elif av and t["alt"] and box and _same(box, t["alt"]):
                row["output_status"] = "correct"; row["box_quality"] = "usable"; row["instance"] = "alt"; row["note"] = f"on the other cat's tail ({t.get('alt_cat', '')})"
            elif tv and not t["ref"]:
                row["output_status"] = "correct"; row["box_quality"] = "usable"; row["instance"] = "target"; row["note"] = "no reference box; accepted on visibility alone — check by eye"
            else:
                row["output_status"] = "wrong_part"; row["wrong_part"] = "other"; row["note"] = "auto: box does not match any reference (or no tail visible)"
        ov = overrides.get((clip, i, tag))
        if ov:
            for k in ("output_status", "wrong_part", "box_quality", "instance"):
                if ov.get(k):
                    row[k] = ov[k]
            row["note"] = "override: " + ov.get("reason", "")
        rows.append(row)
    return rows


def tally(rows: list[dict[str, Any]], truth: dict) -> dict[str, Any]:
    c = {"TP": 0, "FPv": 0, "FN": 0, "FPn": 0, "TN": 0, "excluded": 0, "TP_partial": 0, "FN_partial": 0, "assoc_mismatch": 0}
    for r in rows:
        t = truth[(r["clip_id"], r["frame_index"])]
        vis = t["tail_visibility"]
        s = r["output_status"]
        fc = frame_class(t)
        if fc == "uncertain":
            c["excluded"] += 1
        elif fc == "visible":
            if s in ("correct", "partial"):
                c["TP"] += 1
                if vis == "partial" and r.get("instance") != "alt":
                    c["TP_partial"] += 1
                if r.get("instance") == "alt":
                    c["assoc_mismatch"] += 1
            elif s == "no_output":
                c["FN"] += 1
                if vis == "partial":
                    c["FN_partial"] += 1
            else:
                c["FPv"] += 1
        else:
            if s == "no_output":
                c["TN"] += 1
            else:
                c["FPn"] += 1
    asserted = c["TP"] + c["FPv"] + c["FPn"]
    visible = c["TP"] + c["FPv"] + c["FN"]
    c["precision"] = round(c["TP"] / asserted, 3) if asserted else None
    c["recall"] = round(c["TP"] / visible, 3) if visible else None
    return c


def main() -> None:
    parser = argparse.ArgumentParser(description="Score a tail method against frame truth v1.")
    parser.add_argument("method")
    parser.add_argument("--dense", action="store_true")
    parser.add_argument("--tag", help="name for the methods/<tag>.csv output (default: method[+dense])")
    args = parser.parse_args()
    truth = load_truth()
    overrides = load_overrides()
    clips = load_clips()
    dense_for = {c["dense_of"]: c for c in clips if c.get("dense_of") and c.get("dense_factor")}
    tag = args.tag or (args.method + ("+dense" if args.dense else ""))
    all_rows: list[dict[str, Any]] = []
    per_clip = {}
    for review_clip in sorted({k[0] for k in truth}):
        if args.dense:
            d = dense_for.get(review_clip)
            if not d:
                continue
            rows = judge(args.method, d["clip_id"], review_clip, int(d["dense_factor"]), truth, overrides, tag)
        else:
            rows = judge(args.method, review_clip, review_clip, 1, truth, overrides, tag)
        all_rows += rows
        per_clip[review_clip] = tally(rows, truth)
    out = TRUTH / "methods" / f"{tag}.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as h:
        w = csv.DictWriter(h, fieldnames=["clip_id", "frame_index", "method", "output_status", "wrong_part", "box_quality", "instance", "note"])
        w.writeheader(); w.writerows(all_rows)
    total = tally(all_rows, truth)
    for clip, c in per_clip.items():
        print(f"{clip}: TP {c['TP']} FPv {c['FPv']} FN {c['FN']} FPn {c['FPn']} TN {c['TN']} excl {c['excluded']}  P {c['precision']} R {c['recall']}")
    print(f"TOTAL {tag}: TP {total['TP']} FPv {total['FPv']} FN {total['FN']} FPn {total['FPn']} TN {total['TN']} excl {total['excluded']}  P {total['precision']} R {total['recall']}  (partial: TP {total['TP_partial']} FN {total['FN_partial']}; assoc_mismatch {total['assoc_mismatch']})")
    wrongs = [r for r in all_rows if r["output_status"] not in ("correct", "no_output", "partial")]
    fns = [r for r in all_rows if r["output_status"] == "no_output" and frame_class(truth[(r["clip_id"], r["frame_index"])]) == "visible"]
    print("  asserted-wrong:", [f"{r['clip_id'][8:14]} f{r['frame_index']:03d}" for r in wrongs])
    print("  missed:", [f"{r['clip_id'][8:14]} f{r['frame_index']:03d}" for r in fns])


if __name__ == "__main__":
    main()
