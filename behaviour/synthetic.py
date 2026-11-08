"""Synthetic segments for testing the BH1 baselines and scorer. Never used as data.

A "cat" is a bright blob on a noisy background; each class moves it differently:

* walk: steady horizontal translation;
* sit_lie: still;
* groom: still body, a small patch near the top oscillating;
* jump: fast rise and fall;
* play_other: random jitter.

``mode`` picks what the labels depend on:

* ``signal``: labels follow the motion pattern in 80 % of segments (the rest move at random), so a motion classifier should transfer to unseen cats;
* ``null``: labels are drawn at random, independent of the frames;
* ``identity``: each cat does mostly one behaviour and moves in its own idiosyncratic way regardless
  of the label, so a classifier can learn "this cat -> this label" but nothing that transfers.
  This is the audio failure of 2026-08 in miniature, and the negative control for the
  seen-to-unseen drop.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from behaviour.common import CLASSES, FRAMES_PER_SEGMENT

H, W = 36, 48


def _frames(rng: np.random.Generator, pattern: str, size: float, bright: float, x0: float, y0: float, style: float) -> np.ndarray:
    yy, xx = np.mgrid[0:H, 0:W]
    out = []
    phase = rng.uniform(0, 2 * np.pi)
    for t in range(FRAMES_PER_SEGMENT):
        x, y, patch = x0, y0, 0.0
        if pattern == "walk":
            x = x0 + (2.0 + style) * t
        elif pattern == "groom":
            patch = np.sin(phase + 2.5 * t)
        elif pattern == "jump":
            y = y0 - 14 * np.sin(np.pi * t / (FRAMES_PER_SEGMENT - 1))
        elif pattern == "play_other":
            x, y = x0 + rng.normal(0, 3), y0 + rng.normal(0, 3)
        elif pattern.startswith("style"):
            x = x0 + style * 3 * np.sin(t * (1 + style))
            y = y0 + style * 2 * np.cos(t * (1 + style))
        img = rng.normal(0.15, 0.03, (H, W))
        img += bright * (((xx - x) ** 2 + (yy - y) ** 2) < size ** 2)
        if patch:
            img += 0.5 * patch * (((xx - x) ** 2 + (yy - (y - size)) ** 2) < (size / 2) ** 2)
        out.append(np.clip(img, 0, 1))
    return np.stack(out)


def make(n_cats: int = 12, clips_per_cat: int = 9, segs_per_clip: int = 2, mode: str = "signal", seed: int = 0) -> dict[str, Any]:
    """Returns segments, frames (dict seg -> (T, H, W)), truth, clip_of, cat_of and a key like key.json."""
    rng = np.random.default_rng(seed)
    segments, frames, truth, clip_of, cat_of = [], {}, {}, {}, {}
    key = {"clips": {}}
    n = 0
    for c in range(n_cats):
        cat = f"cat{c:02d}"
        size, bright, style = rng.uniform(3, 6), rng.uniform(0.4, 0.8), rng.uniform(0, 1.5)
        favourite = CLASSES[c % len(CLASSES)]
        for _ in range(clips_per_cat):
            n += 1
            clip = f"BH1-C{n:03d}"
            key["clips"][clip] = {"title": f"File:synthetic {n}.webm", "uploader": f"uploader{c % 4}", "cat_id": cat}
            for k in range(segs_per_clip):
                sid = f"{clip}-S{k:02d}"
                if mode == "identity":
                    label = favourite if rng.random() < 0.85 else CLASSES[rng.integers(len(CLASSES))]
                    pattern = "style"
                else:
                    label = CLASSES[rng.integers(len(CLASSES))]
                    pattern = label if mode == "signal" and rng.random() < 0.8 else CLASSES[rng.integers(len(CLASSES))]
                frames[sid] = _frames(rng, pattern, size, bright, rng.uniform(12, 20), rng.uniform(20, 26), style)
                segments.append(sid)
                truth[sid], clip_of[sid], cat_of[sid] = label, clip, cat
    return {"segments": segments, "frames": frames, "truth": truth, "clip_of": clip_of, "cat_of": cat_of, "key": key}
