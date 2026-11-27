"""Independent audit of the tail-method performance claims (HR1, 2026-10-11).

Reads only committed files — ``review/truth/methods/aggregate.json`` (per-clip counts, both
scorings) and ``review/truth/methods/overrides.csv`` — and adds what the notes do not report:

* a 95 % interval for every pooled precision/recall, two ways: Wilson on frames (treats
  frames as independent, which they are not) and a clip-level bootstrap (resamples whole
  clips, which is the honest unit: one clip is one cat, one camera, one scene);
* leave-one-clip-out range, and the share of true positives that come from the single
  largest clip;
* per-clip (per-cat) recall on the prospective holdouts, so cross-cat generalisation is
  visible as a distribution rather than one pooled number;
* the gap between ``as_frozen`` and ``adjudicated`` scoring, and how many hand overrides
  moved a frame toward ``correct`` versus toward a wrong status.

Nothing here is a new measurement. Every number is a function of files that were committed
before this script existed; the truth underneath them is still model-annotated.

    python -m review.claims_audit
"""

from __future__ import annotations

import csv
import json
import math
import random
from collections import Counter
from pathlib import Path
from typing import Any

from review.score_truth import TRUTH

METHODS = ("tail_grounded_v1", "tail_grounded_v3")
SETS = ("dev", "holdout1", "holdout2")
MODES = ("as_frozen", "adjudicated")
SEED = 20261011
REPS = 10000
OUT_JSON = TRUTH / "methods" / "claims_audit.json"
OUT_MD = TRUTH / "methods" / "claims_audit.md"


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float] | None:
    if n == 0:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (round(c - h, 3), round(c + h, 3))


def _pr(clips: list[dict[str, int]]) -> tuple[float | None, float | None]:
    tp = sum(c["TP"] for c in clips)
    asserted = tp + sum(c["FPv"] + c["FPn"] for c in clips)
    visible = tp + sum(c["FPv"] + c["FN"] for c in clips)
    return (tp / asserted if asserted else None, tp / visible if visible else None)


def cluster_bootstrap(per_clip: dict[str, dict[str, int]], rng: random.Random) -> dict[str, Any]:
    clips = list(per_clip.values())
    ps, rs = [], []
    for _ in range(REPS):
        sample = [rng.choice(clips) for _ in clips]
        p, r = _pr(sample)
        if p is not None:
            ps.append(p)
        if r is not None:
            rs.append(r)

    def ci(xs: list[float]) -> tuple[float, float] | None:
        if not xs:
            return None
        xs = sorted(xs)
        return (round(xs[int(0.025 * len(xs))], 3), round(xs[int(0.975 * len(xs)) - 1], 3))

    return {"precision_ci": ci(ps), "recall_ci": ci(rs), "reps": REPS}


def leave_one_out(per_clip: dict[str, dict[str, int]]) -> dict[str, Any]:
    out = {}
    for name in per_clip:
        p, r = _pr([c for k, c in per_clip.items() if k != name])
        out[name] = {"precision": None if p is None else round(p, 3), "recall": None if r is None else round(r, 3)}
    ps = [v["precision"] for v in out.values() if v["precision"] is not None]
    rs = [v["recall"] for v in out.values() if v["recall"] is not None]
    return {
        "by_dropped_clip": out,
        "precision_range": (min(ps), max(ps)) if ps else None,
        "recall_range": (min(rs), max(rs)) if rs else None,
    }


def override_direction() -> dict[str, Counter]:
    """Count hand overrides per method tag by the status they set."""
    by_tag: dict[str, Counter] = {}
    with (TRUTH / "methods" / "overrides.csv").open(encoding="utf-8") as h:
        for r in csv.DictReader(h):
            by_tag.setdefault(r["method"], Counter())[r["output_status"]] += 1
    return by_tag


