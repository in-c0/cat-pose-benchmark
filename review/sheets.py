"""Build one labelled contact sheet per clip per method for human review."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

from review.common import clip_workdir, frames_dir, load_clips, load_frames_manifest

METHODS = ["body", "tail", "tail_anchored", "tail_grounded", "tail_grounded_v1"]


def _tile(image: Image.Image, width: int) -> Image.Image:
    ratio = width / image.width
    return image.resize((width, int(image.height * ratio)), Image.LANCZOS)


def _crop_windows(clip_id: str, frames: list[dict[str, Any]]) -> dict[int, tuple[int, int, int, int]]:
    """Square crop per frame, centred on the detected cat, one fixed size per clip.

    Uses body.json detections; a frame without a detection borrows the nearest detected
    frame's centre so the reviewer still looks at the right region. A fixed crop size
    keeps scale constant across the sheet. Falls back to the full frame when body.json
    is absent.
    """
    body_path = clip_workdir(clip_id) / "body.json"
    if not body_path.exists():
        return {}
    body = json.loads(body_path.read_text(encoding="utf-8"))
    boxes = {f["frame_index"]: f["bbox_xyxy"] for f in body["frames"] if f["bbox_xyxy"]}
    if not boxes:
        return {}
    width, height = frames[0]["width_px"], frames[0]["height_px"]
    side = max(max(b[2] - b[0], b[3] - b[1]) for b in boxes.values()) * 1.6
    side = int(min(side, width, height))
    windows = {}
    for frame in frames:
        index = frame["frame_index"]
        nearest = min(boxes, key=lambda k: abs(k - index))
        b = boxes[nearest]
        cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
        x0 = int(min(max(cx - side / 2, 0), width - side))
        y0 = int(min(max(cy - side / 2, 0), height - side))
        windows[index] = (x0, y0, x0 + side, y0 + side)
    return windows


def _banner(tile: Image.Image, text: str, *, warn: bool = False) -> None:
    draw = ImageDraw.Draw(tile)
    colour = (180, 30, 30) if warn else (0, 0, 0)
    draw.rectangle((0, 0, tile.width, 22), fill=colour)
    draw.text((6, 5), text, fill=(255, 255, 255))


def build_sheet(
    clip_id: str,
    method: str,
    *,
    columns: int,
    tile_width: int,
    output_path: Path,
    crop: bool = True,
) -> dict[str, Any]:
    manifest = load_frames_manifest(clip_id)
    overlay_dir = clip_workdir(clip_id) / "overlays" / method
    raw_dir = frames_dir(clip_id)

    windows = _crop_windows(clip_id, manifest["frames"]) if crop else {}

    tiles = []
    missing = []
    for frame in manifest["frames"]:
        overlay = overlay_dir / frame["file"]
        label = f"f{frame['frame_index']:03d}  {frame['timestamp_s']:.2f}s"
        if overlay.exists():
            image = Image.open(overlay).convert("RGB")
        else:
            image = Image.open(raw_dir / frame["file"]).convert("RGB")
            missing.append(frame["frame_index"])
        window = windows.get(frame["frame_index"])
        if window:
            image = image.crop(window)
        tile = _tile(image, tile_width)
        if overlay.exists():
            _banner(tile, label)
        else:
            _banner(tile, f"{label}  NO {method.upper()} OUTPUT", warn=True)
        tiles.append(tile)

    tile_height = max(t.height for t in tiles)
    rows = (len(tiles) + columns - 1) // columns
    gap = 6
    sheet = Image.new(
        "RGB",
        (columns * tile_width + (columns + 1) * gap, rows * tile_height + (rows + 1) * gap + 30),
        (40, 40, 40),
    )
    ImageDraw.Draw(sheet).text(
        (gap, 8),
        f"{clip_id} — {method} — {len(tiles)} frames — judge solid points only; hollow = below threshold",
        fill=(255, 255, 255),
    )
    for i, tile in enumerate(tiles):
        r, c = divmod(i, columns)
        x = gap + c * (tile_width + gap)
        y = 30 + gap + r * (tile_height + gap)
        sheet.paste(tile, (x, y))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output_path, quality=85)
    return {
        "clip_id": clip_id,
        "method": method,
        "frames": len(tiles),
        "frames_without_output": missing,
        "sheet": str(output_path),
        "size": sheet.size,
        "cropped": bool(windows),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build review contact sheets.")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--clip", action="append")
    parser.add_argument("--no-crop", action="store_true", help="Show full frames instead of cat-centred crops.")
    args = parser.parse_args()

    for clip in load_clips():
        if args.clip and clip["clip_id"] not in args.clip:
            continue
        for method in METHODS:
            if method == "tail" and "tail_seed" not in clip:
                continue
            first = load_frames_manifest(clip["clip_id"])["frames"][0]
            portrait = first["height_px"] > first["width_px"] and args.no_crop
            info = build_sheet(
                clip["clip_id"],
                method,
                columns=6 if portrait else 5,
                tile_width=360 if portrait else 430,
                output_path=args.output_dir / f"{clip['clip_id']}--{method}.jpg",
                crop=not args.no_crop,
            )
            print(json.dumps(info))


if __name__ == "__main__":
    main()
