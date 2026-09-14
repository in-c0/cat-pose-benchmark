"""Build the paper figures from the review working set (review/work must exist)."""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "review" / "work"
OUT = Path(__file__).resolve().parent / "figures"

METHODS = [("tail", "propagated"), ("tail_anchored", "anchored"), ("tail_grounded", "grounded")]
FRAMES = [
    ("commons-cat-plays", 1, "Cat Plays f001: tail out"),
    ("commons-cat-plays", 12, "Cat Plays f012: tail out"),
    ("commons-cat-plays", 24, "Cat Plays f024: tail tucked"),
    ("commons-cat-jumping-backwards", 11, "Jumping f011: tabby"),
    ("commons-cat-jumping-backwards", 16, "Jumping f016: no YOLOX box"),
    ("commons-cat-jumping-backwards", 21, "Jumping f021: tuxedo"),
]
TILE = 300


def _crop_window(clip: str, index: int) -> tuple[int, int, int, int] | None:
    body = json.loads((WORK / clip / "body.json").read_text(encoding="utf-8"))
    frames = json.loads((WORK / clip / "frames.json").read_text(encoding="utf-8"))["frames"]
    boxes = {f["frame_index"]: f["bbox_xyxy"] for f in body["frames"] if f["bbox_xyxy"]}
    grounded = json.loads((WORK / clip / "tail_grounded" / "result.json").read_text(encoding="utf-8"))
    for f in grounded["frames"]:
        if f.get("cat") and f["frame_index"] not in boxes:
            boxes[f["frame_index"]] = f["cat"]["box"]
    if not boxes:
        return None
    width, height = frames[0]["width_px"], frames[0]["height_px"]
    side = int(min(max(max(b[2] - b[0], b[3] - b[1]) for b in boxes.values()) * 1.5, width, height))
    nearest = min(boxes, key=lambda k: abs(k - index))
    b = boxes[nearest]
    cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
    x0 = int(min(max(cx - side / 2, 0), width - side))
    y0 = int(min(max(cy - side / 2, 0), height - side))
    return (x0, y0, x0 + side, y0 + side)


def method_comparison() -> Path:
    cols = len(FRAMES)
    rows = len(METHODS)
    label_h = 22
    sheet = Image.new("RGB", (cols * TILE + 90, rows * (TILE + label_h) + label_h), (255, 255, 255))
    draw = ImageDraw.Draw(sheet)
    for c, (clip, index, caption) in enumerate(FRAMES):
        draw.text((90 + c * TILE + 4, 4), caption, fill=(0, 0, 0))
        window = _crop_window(clip, index)
        for r, (method, name) in enumerate(METHODS):
            overlay = WORK / clip / "overlays" / method / f"{index:05d}.jpg"
            if overlay.exists():
                image = Image.open(overlay).convert("RGB")
                banner = None
            else:
                image = Image.open(WORK / clip / "frames" / f"{index:05d}.jpg").convert("RGB")
                banner = "no output"
            if window:
                image = image.crop(window)
            image = image.resize((TILE, TILE), Image.LANCZOS)
            if banner:
                d = ImageDraw.Draw(image)
                d.rectangle((0, 0, TILE, 20), fill=(180, 30, 30))
                d.text((6, 4), banner, fill=(255, 255, 255))
            y = label_h + r * (TILE + label_h)
            sheet.paste(image, (90 + c * TILE, y + label_h))
            if c == 0:
                draw.text((6, y + label_h + TILE // 2 - 6), name, fill=(0, 0, 0))
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "method-comparison.jpg"
    sheet.save(path, quality=88)
    return path


if __name__ == "__main__":
    print(method_comparison())
