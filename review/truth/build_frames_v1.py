"""Write frames.csv (truth v1) from the annotation decisions in clips.md.

The visibility labels are hand decisions recorded here as data; reference boxes are taken
from a named method's tail box on frames where the annotator confirmed that box lies on
the tail (see clips.md), and left blank otherwise. Run once; the output is then frozen.
"""

from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path

from review.common import clip_workdir, load_frames_manifest

HERE = Path(__file__).resolve().parent

V, P, N, U = "visible", "partial", "not_visible", "uncertain"


def rng(a: int, b: int) -> list[int]:
    return list(range(a, b + 1))


# (visibility, confidence, condition, note) per frame; default is not_visible / medium.
DECISIONS: dict[str, dict[int, tuple[str, str, str, str]]] = {
    "commons-cat-plays": {
        **{i: (N, "high", "appearance_ambiguous", "raised hind leg with white paw; tail under body") for i in rng(0, 3)},
        4: (V, "high", "none", "black tail extends up-left, no white tip"),
        5: (V, "high", "none", "black tail extends left"),
        6: (N, "medium", "occlusion", "cat curled; tail under body"),
        7: (P, "medium", "occlusion", "only the tail tip shows upper-left"),
        8: (P, "medium", "occlusion", "only the tail tip shows upper-left"),
        **{i: (N, "medium", "appearance_ambiguous", "side-lying; hind legs with white paws toward camera; tail under body") for i in rng(9, 12)},
        **{i: (N, "medium", "occlusion", "tail under body") for i in rng(13, 18)},
        19: (V, "high", "none", "tail curled, upper right"),
        20: (V, "high", "none", "tail curled, upper right"),
        **{i: (N, "medium", "occlusion", "curled on side; tail under body") for i in rng(21, 32)},
    },
    "commons-cat-jumping-backwards": {
        0: (U, "low", "blur", "motion blur, no cat resolvable"),
        1: (U, "low", "blur", "motion blur"),
        2: (V, "high", "dark", "tabby, tail curves up right"),
        3: (V, "high", "dark", "tabby"),
        4: (V, "high", "blur", "tuxedo running, tail up"),
        5: (V, "high", "blur", "tuxedo jumping, tail up"),
        6: (V, "high", "multi_cat", "tuxedo, tail to the left"),
        **{i: (V, "high", "none", "tabby, tail curled up right") for i in rng(7, 12)},
        **{i: (V, "high", "none", "tabby") for i in rng(13, 17)},
        18: (U, "low", "blur", "motion blur"),
        19: (N, "medium", "occlusion", "tuxedo on scratcher, tail behind body"),
        **{i: (V, "high", "none", "tuxedo from behind, tail down") for i in rng(20, 23)},
    },
    "commons-black-cat-walking": {
        0: (N, "medium", "occlusion", "cat faces camera, tail behind body"),
        1: (P, "high", "none", "tail tip above the back"),
        **{i: (V, "high", "none", "tail up") for i in rng(2, 19)},
        20: (P, "high", "none", "tail base above the back, frontal"),
        **{i: (V, "high", "none", "tail up") for i in rng(21, 29)},
        **{i: (P, "high", "none", "frontal, tail tip above the back") for i in rng(30, 33)},
        34: (V, "high", "none", "tail up, close"),
        35: (V, "high", "none", "tail up, close"),
        36: (V, "high", "out_of_frame", "extreme close-up, tail fills frame; no cat box"),
        37: (V, "high", "out_of_frame", "extreme close-up, tail fills frame; no cat box"),
    },
    "commons-cat-licking-tail": {
        **{i: (V, "high", "dark", "tail along the sofa edge") for i in rng(0, 26)},
        # pass 10 blinded re-review with +-1 s of raw 8 fps context: the strip under the chin
        # cannot be separated from the dark body / foreleg shadow; the tail was along the
        # sofa edge at f025-f026 and the head comes down onto that spot, which is consistent
        # with the tail being licked but does not make it resolvable. identity: unresolved.
        **{i: (P, "low", "occlusion", "curled; dark strip under chin, unresolved (re-reviewed with temporal context, pass 10)") for i in rng(27, 35)},
        **{i: (N, "medium", "occlusion", "curled tight, tail under body") for i in rng(36, 51)},
    },
}

# Where the reference box comes from on visible/partial frames: (method, frame) — the
# annotator confirmed that method's tail box on that frame lies on the tail.
REFERENCE_SOURCE: dict[str, dict[int, tuple[str, int]]] = {
    "commons-cat-plays": {i: ("tail_grounded", i) for i in (4, 5, 7, 8, 19, 20)},
    "commons-cat-jumping-backwards": {i: ("tail_grounded", i) for i in rng(2, 17) + rng(20, 23)},
    # f006/f007: every detector box is the whole cat with the tail tip at its top edge; the
    # reference is the tail tip itself, boxed from the bidirectional-consensus mask after
    # checking it by eye on the overlay (pass 9, 2026-09-20).
    "commons-black-cat-walking": {**{i: ("tail_grounded", i) for i in rng(1, 35) if i not in (6, 7)}, 6: ("box", "625 0 805 142"), 7: ("box", "312 0 525 189")},
    "commons-cat-licking-tail": {i: ("tail_grounded", i) for i in rng(0, 26)},
}

