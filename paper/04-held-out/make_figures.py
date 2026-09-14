"""Figure for note 04: v0 vs v1 on the held-out licking clip, and dense sampling on Cat Plays."""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / "review" / "work"
OUT = Path(__file__).resolve().parent / "figures"
TILE = 250


def _window(clip: str, index: int):
    frames = json.loads((WORK / clip / "frames.json").read_text(encoding="utf-8"))["frames"]
    body = json.loads((WORK / clip / "body.json").read_text(encoding="utf-8"))
    boxes = {f["frame_index"]: f["bbox_xyxy"] for f in body["frames"] if f["bbox_xyxy"]}
    w, h = frames[0]["width_px"], frames[0]["height_px"]
    side = int(min(max(max(b[2] - b[0], b[3] - b[1]) for b in boxes.values()) * 1.3, w, h))
    b = boxes[min(boxes, key=lambda k: abs(k - index))]
    cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
    x0 = int(min(max(cx - side / 2, 0), w - side)); y0 = int(min(max(cy - side / 2, 0), h - side))
    return (x0, y0, x0 + side, y0 + side)


def _status(clip, method, index):
    res = json.loads((WORK / clip / method / "result.json").read_text(encoding="utf-8"))
    return next((f["status"] for f in res["frames"] if f["frame_index"] == index), "?")


def grid(frames, rows, name, label_w=60):
    label_h = 20
    sheet = Image.new("RGB", (len(frames) * TILE + label_w, len(rows) * (TILE + label_h) + label_h), (255, 255, 255))
    draw = ImageDraw.Draw(sheet)
    for c, (clip, index, caption) in enumerate(frames):
        draw.text((label_w + c * TILE + 3, 4), caption, fill=(0, 0, 0))
        window = _window(clip, index)
        for r, (method, rname) in enumerate(rows):
            overlay = WORK / clip / "overlays" / method / f"{index:05d}.jpg"
            image = Image.open(overlay if overlay.exists() else WORK / clip / "frames" / f"{index:05d}.jpg").convert("RGB")
            image = image.crop(window).resize((TILE, TILE), Image.LANCZOS)
            if not overlay.exists():
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
    lick = "commons-cat-licking-tail"
    print(grid(
        [(lick, 2, "licking f002"), (lick, 20, "f020"), (lick, 27, "f027 tucked"), (lick, 35, "f035 tucked"), (lick, 41, "f041 tucked"), (lick, 51, "f051 tucked"), ("commons-black-cat-walking", 12, "walking f012"), ("commons-black-cat-walking", 31, "walking f031")],
        [("tail_grounded", "v0"), ("tail_grounded_v1", "v1")], "held-out.jpg"))
    dense = "commons-cat-plays-dense"
    print(grid(
        [(dense, 2, "Cat Plays 8 fps f002"), (dense, 8, "f008"), (dense, 14, "f014"), (dense, 18, "f018"), (dense, 22, "f022 tucked"), (dense, 38, "f038"), (dense, 41, "f041"), (dense, 50, "f050 tucked")],
        [("tail_grounded_v1", "v1 @ 8 fps")], "dense.jpg"))
