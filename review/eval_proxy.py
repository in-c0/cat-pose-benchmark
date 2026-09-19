"""Proxy scoring of a tail method against the frame reading recorded in the notes.

Truth here is not protocol verdicts. For the two tuned clips it is note 01's reading of
the v0 grounded output (which frames had the v0 box on the tail); for the two held-out
clips it is note 04's reading. A method's frame is:

- ``right``   accepted, the frame is in the visible set, and its box overlaps the v0 box
              on that frame at IoU >= 0.3;
- ``wrong``   accepted on any other frame;
- ``missed``  refused on a visible frame;
- ``refused_not_visible`` refused on a frame outside the visible set.

Dense runs are scored on the review timestamps only: a dense clip declares ``dense_of``
and ``dense_factor`` in clips.json, and dense frame ``k * i`` stands for review frame ``i``.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from detail.grounded_tail import _iou
from review.common import clip_workdir, load_clips

# Frames on which the v0 grounded box was read as on the tail. Notes 01 and 04.
VISIBLE: dict[str, set[int]] = {
    "commons-cat-plays": {0, 4, 5, 7, 8, 9, 10, 11, 12, 19, 20},
    "commons-cat-jumping-backwards": {5, 6, 7, 8, 9, 10, 11, 12, 16, 17, 20, 21, 22, 23},
    "commons-black-cat-walking": set(range(0, 36)),
    "commons-cat-licking-tail": set(range(0, 27)),
}
IOU_MIN = 0.3
# Frames where the v0 box itself was later seen to be wrong although the tail is visible;
# the reference box is taken from the named method instead. Found while building this
# scorer: walking f006, v0 grounded the ear, v1 the tail.
REFERENCE_OVERRIDE: dict[tuple[str, int], str] = {("commons-black-cat-walking", 6): "tail_grounded_v1"}


def _matches(box: list[float], ref: list[float]) -> bool:
    """Same tail if the boxes overlap at IoU >= 0.3, or one lies almost entirely inside
    the other (a partial-tail box against a full-tail box is still the tail)."""
    if _iou(box, ref) >= IOU_MIN:
        return True
    x0, y0 = max(box[0], ref[0]), max(box[1], ref[1])
    x1, y1 = min(box[2], ref[2]), min(box[3], ref[3])
    inter = max(0.0, x1 - x0) * max(0.0, y1 - y0)
    smaller = min((box[2] - box[0]) * (box[3] - box[1]), (ref[2] - ref[0]) * (ref[3] - ref[1]))
    return smaller > 0 and inter / smaller >= 0.8


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


def score_clip(review_clip: str, method: str, run_clip: str | None = None, factor: int = 1) -> dict[str, Any]:
    run_clip = run_clip or review_clip
    v0 = {f["frame_index"]: f for f in json.loads((clip_workdir(review_clip) / "tail_grounded" / "result.json").read_text(encoding="utf-8"))["frames"]}
    for (clip, idx), src in REFERENCE_OVERRIDE.items():
        if clip == review_clip:
            alt = {f["frame_index"]: f for f in json.loads((clip_workdir(review_clip) / src / "result.json").read_text(encoding="utf-8"))["frames"]}
            if idx in alt and alt[idx].get("tail"):
                v0[idx] = alt[idx]
    run = {f["frame_index"]: f for f in json.loads((clip_workdir(run_clip) / method / "result.json").read_text(encoding="utf-8"))["frames"]}
    visible = VISIBLE[review_clip]
    counts = {"right": 0, "wrong": 0, "missed": 0, "refused_not_visible": 0}
    changed: list[str] = []
    for i in sorted(v0):
        f = run.get(i * factor)
        if f is None:
            continue
        accepted = f["status"] in ("ok", "propagated")
        if accepted:
            box = _box_of(f)
            ref = _box_of(v0[i])
            if i in visible and box and ref and _matches(box, ref):
                counts["right"] += 1
            else:
                counts["wrong"] += 1
                changed.append(f"wrong f{i:03d}")
        elif i in visible:
            counts["missed"] += 1
            changed.append(f"missed f{i:03d}")
        else:
            counts["refused_not_visible"] += 1
    acc = counts["right"] + counts["wrong"]
    counts["precision"] = round(counts["right"] / acc, 3) if acc else None
    counts["recall"] = round(counts["right"] / len(visible & set(v0)), 3) if visible else None
    counts["frames"] = changed
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Proxy-score a tail method on the review timestamps.")
    parser.add_argument("method")
    parser.add_argument("--dense", action="store_true", help="score the clips' dense resamples on the review timestamps")
    parser.add_argument("--clip", action="append")
    args = parser.parse_args()
    clips = load_clips()
    dense_for = {c["dense_of"]: c for c in clips if c.get("dense_of") and c.get("dense_factor")}
    total = {"right": 0, "wrong": 0, "missed": 0, "refused_not_visible": 0}
    for review_clip in VISIBLE:
        if args.clip and review_clip not in args.clip:
            continue
        if args.dense:
            d = dense_for.get(review_clip)
            if not d:
                continue
            r = score_clip(review_clip, args.method, d["clip_id"], int(d["dense_factor"]))
        else:
            r = score_clip(review_clip, args.method)
        for k in total:
            total[k] += r[k]
        print(f"{review_clip}: right {r['right']} wrong {r['wrong']} missed {r['missed']} refused_nv {r['refused_not_visible']}  P {r['precision']} R {r['recall']}  {' '.join(r['frames'])}")
    acc = total["right"] + total["wrong"]
    vis = total["right"] + total["missed"]
    print(f"TOTAL {args.method}{' dense' if args.dense else ''}: right {total['right']} wrong {total['wrong']} missed {total['missed']} refused_nv {total['refused_not_visible']}  P {total['right']/acc if acc else 0:.3f} R {total['right']/vis if vis else 0:.3f}")


if __name__ == "__main__":
    main()