# v1.1 (pass 8): instance-complete annotation. Every other cat whose tail is discernible on
# a frame gets (cat, visibility, confidence, note, reference box). Only the jumping clip has
# two cats. Reference boxes for the tabby on f004-f006 were confirmed by eye on the
# pass-7 long-propagation overlays and taken from that mask's extent; the tuxedo tail on
# f007-f017 (upright on the scratcher, body hidden) was boxed by eye on a 50 px grid,
# roughly +-20 px.
ALT: dict[str, dict[int, tuple[str, str, str, str, str]]] = {
    "commons-cat-jumping-backwards": {
        **{i: ("tuxedo", "uncertain", "low", "motion blur", "") for i in (0, 1)},
        **{i: ("tuxedo", N, "low", "dark; tuxedo not resolvable", "") for i in (2, 3)},
        4: ("tabby", V, "high", "tabby at the back, tail up right", "783 426 904 478"),
        5: ("tabby", V, "high", "tabby in the doorway, tail to the right", "710 238 871 284"),
        6: ("tabby", V, "high", "tabby in the doorway, tail to the right", "622 226 784 297"),
        7: ("tuxedo", V, "high", "upright tail on the scratcher, body hidden", "1165 655 1300 840"),
        8: ("tuxedo", V, "high", "upright tail on the scratcher, body hidden", "1125 655 1240 880"),
        9: ("tuxedo", V, "high", "upright tail on the scratcher, body hidden", "1095 690 1190 910"),
        10: ("tuxedo", V, "high", "upright tail on the scratcher, body hidden", "1095 660 1205 910"),
        11: ("tuxedo", V, "high", "upright tail on the scratcher, body hidden", "1140 745 1275 960"),
        12: ("tuxedo", V, "high", "upright tail on the scratcher, body hidden", "1065 745 1240 960"),
        13: ("tuxedo", V, "high", "upright tail on the scratcher, body hidden", "1075 745 1215 960"),
        14: ("tuxedo", V, "high", "upright tail on the scratcher, body hidden", "1130 745 1255 960"),
        15: ("tuxedo", V, "high", "upright tail on the scratcher, body hidden", "1055 740 1205 960"),
        16: ("tuxedo", V, "high", "upright tail on the scratcher, body hidden", "1055 720 1175 960"),
        17: ("tuxedo", V, "high", "upright tail on the scratcher, body hidden", "1045 750 1165 960"),
        **{i: ("tabby", "uncertain", "low", "tabby motion-blurred at the left", "") for i in rng(18, 23)},
    },
}

TARGET = {
    "commons-cat-plays": "cat_0 tuxedo",
    "commons-cat-jumping-backwards": "cat boxed by the body run (tabby f002-f003, f007-f017; tuxedo otherwise)",
    "commons-black-cat-walking": "cat_0 black",
    "commons-cat-licking-tail": "cat_0",
}


def main() -> None:
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=HERE).stdout.strip()
    rows = []
    for clip, decisions in DECISIONS.items():
        manifest = load_frames_manifest(clip)
        results: dict[str, dict[int, dict]] = {}
        for f in manifest["frames"]:
            i = f["frame_index"]
            vis, conf, cond, note = decisions.get(i, (N, "medium", "occlusion", "tail under body"))
            ref = ""
            src = REFERENCE_SOURCE.get(clip, {}).get(i)
            if src and vis in (V, P):
                method, idx = src
                if method == "box":
                    ref = idx
                    rows.append({
                        "clip_id": clip, "frame_index": i, "timestamp_s": f"{f['timestamp_s']:.4f}", "target_cat": TARGET[clip],
                        "tail_visibility": vis, "tail_identity_confidence": conf, "identity": "tail", "condition": cond, "note": note, "reference_box": ref,
                        "alt_cat": "", "alt_tail_visibility": "", "alt_identity_confidence": "", "alt_note": "", "alt_reference_box": "",
                    })
                    continue
                if method not in results:
                    results[method] = {x["frame_index"]: x for x in json.loads((clip_workdir(clip) / method / "result.json").read_text(encoding="utf-8"))["frames"]}
                fr = results[method].get(idx)
                if fr and fr.get("tail"):
                    ref = " ".join(f"{v:.0f}" for v in fr["tail"]["box"])
            alt = ALT.get(clip, {}).get(i, ("", "", "", "", ""))
            identity = ("tail" if conf in ("high", "medium") else "unresolved") if vis in (V, P) else ""
            rows.append({
                "clip_id": clip, "frame_index": i, "timestamp_s": f"{f['timestamp_s']:.4f}", "target_cat": TARGET[clip],
                "tail_visibility": vis, "tail_identity_confidence": conf, "identity": identity, "condition": cond, "note": note, "reference_box": ref,
                "alt_cat": alt[0], "alt_tail_visibility": alt[1], "alt_identity_confidence": alt[2], "alt_note": alt[3], "alt_reference_box": alt[4],
            })
    out = HERE / "frames.csv"
    with out.open("w", newline="", encoding="utf-8") as h:
        h.write(f"# annotation_protocol_version: 1.3; reviewer_id: claude-809c44f2 (model); frozen_at_commit: {commit}; date: 2026-09-20\n")
        w = csv.DictWriter(h, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    counts: dict[str, dict[str, int]] = {}
    for r in rows:
        counts.setdefault(r["clip_id"], {}).setdefault(r["tail_visibility"], 0)
        counts[r["clip_id"]][r["tail_visibility"]] += 1
    print(json.dumps(counts, indent=1))


if __name__ == "__main__":
    main()
