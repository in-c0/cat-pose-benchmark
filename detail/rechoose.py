"""Re-run only the temporal choice of a grounded-v1 result from its saved candidates.

Every v1 ``result.json`` keeps, per frame, the candidate boxes with their detector scores
and crop-check outcome. That is everything the Viterbi needs, so a different temporal
setting can be scored without touching a model. The output is a result.json with the
same shape (statuses, ``tail`` boxes, ``n_after_crop_check``) but no masks or curves;
``review.eval_proxy`` scores it, and ``grounded_tail_v1`` can be re-run for overlays once
a setting is chosen.

    python -m detail.rechoose review/work/<clip>/tail_grounded_v1/result.json \
        --output review/work/<clip>/<tag>/result.json --time-scale
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import detail.grounded_tail_v1 as v1


def rechoose(
    result: dict[str, Any],
    *,
    frame_interval_s: float,
    time_scale: bool = False,
    emission_weight: float | None = None,
    none_emission: float | None = None,
    move_weight: float | None = None,
    none_switch_cost: float | None = None,
) -> dict[str, Any]:
    saved = (v1.NONE_EMISSION, v1.MOVE_WEIGHT, v1.NONE_SWITCH_COST)
    if none_emission is not None:
        v1.NONE_EMISSION = none_emission
    if move_weight is not None:
        v1.MOVE_WEIGHT = move_weight
    if none_switch_cost is not None:
        v1.NONE_SWITCH_COST = none_switch_cost
    try:
        frames = result["frames"]
        surviving = [[c for c in (f.get("candidates") or []) if not c.get("looks_like_paw")] for f in frames]
        diagonals = []
        for f in frames:
            if f.get("cat"):
                b = f["cat"]["box"]
                diagonals.append(math.hypot(b[2] - b[0], b[3] - b[1]))
            else:
                diagonals.append(math.hypot(*f.get("image_size", [1920, 1080])))
        if emission_weight is not None:
            scale = emission_weight
        else:
            scale = (frame_interval_s / v1.REFERENCE_INTERVAL_S) if time_scale else 1.0
        choice = v1.viterbi(surviving, diagonals, scale)
    finally:
        v1.NONE_EMISSION, v1.MOVE_WEIGHT, v1.NONE_SWITCH_COST = saved

    out_frames = []
    counts: dict[str, int] = {}
    for f, cands, pick in zip(frames, surviving, choice):
        rec = {k: f[k] for k in ("frame_index", "file", "cat", "image_size", "n_candidates") if k in f}
        rec["n_after_crop_check"] = len(cands)
        if f.get("cat") is None:
            rec["status"] = "no_cat"
        elif not f.get("candidates"):
            rec["status"] = "no_tail_box"
        elif not cands:
            rec["status"] = "all_look_like_paw"
        elif pick is None:
            rec["status"] = "temporal_none"
        else:
            rec["status"] = "ok"
            rec["tail"] = cands[pick]
        counts[rec["status"]] = counts.get(rec["status"], 0) + 1
        out_frames.append(rec)
    return {
        "schema_version": "0.1.0",
        "clip_id": result["clip_id"],
        "method": "tail_grounded_v1_rechoose",
        "source": result.get("options"),
        "options": {
            "time_scale": time_scale,
            "emission_weight": scale,
            "frame_interval_s": frame_interval_s,
            "none_emission": none_emission if none_emission is not None else saved[0],
            "move_weight": move_weight if move_weight is not None else saved[1],
            "none_switch_cost": none_switch_cost if none_switch_cost is not None else saved[2],
        },
        "summary": {"frames_total": len(out_frames), "frames_with_curve": counts.get("ok", 0), "status_counts": counts},
        "frames": out_frames,
        "note": "temporal choice only; no masks or curves. Re-run grounded_tail_v1 for overlays.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Re-run the temporal choice from saved v1 candidates.")
    parser.add_argument("result_json", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--fps", type=float, required=True, help="sampling rate of the clip the result came from")
    parser.add_argument("--time-scale", action="store_true")
    parser.add_argument("--emission-weight", type=float, help="explicit per-frame emission weight (overrides --time-scale)")
    parser.add_argument("--none-emission", type=float)
    parser.add_argument("--move-weight", type=float)
    parser.add_argument("--none-switch-cost", type=float)
    args = parser.parse_args()
    result = json.loads(args.result_json.read_text(encoding="utf-8"))
    out = rechoose(
        result, frame_interval_s=1.0 / args.fps, time_scale=args.time_scale, emission_weight=args.emission_weight,
        none_emission=args.none_emission, move_weight=args.move_weight, none_switch_cost=args.none_switch_cost,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out, indent=2, sort_keys=True, default=float) + "\n", encoding="utf-8")
    print(json.dumps(out["summary"], sort_keys=True))


if __name__ == "__main__":
    main()


def path_score(frames: list[list[dict[str, Any]]], diagonals: list[float], emission_scale: float = 1.0) -> float:
    """Total score of the best Viterbi path (same objective as ``v1.viterbi``)."""
    n = len(frames)
    if n == 0:
        return 0.0

    def centre(b):
        return ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)

    best = None
    for t in range(n):
        emis = [v1.NONE_EMISSION * emission_scale] + [c["score"] * emission_scale for c in frames[t]]
        if t == 0:
            best = emis[:]
            continue
        cur = [-math.inf] * len(emis)
        for s in range(len(emis)):
            for p in range(len(best)):
                if s == 0 and p == 0:
                    trans = 0.0
                elif s == 0 or p == 0:
                    trans = -v1.NONE_SWITCH_COST
                else:
                    a = centre(frames[t - 1][p - 1]["box"])
                    b = centre(frames[t][s - 1]["box"])
                    trans = -v1.MOVE_WEIGHT * math.hypot(a[0] - b[0], a[1] - b[1]) / max(diagonals[t], 1.0)
                cur[s] = max(cur[s], best[p] + trans + emis[s])
        best = cur
    return max(best)


def margin(result: dict[str, Any], frame_index: int, emission_scale: float = 1.0) -> float | None:
    """S(best path) - S(best path with the opposite decision forced at ``frame_index``):
    positive means the current decision is preferred by that much. Forcing NONE means
    emptying the candidate list on that frame; forcing TAIL means removing the NONE
    option there (approximated by a very negative none emission)."""
    frames = result["frames"]
    surviving = [[c for c in (f.get("candidates") or []) if not c.get("looks_like_paw")] for f in frames]
    diagonals = [math.hypot(f["cat"]["box"][2] - f["cat"]["box"][0], f["cat"]["box"][3] - f["cat"]["box"][1]) if f.get("cat") else math.hypot(*f.get("image_size", [1920, 1080])) for f in frames]
    pos = next((k for k, f in enumerate(frames) if f["frame_index"] == frame_index), None)
    if pos is None:
        return None
    full = path_score(surviving, diagonals, emission_scale)
    chosen_tail = frames[pos].get("status") == "ok"
    if chosen_tail:
        forced = [list(s) for s in surviving]
        forced[pos] = []
        alt = path_score(forced, diagonals, emission_scale)
    else:
        if not surviving[pos]:
            return None
        saved = v1.NONE_EMISSION
        # force a tail at pos by making NONE prohibitively bad on that frame only
        forced = [list(s) for s in surviving]
        # emulate by giving each candidate at pos a large bonus and subtracting it back
        bonus = 10.0
        forced[pos] = [dict(c, score=c["score"] + bonus / max(emission_scale, 1e-9)) for c in surviving[pos]]
        alt = path_score(forced, diagonals, emission_scale) - bonus
        v1.NONE_EMISSION = saved
    return full - alt
