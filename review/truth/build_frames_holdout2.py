"""Write holdout2_frames.csv (truth 1.3) for prospective holdout #2 (ChatGPT pass 15).

Eight clips, the next eight distinct-uploader files in the frozen seed-20260920 order
(review/holdout/selection2.json). Annotated from raw review frames only, before any
method ran on these clips; reference boxes boxed by eye on a 100-200 px grid (about
+-60 px on the 4K clip), none from a method.
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
    # 1920x1080; silver tabby fills the frame with its head for 8 s, then walks away
    # from the camera with the tail straight up; the tip leaves the top edge.
    "holdout2-ljubljana-domaca-macka": {
        **{i: (N, "medium", "out_of_frame", "head close to the lens, tail out of frame", "") for i in rng(0, 32)},
        33: (P, "high", "out_of_frame", "tail rising at the top right edge", "1690 0 1810 430"),
        34: (V, "high", "out_of_frame", "tail straight up, tip out of frame", "1400 0 1550 800"),
        35: (V, "high", "out_of_frame", "tail straight up", "1280 0 1480 820"),
        36: (V, "high", "out_of_frame", "tail straight up", "1330 0 1500 800"),
        37: (V, "high", "out_of_frame", "tail straight up", "1150 0 1425 1000"),
        38: (V, "high", "out_of_frame", "tail straight up", "1080 0 1280 1000"),
        39: (V, "high", "out_of_frame", "tail straight up", "1110 0 1360 1000"),
    },
    # 1920x1080; small tabby on the ground beside a person, lying, then sitting with the
    # tail out on the ground to the right, then walking towards the person with the tail up,
    # then at the left edge of the frame.
    "holdout2-andra-and-billy": {
        **{i: (N, "medium", "occlusion", "lying, tail behind the body", "") for i in rng(0, 15)},
        # post-inference amendment (pass 15): v1 drew a mask at ground level behind the
        # hindquarters on f012-f014 that could be the tail lying on the ground; the blind
        # reading said not_visible. Disagreement resolves to uncertain, never to visible.
        **{i: (U, "low", "appearance_ambiguous", "striped shape on the ground behind the rump: tail or shadow (post-inference disagreement -> uncertain)", "") for i in (12, 13, 14)},
        16: (V, "high", "none", "sitting, tail on the ground to the right", "610 545 790 660"),
        17: (V, "high", "none", "sitting, tail on the ground to the right", "610 545 800 660"),
        **{i: (V, "high", "none", "tail extended on the ground to the right", "620 545 880 660") for i in rng(18, 21)},
        22: (U, "low", "appearance_ambiguous", "turning; striped part at the right could be tail or hind leg", ""),
        23: (P, "medium", "out_of_frame", "tail lying on the ground at the left edge", "0 560 130 690"),
        24: (V, "high", "none", "walking away, tail dropping to the right", "280 400 570 660"),
        25: (V, "high", "none", "tail up", "230 250 400 470"),
        26: (V, "high", "none", "tail up", "180 250 340 520"),
        27: (V, "high", "none", "tail up", "110 250 300 470"),
        28: (P, "medium", "occlusion", "frontal, tail behind and above the back", "140 250 300 420"),
        29: (P, "medium", "occlusion", "frontal, tail behind and above the back", "140 250 300 420"),
        **{i: (N, "medium", "occlusion", "frontal, tail behind the body", "") for i in (30, 31)},
        **{i: (U, "low", "out_of_frame", "cat at the left edge, striped part could be tail or leg", "") for i in rng(32, 35)},
        **{i: (N, "medium", "occlusion", "walking towards the camera, tail behind", "") for i in rng(36, 38)},
        39: (U, "low", "blur", "walking right, striped diagonal at the left edge", ""),
    },
    # 1440x2560 portrait; extreme close-up of an orange-and-white cat's face, dark.
    "holdout2-koetjing-cito": {i: (N, "medium", "out_of_frame", "face fills the frame", "") for i in rng(0, 39)},
    # 1920x1080; cat sitting on a high ledge seen from below, backlit; 24 frames.
    "holdout2-sophy-ledge": {
        **{i: (N, "medium", "occlusion", "sitting on the ledge, tail behind on the ledge", "") for i in rng(0, 23)},
        11: (U, "low", "blur", "camera motion blur", ""),
        13: (U, "low", "blur", "camera motion blur", ""),
    },
    # 720x1280; top-down view of a street from a window; an orange cat lies on a balcony
    # below, about 80 px long; 32 frames.
    "holdout2-cat-spied-on": {i: (U, "low", "small", "cat is ~80 px on a balcony far below; tail not resolvable", "") for i in rng(0, 31)},
    # 720x576 archival newsreel: leader, a building, then a child with a terrier. No cat.
    "holdout2-dierenasyl": {i: (N, "high", "out_of_frame", "no cat (leader, building, child with a dog)", "") for i in rng(0, 39)},
    # 1920x1080 (1080p transcode of a 4K AV1 upload); grey British Shorthair eating cat
    # grass, seen from above and behind; the tail lies curled around the right of the rump.
    "holdout2-katze-katzengras": {i: (P, "medium", "occlusion", "tail curled along the right of the rump, uniform grey fur", "1350 820 1780 1060") for i in rng(0, 39)},
    # 3840x2160; a produced video (university series) that the keyword list did not catch:
    # a ginger cat with a collar walks towards the camera with its tail straight up (tip out
    # of frame) under title overlays, turns, walks away; then two phone clips of other cats.
    "holdout2-katten-naar-buiten": {
        0: (V, "high", "out_of_frame", "tail up behind the head, blurred by shallow focus", "1760 0 2000 750"),
        **{i: (V, "medium", "occlusion", "tail up behind the head under the title overlay", "1710 0 2050 750") for i in (1, 2, 3)},
        4: (V, "medium", "occlusion", "tail up under the title overlay", "1760 0 2000 750"),
        **{i: (V, "medium", "occlusion", "tail up under the title overlay", "1710 0 2050 750") for i in (5, 6, 7)},
        8: (V, "medium", "occlusion", "tail up between the logo blocks", "1800 0 2000 750"),
        9: (U, "low", "occlusion", "logo covers most of the frame", ""),
        10: (V, "high", "out_of_frame", "tail up behind the head", "1400 0 1720 750"),
        11: (V, "high", "out_of_frame", "tail up behind the head", "1560 0 1840 750"),
        **{i: (V, "high", "out_of_frame", "tail up behind the head", "1320 0 1640 750") for i in rng(12, 19)},
        **{i: (V, "high", "out_of_frame", "tail up behind the head", "1280 0 1560 750") for i in rng(20, 23)},
        24: (V, "high", "out_of_frame", "side view, tail up at the top left", "690 0 1000 800"),
        25: (V, "high", "out_of_frame", "side view, tail up", "770 0 1150 700"),
        26: (V, "high", "out_of_frame", "side view, tail up", "850 0 1230 800"),
        27: (V, "high", "out_of_frame", "walking away, tail up and curving", "1075 0 1540 1000"),
        28: (V, "high", "out_of_frame", "walking away, tail up", "1770 0 2230 900"),
        29: (V, "high", "out_of_frame", "walking away, tail up", "2150 0 2540 800"),
        30: (V, "high", "out_of_frame", "walking away, tail up", "2300 0 2690 800"),
        **{i: (N, "medium", "occlusion", "second clip: tuxedo cat in a cone held by a person; tail not in view", "") for i in rng(31, 34)},
        **{i: (N, "medium", "occlusion", "third clip: tabby sitting on a dog, facing the camera; tail behind", "") for i in rng(35, 39)},
    },
}

TARGET = {
    "holdout2-ljubljana-domaca-macka": "cat_0 silver tabby",
    "holdout2-andra-and-billy": "cat_0 tabby",
    "holdout2-koetjing-cito": "cat_0 orange-white",
    "holdout2-sophy-ledge": "cat_0",
    "holdout2-cat-spied-on": "cat_0 orange (tiny)",
    "holdout2-dierenasyl": "none",
    "holdout2-katze-katzengras": "cat_0 grey",
    "holdout2-katten-naar-buiten": "cat_0 ginger (f000-f030), cat_1 tuxedo (f031-f034), cat_2 tabby (f035-f039)",
}


def main() -> None:
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=HERE).stdout.strip()
    rows = []
    for clip, decisions in DECISIONS.items():
        for f in load_frames_manifest(clip)["frames"]:
            i = f["frame_index"]
            vis, conf, cond, note, ref = decisions[i]
            identity = ("tail" if conf in ("high", "medium") else "unresolved") if vis in (V, P) else ""
            rows.append({
                "clip_id": clip, "frame_index": i, "timestamp_s": f"{f['timestamp_s']:.4f}", "target_cat": TARGET[clip],
                "tail_visibility": vis, "tail_identity_confidence": conf, "identity": identity, "condition": cond, "note": note, "reference_box": ref,
                "alt_cat": "", "alt_tail_visibility": "", "alt_identity_confidence": "", "alt_note": "", "alt_reference_box": "",
            })
    out = HERE / "holdout2_frames.csv"
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
