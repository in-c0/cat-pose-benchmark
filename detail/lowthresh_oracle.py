"""Low-threshold detector dump: does a tail box exist at all on frames v1 had none for?

Runs Grounding DINO with box threshold 0.05 (text threshold frozen at 0.15) and saves every
detection whose label contains "tail", sorted by score, with no filtering, on two frame
sets: the visible/partial frames where v1 reported ``no_tail_box`` (recovery oracle) and
a set of ``not_visible`` frames (negative control: how many false tail boxes appear per
score band when there is no tail). Draws the top boxes per frame on a sheet for labelling.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw

from detail.grounded_tail import DETECTOR_ID, TEXT_THRESHOLD, pick_cat_box
from review.common import clip_workdir, frames_dir

BANDS = [(0.20, 1.01), (0.15, 0.20), (0.10, 0.15), (0.05, 0.10)]


def detect(processor, detector, image, device, box_threshold):
    inputs = processor(images=image, text="cat. tail.", return_tensors="pt").to(device)
    outputs = detector(**inputs)
    result = processor.post_process_grounded_object_detection(
        outputs, inputs.input_ids, threshold=box_threshold, text_threshold=TEXT_THRESHOLD, target_sizes=[image.size[::-1]]
    )[0]
    labels = result.get("text_labels", result.get("labels"))
    return [{"label": str(l), "score": float(s), "box": [float(v) for v in b]} for s, l, b in zip(result["scores"], labels, result["boxes"])]


def run(frames, output: Path, device: str, box_threshold: float = 0.05, draw_top: int = 6):
    import torch
    from transformers import AutoModelForZeroShotObjectDetection, AutoProcessor

    torch.set_grad_enabled(False)
    processor = AutoProcessor.from_pretrained(DETECTOR_ID)
    detector = AutoModelForZeroShotObjectDetection.from_pretrained(DETECTOR_ID).to(device).eval()
    records, tiles = [], []
    pal = [(0, 255, 255), (255, 255, 0), (255, 0, 255), (0, 255, 0), (255, 128, 0), (128, 128, 255)]
    for clip, i, group in frames:
        image = Image.open(frames_dir(clip) / f"{i:05d}.jpg").convert("RGB")
        body = {f["frame_index"]: f["bbox_xyxy"] for f in json.loads((clip_workdir(clip) / "body.json").read_text(encoding="utf-8"))["frames"]}
        dets = detect(processor, detector, image, device, box_threshold)
        cat = pick_cat_box(dets, body.get(i))
        tails = sorted([d for d in dets if "tail" in d["label"] and d["label"] != "cat tail"], key=lambda d: -d["score"])
        for r, d in enumerate(tails):
            d["rank"] = r + 1
        records.append({"clip_id": clip, "frame_index": i, "group": group, "cat": cat, "tails": tails})
        im = image.copy(); dr = ImageDraw.Draw(im)
        if cat:
            dr.rectangle(cat["box"], outline=(255, 255, 255), width=2)
        for d in tails[:draw_top]:
            col = pal[(d["rank"] - 1) % len(pal)]
            dr.rectangle(d["box"], outline=col, width=3)
            dr.text((d["box"][0] + 3, max(0, d["box"][1] - 12)), f"#{d['rank']} {d['score']:.2f}", fill=col)
        if cat:
            b = cat["box"]; side = max(b[2] - b[0], b[3] - b[1]) * 1.5
            cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
            x0 = int(max(0, min(cx - side / 2, im.width - side))); y0 = int(max(0, min(cy - side / 2, im.height - side)))
            im = im.crop((x0, y0, int(x0 + side), int(y0 + side)))
        im = im.resize((500, 500)); ImageDraw.Draw(im).text((6, 6), f"{group} {clip[8:14]} f{i:03d}", fill=(255, 255, 0)); tiles.append(im)
    output.mkdir(parents=True, exist_ok=True)
    cols = 6
    rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * 500, rows * 500), (40, 40, 40))
    for k, t in enumerate(tiles):
        sheet.paste(t, ((k % cols) * 500, (k // cols) * 500))
    sheet.save(output / "lowthresh-sheet.jpg", quality=85)
    (output / "lowthresh.json").write_text(json.dumps({"box_threshold": box_threshold, "text_threshold": TEXT_THRESHOLD, "frames": records}, indent=2, default=float) + "\n", encoding="utf-8")
    return records


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--frames", action="append", required=True, help="group:clip_id:i,j,k")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--device", default="cpu")
    args = parser.parse_args()
    frames = []
    for spec in args.frames:
        group, clip, idxs = spec.split(":")
        frames += [(clip, int(i), group) for i in idxs.split(",") if i]
    records = run(frames, args.output, args.device)
    for r in records:
        top = [(d["rank"], round(d["score"], 2)) for d in r["tails"][:6]]
        print(r["group"], r["clip_id"][8:14], r["frame_index"], "cat", (round(r["cat"]["score"], 2) if r["cat"] else None), "tails", len(r["tails"]), top)


if __name__ == "__main__":
    main()
