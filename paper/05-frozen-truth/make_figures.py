"""Figures for note 05: bridging and audit on the development clips, and the prospective
holdout where the rump patch is read as a tail."""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / "review" / "work"
OUT = Path(__file__).resolve().parent / "figures"
TILE = 250


FIXED_WINDOW = {"holdout-cat-playing-taiwan": (0, 0, 720, 720)}  # the rump sits at the left edge, outside the body box


def _window(clip: str, index: int):
    if clip in FIXED_WINDOW:
        return FIXED_WINDOW[clip]
    frames = json.loads((WORK / clip / "frames.json").read_text(encoding="utf-8"))["frames"]
    body = json.loads((WORK / clip / "body.json").read_text(encoding="utf-8"))
    boxes = {f["frame_index"]: f["bbox_xyxy"] for f in body["frames"] if f["bbox_xyxy"]}
    w, h = frames[0]["width_px"], frames[0]["height_px"]
    if not boxes:
        side = min(w, h)
        return ((w - side) // 2, (h - side) // 2, (w - side) // 2 + side, (h - side) // 2 + side)
    side = int(min(max(max(b[2] - b[0], b[3] - b[1]) for b in boxes.values()) * 1.3, w, h))
    b = boxes[min(boxes, key=lambda k: abs(k - index))]
    cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
    x0 = int(min(max(cx - side / 2, 0), w - side))
    y0 = int(min(max(cy - side / 2, 0), h - side))
    return (x0, y0, x0 + side, y0 + side)


def _overlay(clip: str, method: str, index: int) -> Path | None:
    for p in (WORK / clip / "overlays" / method / f"{index:05d}.jpg", WORK / clip / method / "overlays" / f"{index:05d}.jpg"):
        if p.exists():
            return p
    return None


def _status(clip, method, index):
    res = json.loads((WORK / clip / method / "result.json").read_text(encoding="utf-8"))
    return next((f["status"] for f in res["frames"] if f["frame_index"] == index), "?")


def grid(frames, rows, name, label_w=70):
    label_h = 20
    sheet = Image.new("RGB", (len(frames) * TILE + label_w, len(rows) * (TILE + label_h) + label_h), (255, 255, 255))
    draw = ImageDraw.Draw(sheet)
    for c, (clip, index, caption) in enumerate(frames):
        draw.text((label_w + c * TILE + 3, 4), caption, fill=(0, 0, 0))
        window = _window(clip, index)
        for r, (method, rname) in enumerate(rows):
            overlay = _overlay(clip, method, index)
            image = Image.open(overlay or WORK / clip / "frames" / f"{index:05d}.jpg").convert("RGB")
            image = image.crop(window).resize((TILE, TILE), Image.LANCZOS)
            if overlay is None:
                d = ImageDraw.Draw(image)
                d.rectangle((0, 0, TILE, 18), fill=(180, 30, 30))
                d.text((5, 3), f"refused: {_status(clip, method, index)}", fill=(255, 255, 255))
            y = label_h + r * (TILE + label_h)
            sheet.paste(image, (label_w + c * TILE, y + label_h))
            if c == 0:
                draw.text((6, y + label_h + TILE // 2 - 6), rname, fill=(0, 0, 0))
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    sheet.save(path, quality=88)
    return path


if __name__ == "__main__":
    j, w, p = "commons-cat-jumping-backwards", "commons-black-cat-walking", "commons-cat-plays"
    print(grid(
        [(j, 13, "jumping f013"), (j, 14, "f014"), (j, 15, "f015"), (w, 31, "walking f031"), (w, 32, "f032"), (j, 19, "jumping f019 hidden"), (p, 4, "Cat Plays f004"), (p, 6, "f006 hidden")],
        [("tail_grounded_v1", "v1"), ("tail_grounded_v3", "v3")], "bridge.jpg"))
    print(grid(
        [(w, 6, "walking f006"), (w, 7, "f007"), (p, 6, "Cat Plays f006 hidden"), (j, 10, "jumping f010")],
        [("tail_grounded_v3", "v3"), ("tail_grounded_v3a", "v3a audit")], "audit.jpg"))
    t, l, d = "holdout-cat-playing-taiwan", "holdout-larry-nails", "holdout-dejeuner-des-minet-1906"
    print(grid(
        [(t, 22, "Taiwan f022 tail visible"), (t, 23, "f023"), (t, 28, "f028"), (t, 34, "f034"), (t, 39, "f039"), (l, 10, "Larry f010"), (l, 30, "f030"), (d, 20, "Déjeuner f020 no cat")],
        [("tail_grounded_v1", "v1"), ("tail_grounded_v3", "v3")], "holdout.jpg"))
