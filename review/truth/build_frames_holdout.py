"""Write holdout_frames.csv (truth 1.3) for the prospective holdout clips.

Annotated from raw review frames only, before any method was run on these clips
(ChatGPT pass 11 protocol). Reference boxes are boxed by eye on a 50 px grid (+-20 px);
none comes from a method. Two-cat frames carry the second cat in the alt_* columns.
"""

from __future__ import annotations

import csv
import subprocess
from pathlib import Path

from review.common import load_frames_manifest

HERE = Path(__file__).resolve().parent
V, P, N, U = "visible", "partial", "not_visible", "uncertain"


def rng(a: int, b: int) -> list[int]:
    return list(range(a, b + 1))


# (visibility, confidence, condition, note, reference_box)
DECISIONS: dict[str, dict[int, tuple[str, str, str, str, str]]] = {
    # 1080x1920 portrait; cream cat on its back on a lap, tail hanging down the right leg the
    # whole window; the tail barely moves so one box serves every frame (checked on all 40).
    "holdout-larry-nails": {i: (V, "high", "none", "cream tail hangs down along the leg, tip at lower right", "680 930 860 1260") for i in rng(0, 39)},
    # 1440x1080 archival film (1894), two cats in harnesses boxing behind ropes; f000-f001 black.
    # Tails cannot be resolved on any frame at this quality: uncertain, low.
    "holdout-boxing-cats-1894": {
        **{i: (N, "high", "out_of_frame", "black frame, no cat", "") for i in (0, 1)},
        **{i: (U, "low", "small", "archival film, ropes; neither cat's tail resolvable", "") for i in rng(2, 39)},
    },
    # 1280x720; white/orange cat rolling on a plate, extreme close-up, rump at the left edge.
    "holdout-cat-playing-taiwan": {
        0: (U, "low", "blur", "motion blur", ""),
        **{i: (N, "medium", "out_of_frame", "rump at the left edge, tail behind/out of frame", "") for i in rng(1, 18)},
        19: (U, "low", "blur", "orange smear across the top right; tail or head in motion", ""),
        **{i: (N, "medium", "occlusion", "white body, tail not in view", "") for i in (20, 21)},
        22: (V, "high", "none", "orange striped tail rises from the rump at right", "880 230 1010 460"),
        23: (P, "medium", "out_of_frame", "orange tail tip lying at the right edge", "1140 370 1280 480"),
        **{i: (N, "medium", "out_of_frame", "lying on its side, head lower right, tail behind the body", "") for i in rng(24, 39)},
    },
    # 3840x2160 (1906 film, upscaled): title card then two people at a table; no cat in the
    # first 10 s. Negative-control clip by construction of the sampling protocol.
    "holdout-dejeuner-des-minet-1906": {i: (N, "high", "out_of_frame", "no cat in frame (title card / people at a table)", "") for i in rng(0, 39)},
}

ALT: dict[str, dict[int, tuple[str, str, str, str, str]]] = {
    "holdout-boxing-cats-1894": {i: ("cat_1 right", U, "low", "as cat_0", "") for i in rng(2, 39)},
}

TARGET = {
    "holdout-larry-nails": "cat_0 cream",
    "holdout-boxing-cats-1894": "cat_0 left",
    "holdout-cat-playing-taiwan": "cat_0 white-orange",
    "holdout-dejeuner-des-minet-1906": "none",
}


def main() -> None:
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=HERE).stdout.strip()
    rows = []
    for clip, decisions in DECISIONS.items():
        for f in load_frames_manifest(clip)["frames"]:
            i = f["frame_index"]
            vis, conf, cond, note, ref = decisions[i]
            alt = ALT.get(clip, {}).get(i, ("", "", "", "", ""))
            identity = ("tail" if conf in ("high", "medium") else "unresolved") if vis in (V, P) else ""
            rows.append({
                "clip_id": clip, "frame_index": i, "timestamp_s": f"{f['timestamp_s']:.4f}", "target_cat": TARGET[clip],
                "tail_visibility": vis, "tail_identity_confidence": conf, "identity": identity, "condition": cond, "note": note, "reference_box": ref,
                "alt_cat": alt[0], "alt_tail_visibility": alt[1], "alt_identity_confidence": alt[2], "alt_note": alt[3], "alt_reference_box": alt[4],
            })
    out = HERE / "holdout_frames.csv"
    with out.open("w", newline="", encoding="utf-8") as h:
        h.write(f"# annotation_protocol_version: 1.3; reviewer_id: claude-809c44f2 (model); frozen_at_commit: {commit}; date: 2026-09-20; annotated before any method ran on these clips\n")
        w = csv.DictWriter(h, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    counts: dict[str, dict[str, int]] = {}
    for r in rows:
        counts.setdefault(r["clip_id"], {}).setdefault(r["tail_visibility"], 0)
        counts[r["clip_id"]][r["tail_visibility"]] += 1
    print(counts)


if __name__ == "__main__":
    main()