def audit() -> dict[str, Any]:
    agg = json.loads((TRUTH / "methods" / "aggregate.json").read_text(encoding="utf-8"))
    rng = random.Random(SEED)
    result: dict[str, Any] = {"seed": SEED, "reps": REPS, "sets": {}}
    for s in SETS:
        result["sets"][s] = {}
        for m in METHODS:
            result["sets"][s][m] = {}
            for mode in MODES:
                block = agg[s][m][mode]
                pooled, per_clip = block["pooled"], block["per_clip"]
                tp = pooled["TP"]
                asserted = tp + pooled["FPv"] + pooled["FPn"]
                visible = tp + pooled["FPv"] + pooled["FN"]
                tp_by_clip = {k: c["TP"] for k, c in per_clip.items()}
                top = max(tp_by_clip, key=tp_by_clip.get) if tp_by_clip else None
                clip_recall = {k: c["recall"] for k, c in per_clip.items() if c["recall"] is not None}
                result["sets"][s][m][mode] = {
                    "TP": tp, "asserted": asserted, "visible": visible,
                    "precision": pooled["precision"], "recall": pooled["recall"],
                    "precision_wilson": wilson(tp, asserted), "recall_wilson": wilson(tp, visible),
                    **cluster_bootstrap(per_clip, rng),
                    "loo": leave_one_out(per_clip),
                    "clips_scored": len(per_clip),
                    "clips_with_positives": len(clip_recall),
                    "clips_with_any_tp": sum(1 for v in tp_by_clip.values() if v),
                    "top_clip": top,
                    "top_clip_tp_share": round(tp_by_clip[top] / tp, 3) if top and tp else None,
                    "per_clip_recall": clip_recall,
                    "false_runs": pooled["false_runs"],
                }
    # Both prospective holdouts pooled: the only data no decision was taken on.
    result["holdouts_pooled"] = {}
    for m in METHODS:
        result["holdouts_pooled"][m] = {}
        for mode in MODES:
            per_clip = {**agg["holdout1"][m][mode]["per_clip"], **agg["holdout2"][m][mode]["per_clip"]}
            p, r = _pr(list(per_clip.values()))
            tp = sum(c["TP"] for c in per_clip.values())
            asserted = tp + sum(c["FPv"] + c["FPn"] for c in per_clip.values())
            visible = tp + sum(c["FPv"] + c["FN"] for c in per_clip.values())
            recalls = sorted(c["recall"] for c in per_clip.values() if c["recall"] is not None)
            result["holdouts_pooled"][m][mode] = {
                "TP": tp, "asserted": asserted, "visible": visible,
                "precision": round(p, 3), "recall": round(r, 3),
                "precision_wilson": wilson(tp, asserted), "recall_wilson": wilson(tp, visible),
                **cluster_bootstrap(per_clip, rng),
                "per_clip_recall_sorted": recalls,
                "median_clip_recall": recalls[len(recalls) // 2] if len(recalls) % 2 else round((recalls[len(recalls) // 2 - 1] + recalls[len(recalls) // 2]) / 2, 3),
                "clips_with_positives": len(recalls),
            }
    result["override_direction"] = {k: dict(v) for k, v in override_direction().items() if k.startswith("tail_grounded_v3")}
    return result


def _fmt_ci(ci: Any) -> str:
    return "—" if not ci else f"{ci[0]:.2f}–{ci[1]:.2f}"


def render(a: dict[str, Any]) -> str:
    L = ["# Claims audit (generated by `python -m review.claims_audit`; do not edit)", "",
         f"Inputs: `aggregate.json`, `overrides.csv`. Clip bootstrap: {a['reps']} resamples of whole clips, seed {a['seed']}. "
         "Truth is model-annotated (claude-809c44f2); no row here is a human measurement.", ""]
    L += ["## Pooled precision and recall with intervals", "",
          "| set | method | scoring | P | P 95% (frames, Wilson) | P 95% (clips, bootstrap) | R | R 95% (frames) | R 95% (clips) | clips with positives | top clip share of TP |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    for s, ms in a["sets"].items():
        for m, modes in ms.items():
            for mode, c in modes.items():
                L.append(f"| {s} | {m.removeprefix('tail_grounded_')} | {mode} | {c['precision']} | {_fmt_ci(c['precision_wilson'])} | {_fmt_ci(c['precision_ci'])} | "
                         f"{c['recall']} | {_fmt_ci(c['recall_wilson'])} | {_fmt_ci(c['recall_ci'])} | {c['clips_with_positives']} | "
                         f"{c['top_clip_tp_share']} ({c['top_clip']}) |")
    L += ["", "## Both prospective holdouts pooled (12 clips; no decision was taken on them)", "",
          "| method | scoring | TP / asserted / visible | P | P 95% (clips) | R | R 95% (clips) | median per-clip recall | per-clip recall, sorted |",
          "|---|---|---|---|---|---|---|---|---|"]
    for m, modes in a["holdouts_pooled"].items():
        for mode, c in modes.items():
            L.append(f"| {m.removeprefix('tail_grounded_')} | {mode} | {c['TP']} / {c['asserted']} / {c['visible']} | {c['precision']} | {_fmt_ci(c['precision_ci'])} | "
                     f"{c['recall']} | {_fmt_ci(c['recall_ci'])} | {c['median_clip_recall']} | {', '.join(f'{x:.2f}' for x in c['per_clip_recall_sorted'])} |")
    L += ["", "## Leave-one-clip-out range (v3)", "", "| set | scoring | P range | R range |", "|---|---|---|---|"]
    for s, ms in a["sets"].items():
        for mode, c in ms["tail_grounded_v3"].items():
            L.append(f"| {s} | {mode} | {_fmt_ci(c['loo']['precision_range'])} | {_fmt_ci(c['loo']['recall_range'])} |")
    L += ["", "## Hand overrides on v3, by the status they set", "", "| tag | " + " | ".join(sorted({k for v in a['override_direction'].values() for k in v})) + " |"]
    keys = sorted({k for v in a["override_direction"].values() for k in v})
    L.append("|---|" + "---|" * len(keys))
    for tag, c in sorted(a["override_direction"].items()):
        L.append(f"| {tag} | " + " | ".join(str(c.get(k, 0)) for k in keys) + " |")
    L.append("")
    return "\n".join(L)


def main() -> None:
    a = audit()
    OUT_JSON.write_text(json.dumps(a, indent=1) + "\n", encoding="utf-8")
    md = render(a)
    OUT_MD.write_text(md, encoding="utf-8")
    print(md)


if __name__ == "__main__":
    main()
