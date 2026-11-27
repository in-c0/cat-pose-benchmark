"""Top-K proposal oracle for the grounded tail method.

For a list of (clip, frame) pairs, run the detector once and record every stage a tail
proposal passes through: raw ``tail`` detections, the candidates that survive the score /
centre-in-cat / area / dedup filters, their rank, and the SigLIP crop-check decision on
each. Draw every surviving candidate on the frame, numbered by rank, so a person can
label each one TAIL_USABLE / TAIL_PARTIAL / NOT_TAIL and answer: is the true tail already
among the proposals, and if so where in the pipeline does it die?

    python -m detail.topk_oracle --frames commons-cat-plays:0,1,2 ... --output review/work/oracle
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw

from detail.grounded_tail import MAX_TAIL_TO_CAT_AREA, MIN_TAIL_SCORE, _area, _centre_inside, _detect, _iou, pick_cat_box
from detail.grounded_tail_v1 import _crop_probs, _load_models, looks_like_paw
from review.common import clip_workdir, frames_dir, load_frames_manifest


def stage_filters(detections: list[dict[str, Any]], cat_box: list[float]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """The same filters as ``grounded_tail_v1.tail_candidates`` but recording why each
    raw tail detection was dropped."""
    margin = 0.05 * math.hypot(cat_box[2] - cat_box[0], cat_box[3] - cat_box[1])
    reasons = {"filtered_score": 0, "filtered_centre": 0, "filtered_area": 0, "dedup_removed": 0}
    kept: list[dict[str, Any]] = []
    raw = [d for d in detections if "tail" in d["label"]]
    raw.sort(key=lambda d: -d["score"])
    for d in raw:
        if d["score"] < MIN_TAIL_SCORE:
            d["dropped"] = "filtered_score"; reasons["filtered_score"] += 1; continue
        if not _centre_inside(d["box"], cat_box, margin):
            d["dropped"] = "filtered_centre"; reasons["filtered_centre"] += 1; continue
        if _area(d["box"]) > MAX_TAIL_TO_CAT_AREA * _area(cat_box):
            d["dropped"] = "filtered_area"; reasons["filtered_area"] += 1; continue
        if any(_iou(d["box"], k["box"]) >= 0.7 for k in kept):
            d["dropped"] = "dedup_removed"; reasons["dedup_removed"] += 1; continue
        d["rank"] = len(kept) + 1
        kept.append(d)
    return kept, reasons


def _draw(image: Image.Image, cat: dict[str, Any] | None, kept: list[dict[str, Any]], raw_dropped: list[dict[str, Any]], label: str) -> Image.Image:
    im = image.convert("RGB").copy()
    d = ImageDraw.Draw(im)
    if cat:
        d.rectangle(cat["box"], outline=(255, 255, 255), width=2)
    palette = [(0, 255, 255), (255, 255, 0), (255, 0, 255), (0, 255, 0), (255, 128, 0), (128, 128, 255)]
    for c in raw_dropped:
        d.rectangle(c["box"], outline=(120, 120, 120), width=1)
    for c in kept:
        col = palette[(c["rank"] - 1) % len(palette)]
        d.rectangle(c["box"], outline=col, width=3)
        tag = f"#{c['rank']} {c['score']:.2f}" + (" PAW" if c.get("looks_like_paw") else "")
        d.text((c["box"][0] + 3, max(0, c["box"][1] - 12)), tag, fill=col)
    d.rectangle((6, 6, 6 + 7 * len(label), 22), fill=(0, 0, 0))
    d.text((9, 8), label, fill=(255, 255, 255))
    return im


def run(frames: list[tuple[str, int]], output: Path, device: str, k_max: int = 5) -> dict[str, Any]:
    models = _load_models(device)
    records = []
    tiles = []
    for clip_id, index in frames:
        manifest = load_frames_manifest(clip_id)
        frame = next(f for f in manifest["frames"] if f["frame_index"] == index)
        image = Image.open(frames_dir(clip_id) / frame["file"]).convert("RGB")
        body = json.loads((clip_workdir(clip_id) / "body.json").read_text(encoding="utf-8"))
        prefer = next((f["bbox_xyxy"] for f in body["frames"] if f["frame_index"] == index), None)
        dets = _detect(models["det_processor"], models["detector"], image, device)
        cat = pick_cat_box(dets, prefer)
        rec: dict[str, Any] = {"clip_id": clip_id, "frame_index": index, "cat": cat, "raw_tail_detections": [d for d in dets if "tail" in d["label"]]}
        kept: list[dict[str, Any]] = []
        if cat:
            kept, reasons = stage_filters([dict(d) for d in dets], cat["box"])
            rec["filter_drops"] = reasons
            for c in kept:
                c["crop_probs"] = _crop_probs(models, image, c["box"], device)
                c["looks_like_paw"] = looks_like_paw(c["crop_probs"])
            rec["candidates"] = kept[:k_max]
            rec["n_after_filters"] = len(kept)
        else:
            rec["candidates"] = []
            rec["n_after_filters"] = 0
        records.append(rec)
        raw_dropped = [d for d in rec["raw_tail_detections"] if d.get("dropped")]
        tile = _draw(image, cat, kept[:k_max], raw_dropped, f"{clip_id} f{index:03d}")
        # crop around the cat for legibility
        if cat:
            b = cat["box"]; side = max(b[2] - b[0], b[3] - b[1]) * 1.5
            cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
            x0 = int(max(0, min(cx - side / 2, image.width - side))); y0 = int(max(0, min(cy - side / 2, image.height - side)))
            tile = tile.crop((x0, y0, int(x0 + side), int(y0 + side)))
        tiles.append(tile.resize((480, 480)))
    output.mkdir(parents=True, exist_ok=True)
    cols = 5
    rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * 480, rows * 480), (40, 40, 40))
    for i, t in enumerate(tiles):
        sheet.paste(t, ((i % cols) * 480, (i // cols) * 480))
    sheet.save(output / "oracle-sheet.jpg", quality=85)
    payload = {"k_max": k_max, "frames": records}
    (output / "oracle.json").write_text(json.dumps(payload, indent=2, sort_keys=True, default=float) + "\n", encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Top-K proposal oracle on chosen frames.")
    parser.add_argument("--frames", action="append", required=True, help="clip_id:i,j,k")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--k", type=int, default=5)
    args = parser.parse_args()
    pairs = []
    for spec in args.frames:
        clip, idxs = spec.split(":")
        pairs += [(clip, int(i)) for i in idxs.split(",") if i]
    payload = run(pairs, args.output, args.device, args.k)
    for r in payload["frames"]:
        print(r["clip_id"], r["frame_index"], "raw", len(r["raw_tail_detections"]), "kept", r["n_after_filters"],
              [(c["rank"], round(c["score"], 2), "PAW" if c["looks_like_paw"] else "ok") for c in r["candidates"]], r.get("filter_drops"))


if __name__ == "__main__":
    main()
