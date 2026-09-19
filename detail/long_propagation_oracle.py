"""Long one-sided propagation oracle: how far can SAM2 carry an accepted tail mask?

From one accepted frame (seed), propagate the tail mask in one direction for ``n`` frames
with no acceptance rule at all, and record per frame: distance from seed, mask area over
seed area, overlap (IoU) with the previous propagated mask, the SigLIP crop probabilities
on the mask's bounding box, and whether a centreline can be extracted. Overlays are
written for a person to judge against frame truth. Nothing here changes any method.

    python -m detail.long_propagation_oracle --clip commons-cat-jumping-backwards --seed 7 --direction back --n 5 --device cuda
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from detail.grounded_tail_v1 import CLASSIFIER_ID, _crop_probs
from detail.mask_centerline import mask_to_tail_samples
from detail.tail_bridge import _mask_from_logits
from detail.tail_bridge_bidir import _bbox, _seed_mask
from review.common import clip_workdir, frames_dir


def run(clip: str, seed: int, direction: str, n: int, device: str, method: str = "tail_grounded_v3", sample_count: int = 24):
    from sam2.sam2_image_predictor import SAM2ImagePredictor
    from sam2.sam2_video_predictor import SAM2VideoPredictor
    from transformers import AutoModel, AutoProcessor

    work = clip_workdir(clip)
    result = json.loads((work / method / "result.json").read_text(encoding="utf-8"))
    frames = {f["frame_index"]: f for f in result["frames"]}
    seed_frame = frames[seed]
    if not seed_frame.get("tail"):
        raise SystemExit(f"seed frame {seed} has no tail box in {method}")
    fdir = frames_dir(clip)
    predictor = SAM2VideoPredictor.from_pretrained("facebook/sam2.1-hiera-tiny", device=device)
    img_pred = SAM2ImagePredictor.from_pretrained("facebook/sam2.1-hiera-tiny", device=device)
    clf = {"clf_processor": AutoProcessor.from_pretrained(CLASSIFIER_ID), "classifier": AutoModel.from_pretrained(CLASSIFIER_ID).to(device).eval()}
    seed_mask = _seed_mask(img_pred, fdir, seed_frame)
    seed_area = max(int(seed_mask.sum()), 1)
    state = predictor.init_state(video_path=str(fdir))
    predictor.reset_state(state)
    predictor.add_new_mask(inference_state=state, frame_idx=seed, obj_id=1, mask=seed_mask)
    out_dir = work / "longprop" / f"seed{seed:03d}_{direction}"
    (out_dir / "overlays").mkdir(parents=True, exist_ok=True)
    records = []
    prev = seed_mask
    for frame_idx, _ids, logits in predictor.propagate_in_video(state, start_frame_idx=seed, max_frame_num_to_track=n, reverse=(direction == "back")):
        t = int(frame_idx)
        if t == seed:
            continue
        mask = _mask_from_logits(logits)
        area = int(mask.sum())
        inter = np.logical_and(mask, prev).sum(); union = np.logical_or(mask, prev).sum()
        rec = {"frame_index": t, "distance": abs(t - seed), "area_ratio": area / seed_area, "iou_prev": float(inter / union) if union else 0.0, "centreline": False, "siglip": None}
        image = Image.open(fdir / frames[t]["file"]).convert("RGB")
        b = _bbox(mask)
        if b:
            rec["siglip"] = _crop_probs(clf, image, b, device)
            try:
                samples = mask_to_tail_samples(mask, base_xy=tuple(seed_frame["root_xy"]) if seed_frame.get("root_xy") else (b[0], b[1]), sample_count=sample_count)
                rec["centreline"] = True
            except ValueError:
                samples = None
            im = image.convert("RGBA"); ov = np.zeros((*mask.shape, 4), dtype=np.uint8); ov[mask] = (255, 120, 0, 120)
            comp = Image.alpha_composite(im, Image.fromarray(ov, "RGBA")); dr = ImageDraw.Draw(comp)
            if samples:
                dr.line([(s["x_px"], s["y_px"]) for s in samples], fill=(255, 255, 0, 255), width=4)
            lab = f"{clip} f{t:03d} from f{seed:03d} d{rec['distance']} area {rec['area_ratio']:.2f} iou_prev {rec['iou_prev']:.2f}"
            dr.rectangle((8, 8, 8 + 11 * len(lab), 34), fill=(0, 0, 0, 170)); dr.text((14, 14), lab, fill=(255, 255, 255, 255))
            comp.convert("RGB").save(out_dir / "overlays" / frames[t]["file"], quality=90)
        records.append(rec)
        prev = mask
    (out_dir / "records.json").write_text(json.dumps({"clip": clip, "seed": seed, "direction": direction, "records": records}, indent=2, default=float) + "\n", encoding="utf-8")
    return records


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--clip", required=True); p.add_argument("--seed", type=int, required=True)
    p.add_argument("--direction", choices=["back", "forward"], default="back"); p.add_argument("--n", type=int, default=5)
    p.add_argument("--device", default="cpu"); p.add_argument("--method", default="tail_grounded_v3")
    a = p.parse_args()
    for r in run(a.clip, a.seed, a.direction, a.n, a.device, a.method):
        s = r["siglip"] or {}
        print(f"f{r['frame_index']:03d} d{r['distance']} area {r['area_ratio']:.2f} iou_prev {r['iou_prev']:.2f} centreline {r['centreline']} tail {s.get('tail', 0):.2f} paw {s.get('paw', 0):.2f}")


if __name__ == "__main__":
    main()
