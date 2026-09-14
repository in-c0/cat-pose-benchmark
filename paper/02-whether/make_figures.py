"""Figures for note 02: v0 vs v1 on the tucked-tail stretch and on the jumping clip."""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / "review" / "work"
OUT = Path(__file__).resolve().parent / "figures"
TILE = 260

FRAMES = [
    ("commons-cat-plays", 5, "Cat Plays f005 tail out"),
    ("commons-cat-plays", 12, "f012 tail out"),
    ("commons-cat-plays", 20, "f020 tail out"),
    ("commons-cat-plays", 1, "f001 tucked"),
    ("commons-cat-plays", 24, "f024 tucked"),
    ("commons-cat-plays", 31, "f031 tucked"),
    ("commons-cat-jumping-backwards", 11, "Jumping f011"),
    ("commons-cat-jumping-backwards", 21, "Jumping f021"),
]
ROWS = [("tail_grounded", "v0"), ("tail_grounded_v1", "v1")]


def _window(clip: str, index: int) -> tuple[int, int, int, int] | None:
    frames = json.loads((WORK / clip / "frames.json").read_text(encoding="utf-8"))["frames"]
    grounded = json.loads((WORK / clip / "tail_grounded" / "result.json").read_text(encoding="utf-8"))
    boxes = {f["frame_index"]: f["cat"]["box"] for f in grounded["frames"] if f.get("cat")}
    if not boxes:
        return None
    w, h = frames[0]["width_px"], frames[0]["height_px"]
    side = int(min(max(max(b[2] - b[0], b[3] - b[1]) for b in boxes.values()) * 1.4, w, h))
    b = boxes[min(boxes, key=lambda k: abs(k - index))]
    cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
    x0 = int(min(max(cx - side / 2, 0), w - side))
    y0 = int(min(max(cy - side / 2, 0), h - side))
    return (x0, y0, x0 + side, y0 + side)


def _status(clip: str, method: str, index: int) -> str:
    res = json.loads((WORK / clip / method / "result.json").read_text(encoding="utf-8"))
    for f in res["frames"]:
        if f["frame_index"] == index:
            return f["status"]
    return "?"


def v0_vs_v1() -> Path:
    label_h = 20
    sheet = Image.new("RGB", (len(FRAMES) * TILE + 40, len(ROWS) * (TILE + label_h) + label_h), (255, 255, 255))
    draw = ImageDraw.Draw(sheet)
    for c, (clip, index, caption) in enumerate(FRAMES):
        draw.text((40 + c * TILE + 3, 4), caption, fill=(0, 0, 0))
        window = _window(clip, index)
        for r, (method, name) in enumerate(ROWS):
            overlay = WORK / clip / "overlays" / method / f"{index:05d}.jpg"
            status = _status(clip, method, index)
            if overlay.exists():
                image = Image.open(overlay).convert("RGB")
            else:
                image = Image.open(WORK / clip / "frames" / f"{index:05d}.jpg").convert("RGB")
            if window:
                image = image.crop(window)
            image = image.resize((TILE, TILE), Image.LANCZOS)
            if not overlay.exists():
                d = ImageDraw.Draw(image)
                d.rectangle((0, 0, TILE, 18), fill=(180, 30, 30))
                d.text((5, 3), f"refused: {status}", fill=(255, 255, 255))
            y = label_h + r * (TILE + label_h)
            sheet.paste(image, (40 + c * TILE, y + label_h))
            if c == 0:
                draw.text((6, y + label_h + TILE // 2 - 6), name, fill=(0, 0, 0))
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "v0-vs-v1.jpg"
    sheet.save(path, quality=88)
    return path


if __name__ == "__main__":
    print(v0_vs_v1())
