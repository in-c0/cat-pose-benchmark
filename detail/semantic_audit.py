"""Offline audit of the SigLIP crop scores v1 already computes (ChatGPT pass 13).

For every frame v1 accepted, read the accepted candidate's six zero-shot probabilities
(tail, paw, leg, face, belly, floor), compute the margin ``tail - max(others)`` and which
negative class wins, and cross it with the frozen truth judgement of that frame. Then
evaluate the parameter-free rule ``accept iff tail > max(others)`` as a post-hoc refusal on
v1's accepted frames (no model rerun, the temporal pass is not re-solved). Nothing is
fitted; the output is a table.

    python -m detail.semantic_audit            # development clips
    python -m detail.semantic_audit --holdout  # holdout clips
"""

from __future__ import annotations

import argparse
import json
from collections import Counter

from review.common import clip_workdir
from review.score_truth import frame_class, judge, load_overrides, load_truth

NEG = ("paw", "leg", "face", "belly", "floor")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--holdout", action="store_true")
    p.add_argument("--method", default="tail_grounded_v1")
    a = p.parse_args()
    truth = load_truth("holdout_frames.csv" if a.holdout else "frames.csv")
    overrides = load_overrides()
    tag = a.method + ("+holdout" if a.holdout else "")
    rows = []
    for clip in sorted({k[0] for k in truth}):
        judged = {r["frame_index"]: r for r in judge(a.method, clip, clip, 1, truth, overrides, tag)}
        if not judged:
            continue
        res = json.loads((clip_workdir(clip) / a.method / "result.json").read_text(encoding="utf-8"))
        for f in res["frames"]:
            j = judged.get(f["frame_index"])
            if j is None or f["status"] != "ok" or not f.get("tail") or not f["tail"].get("crop_probs"):
                continue
            pr = f["tail"]["crop_probs"]
            worst = max(NEG, key=lambda k: pr.get(k, 0.0))
            fc = frame_class(truth[(clip, f["frame_index"])])
            verdict = "TP" if (fc == "visible" and j["output_status"] in ("correct", "partial")) else ("FP" if fc != "ambiguous" else "ambiguous")
            rows.append({"clip": clip, "frame": f["frame_index"], "verdict": verdict, "wrong_part": j.get("wrong_part", ""), "tail": pr["tail"], "worst": worst, "worst_p": pr[worst], "margin": pr["tail"] - pr[worst]})
    # summary
    for v in ("TP", "FP", "ambiguous"):
        sub = [r for r in rows if r["verdict"] == v]
        if not sub:
            continue
        keep = sum(1 for r in sub if r["margin"] > 0)
        print(f"{v}: n {len(sub)}, tail wins on {keep}, loses on {len(sub) - keep}; losing class counts {Counter(r['worst'] for r in sub if r['margin'] <= 0)}")
        ms = sorted(r["margin"] for r in sub)
        print(f"   margin min {ms[0]:.2f} p10 {ms[len(ms)//10]:.2f} median {ms[len(ms)//2]:.2f} p90 {ms[9*len(ms)//10]:.2f}")
    print("FP frames:")
    for r in rows:
        if r["verdict"] == "FP":
            print(f"   {r['clip'][8:22]} f{r['frame']:03d} {r['wrong_part'] or '-':9s} tail {r['tail']:.2f} {r['worst']} {r['worst_p']:.2f} margin {r['margin']:+.2f}")
    print("TP frames the rule would refuse:")
    for r in rows:
        if r["verdict"] == "TP" and r["margin"] <= 0:
            print(f"   {r['clip'][8:22]} f{r['frame']:03d} tail {r['tail']:.2f} {r['worst']} {r['worst_p']:.2f} margin {r['margin']:+.2f}")
    out = clip_workdir("_audit") / f"semantic_audit_{tag}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rows, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
