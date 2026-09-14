"""Figure for note 03: detector coverage (YOLOX-m vs Grounding DINO) and bridging."""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / "review" / "work"
OUT = Path(__file__).resolve().parent / "figures"
TILE = 300

FRAMES = [
    ("commons-cat-jumping-backwards", 16, "Jumping f016: no YOLOX box"),
    ("commons-cat-jumping-backwards", 17, "f017: no YOLOX box"),
    ("commons-cat-jumping-backwards", 14, "f014: no YOLOX box"),
    ("commons-cat-plays", 4, "Cat Plays f004: bridged"),
    ("commons-cat-jumping-backwards", 6, "Jumping f006: bridged"),
]
ROWS = [("tail_anchored", "anchored, grounding detector"), ("tail_grounded_v1", "v1"), ("tail_grounded_v2", "v2 = v1 + bridge")]


def _window(clip: str, index: int):
    frames = json.loads((WORK / clip / "frames.json").read_text(encoding="utf-8"))["frames"]
    body = json.loads((WORK / clip / "body.json").read_text(encoding="utf-8"))
    boxes = {f["frame_index"]: f["bbox_xyxy"] for f in body["frames"] if f["bbox_xyxy"]}
    w, h = frames[0]["width_px"], frames[0]["height_px"]
    side = int(min(max(max(b[2] - b[0], b[3] - b[1]) for b in boxes.values()) * 1.4, w, h))
    b = boxes[min(boxes, key=lambda k: abs(k - index))]
    cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
    x0 = int(min(max(cx - side / 2, 0), w - side))
    y0 = int(min(max(cy - side / 2, 0), h - side))
    return (x0, y0, x0 + side, y0 + side)


def _status(clip: str, method: str, index: int) -> str:
    res = json.loads((WORK / clip / method / "result.json").read_text(encoding="utf-8"))
    return next((f["status"] for f in res["frames"] if f["frame_index"] == index), "?")


def coverage() -> Path:
    label_h = 20
    sheet = Image.new("RGB", (len(FRAMES) * TILE + 150, len(ROWS) * (TILE + label_h) + label_h), (255, 255, 255))
    draw = ImageDraw.Draw(sheet)
    for c, (clip, index, caption) in enumerate(FRAMES):
        draw.text((150 + c * TILE + 3, 4), caption, fill=(0, 0, 0))
        window = _window(clip, index)
        for r, (method, name) in enumerate(ROWS):
            overlay = WORK / clip / "overlays" / method / f"{index:05d}.jpg"
            image = Image.open(overlay if overlay.exists() else WORK / clip / "frames" / f"{index:05d}.jpg").convert("RGB")
            image = image.crop(window).resize((TILE, TILE), Image.LANCZOS)
            if not overlay.exists():
                d = ImageDraw.Draw(image)
                d.rectangle((0, 0, TILE, 18), fill=(180, 30, 30))
                d.text((5, 3), f"refused: {_status(clip, method, index)}", fill=(255, 255, 255))
            y = label_h + r * (TILE + label_h)
            sheet.paste(image, (150 + c * TILE, y + label_h))
            if c == 0:
                draw.text((6, y + label_h + TILE // 2 - 6), name, fill=(0, 0, 0))
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "coverage.jpg"
    sheet.save(path, quality=88)
    return path


if __name__ == "__main__":
    print(coverage())
