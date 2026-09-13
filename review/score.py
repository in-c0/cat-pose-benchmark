"""Score one or more filled review CSVs.

Per clip, method and part: how often a visible part was judged ok. With two reviewers,
also reports raw agreement so disagreement is kept, not averaged away.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from review.common import CONDITIONS, METHOD_FOR_PART, PARTS, VERDICTS

Key = tuple[str, int, str]  # clip_id, frame_index, part


def load_reviews(path: Path) -> dict[Key, dict[str, str]]:
    rows: dict[Key, dict[str, str]] = {}
    errors = []
    with path.open(newline="", encoding="utf-8") as handle:
        for line_no, row in enumerate(csv.DictReader(handle), start=2):
            verdict = (row.get("verdict") or "").strip()
            if not verdict:
                continue  # unreviewed row
            part = row["part"].strip()
            condition = (row.get("condition") or "none").strip() or "none"
            if part not in PARTS:
                errors.append(f"line {line_no}: unknown part {part!r}")
            if verdict not in VERDICTS:
                errors.append(f"line {line_no}: verdict {verdict!r} not in {VERDICTS}")
            if condition not in CONDITIONS:
                errors.append(f"line {line_no}: condition {condition!r} not in {CONDITIONS}")
            key = (row["clip_id"].strip(), int(row["frame_index"]), part)
            if key in rows:
                errors.append(f"line {line_no}: duplicate row for {key}")
            rows[key] = {"verdict": verdict, "condition": condition, "note": (row.get("note") or "").strip()}
    if errors:
        raise ValueError(f"{path}: " + "; ".join(errors[:10]) + (" ..." if len(errors) > 10 else ""))
    return rows


def _tally(reviews: dict[Key, dict[str, str]]) -> dict[str, Any]:
    by_group: dict[tuple[str, str, str], Counter] = defaultdict(Counter)
    by_condition: dict[tuple[str, str], Counter] = defaultdict(Counter)
    failures: list[dict[str, Any]] = []
    for (clip_id, frame_index, part), row in sorted(reviews.items()):
        method = METHOD_FOR_PART[part]
        by_group[(clip_id, method, part)][row["verdict"]] += 1
        if row["verdict"] == "wrong":
            by_condition[(method, part)][row["condition"]] += 1
            failures.append(
                {
                    "clip_id": clip_id,
                    "frame_index": frame_index,
                    "part": part,
                    "condition": row["condition"],
                    "note": row["note"],
                }
            )

    groups = []
    for (clip_id, method, part), counts in sorted(by_group.items()):
        visible = counts["ok"] + counts["wrong"]
        groups.append(
            {
                "clip_id": clip_id,
                "method": method,
                "part": part,
                "n_reviewed": sum(counts.values()),
                "n_visible": visible,
                "n_ok": counts["ok"],
                "n_wrong": counts["wrong"],
                "n_not_visible": counts["not_visible"],
                "pct_ok_of_visible": round(100.0 * counts["ok"] / visible, 1) if visible else None,
            }
        )

    totals = []
    per_method_part: dict[tuple[str, str], Counter] = defaultdict(Counter)
    for g in groups:
        c = per_method_part[(g["method"], g["part"])]
        c["ok"] += g["n_ok"]
        c["wrong"] += g["n_wrong"]
        c["not_visible"] += g["n_not_visible"]
    for (method, part), c in sorted(per_method_part.items()):
        visible = c["ok"] + c["wrong"]
        totals.append(
            {
                "method": method,
                "part": part,
                "n_visible": visible,
                "n_ok": c["ok"],
                "n_wrong": c["wrong"],
                "n_not_visible": c["not_visible"],
                "pct_ok_of_visible": round(100.0 * c["ok"] / visible, 1) if visible else None,
                "wrong_by_condition": dict(sorted(by_condition[(method, part)].items())),
            }
        )
    return {"per_clip": groups, "totals": totals, "failures": failures}


def _agreement(a: dict[Key, dict[str, str]], b: dict[Key, dict[str, str]]) -> dict[str, Any]:
    shared = sorted(set(a) & set(b))
    agree = sum(1 for k in shared if a[k]["verdict"] == b[k]["verdict"])
    disagreements = [
        {"clip_id": k[0], "frame_index": k[1], "part": k[2], "a": a[k]["verdict"], "b": b[k]["verdict"]}
        for k in shared
        if a[k]["verdict"] != b[k]["verdict"]
    ]
    return {
        "n_shared": len(shared),
        "n_agree": agree,
        "pct_agree": round(100.0 * agree / len(shared), 1) if shared else None,
        "disagreements": disagreements,
    }


def score(paths: list[Path]) -> dict[str, Any]:
    reviewers = {p.stem: load_reviews(p) for p in paths}
    result: dict[str, Any] = {
        "schema_version": "0.1.0",
        "evidence_tier": "G3-verdict",
        "reviewers": {name: _tally(rows) for name, rows in reviewers.items()},
    }
    names = list(reviewers)
    if len(names) == 2:
        result["agreement"] = _agreement(reviewers[names[0]], reviewers[names[1]])
    return result


def render_markdown(result: dict[str, Any]) -> str:
    lines = ["# Frame review scores", ""]
    for name, tally in result["reviewers"].items():
        lines += [f"## Reviewer `{name}`", "", "| method | part | visible | ok | wrong | not visible | % ok of visible | wrong by condition |", "|---|---|---|---|---|---|---|---|"]
        for t in tally["totals"]:
            pct = "—" if t["pct_ok_of_visible"] is None else f"{t['pct_ok_of_visible']:.1f}"
            cond = ", ".join(f"{k} {v}" for k, v in t["wrong_by_condition"].items()) or "—"
            lines.append(
                f"| {t['method']} | {t['part']} | {t['n_visible']} | {t['n_ok']} | {t['n_wrong']} | {t['n_not_visible']} | {pct} | {cond} |"
            )
        lines += ["", "### Per clip", "", "| clip | method | part | visible | ok | wrong | % ok |", "|---|---|---|---|---|---|---|"]
        for g in tally["per_clip"]:
            pct = "—" if g["pct_ok_of_visible"] is None else f"{g['pct_ok_of_visible']:.1f}"
            lines.append(f"| {g['clip_id']} | {g['method']} | {g['part']} | {g['n_visible']} | {g['n_ok']} | {g['n_wrong']} | {pct} |")
        if tally["failures"]:
            lines += ["", "### Frames judged wrong", ""]
            for f in tally["failures"]:
                note = f" — {f['note']}" if f["note"] else ""
                lines.append(f"- {f['clip_id']} f{f['frame_index']:03d} {f['part']} ({f['condition']}){note}")
        lines.append("")
    if "agreement" in result:
        a = result["agreement"]
        lines += [
            "## Reviewer agreement",
            "",
            f"{a['n_agree']}/{a['n_shared']} shared verdicts agree ({a['pct_agree']}%).",
            "",
        ]
        for d in a["disagreements"]:
            lines.append(f"- {d['clip_id']} f{d['frame_index']:03d} {d['part']}: {d['a']} vs {d['b']}")
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Score filled review CSVs.")
    parser.add_argument("reviews", nargs="+", type=Path, help="One CSV per reviewer; the file stem is the reviewer id.")
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--output-md", type=Path)
    args = parser.parse_args()

    result = score(args.reviews)
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown = render_markdown(result)
    if args.output_md:
        args.output_md.parent.mkdir(parents=True, exist_ok=True)
        args.output_md.write_text(markdown, encoding="utf-8")
    print(markdown)


if __name__ == "__main__":
    main()
