from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image


class YouTubeVISAdapterError(ValueError):
    pass


SELECTION_RULE_VERSION = "ID1-YTVIS-select-v0"
OUTPUT_SCHEMA_VERSION = "ID1-YTVIS-DAVIS-v0"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_annotations(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise YouTubeVISAdapterError("YouTube-VIS annotations must be a JSON object")
    for key in ("videos", "annotations", "categories"):
        if not isinstance(raw.get(key), list):
            raise YouTubeVISAdapterError(f"YouTube-VIS annotations missing list field: {key}")
    return raw


def resolve_category_id(data: dict[str, Any], category_name: str = "cat") -> int:
    wanted = str(category_name).strip().casefold()
    if not wanted:
        raise YouTubeVISAdapterError("category name cannot be empty")
    matches: list[int] = []
    for item in data.get("categories", []):
        if not isinstance(item, dict):
            continue
        if str(item.get("name", "")).strip().casefold() != wanted:
            continue
        try:
            matches.append(int(item["id"]))
        except Exception as exc:
            raise YouTubeVISAdapterError("matching category has no integer id") from exc
    if len(matches) != 1:
        raise YouTubeVISAdapterError(
            f"expected exactly one category named {category_name!r}, found {len(matches)}"
        )
    return matches[0]


def _video_index(data: dict[str, Any]) -> dict[int, dict[str, Any]]:
    out: dict[int, dict[str, Any]] = {}
    for raw in data.get("videos", []):
        if not isinstance(raw, dict):
            raise YouTubeVISAdapterError("video entry must be an object")
        try:
            video_id = int(raw["id"])
        except Exception as exc:
            raise YouTubeVISAdapterError("video entry missing integer id") from exc
        if video_id in out:
            raise YouTubeVISAdapterError(f"duplicate video id: {video_id}")
        out[video_id] = raw
    return out


def _validate_video(video: dict[str, Any]) -> tuple[int, int, int, list[str]]:
    try:
        width = int(video["width"])
        height = int(video["height"])
        length = int(video["length"])
    except Exception as exc:
        raise YouTubeVISAdapterError("video width/height/length must be integers") from exc
    names = video.get("file_names")
    if width <= 0 or height <= 0 or length <= 0:
        raise YouTubeVISAdapterError("video width/height/length must be positive")
    if not isinstance(names, list) or len(names) != length:
        raise YouTubeVISAdapterError(
            f"video file_names length mismatch: expected {length}, got "
            f"{len(names) if isinstance(names, list) else 'non-list'}"
        )
    file_names = [str(x).strip() for x in names]
    if any(not name for name in file_names):
        raise YouTubeVISAdapterError("video file_names contains an empty path")
    return width, height, length, file_names


def _annotations_for_video(
    data: dict[str, Any], *, video_id: int, category_id: int
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen_ids: set[int] = set()
    for raw in data.get("annotations", []):
        if not isinstance(raw, dict):
            raise YouTubeVISAdapterError("annotation entry must be an object")
        try:
            ann_video_id = int(raw["video_id"])
            ann_category_id = int(raw["category_id"])
            ann_id = int(raw["id"])
        except Exception as exc:
            raise YouTubeVISAdapterError(
                "annotation id/video_id/category_id must be integers"
            ) from exc
        if ann_id in seen_ids:
            raise YouTubeVISAdapterError(f"duplicate annotation id: {ann_id}")
        seen_ids.add(ann_id)
        if ann_video_id == int(video_id) and ann_category_id == int(category_id):
            out.append(raw)
    return sorted(out, key=lambda row: int(row["id"]))


def _seg_visible(seg: Any) -> bool:
    if seg is None:
        return False
    if isinstance(seg, dict):
        counts = seg.get("counts", None)
        if counts is None:
            return False
        if isinstance(counts, (list, tuple)):
            return any(int(x) != 0 for x in counts)
        return bool(str(counts))
    if isinstance(seg, list):
        return bool(seg)
    return True


def _internal_gap_lengths(indices: list[int]) -> list[int]:
    if len(indices) < 2:
        return []
    return [b - a - 1 for a, b in zip(indices, indices[1:]) if b - a > 1]


def _bbox_iou_xywh(a: Any, b: Any) -> float:
    if not isinstance(a, (list, tuple)) or not isinstance(b, (list, tuple)):
        return 0.0
    if len(a) < 4 or len(b) < 4:
        return 0.0
    ax, ay, aw, ah = [float(v) for v in a[:4]]
    bx, by, bw, bh = [float(v) for v in b[:4]]
    if aw <= 0 or ah <= 0 or bw <= 0 or bh <= 0:
        return 0.0
    ax2, ay2 = ax + aw, ay + ah
    bx2, by2 = bx + bw, by + bh
    ix1, iy1 = max(ax, bx), max(ay, by)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    union = aw * ah + bw * bh - inter
    return 0.0 if union <= 0 else inter / union


def _validate_track_lengths(track: dict[str, Any], expected_length: int) -> None:
    segs = track.get("segmentations", None)
    if not isinstance(segs, list) or len(segs) != expected_length:
        raise YouTubeVISAdapterError(
            f"annotation {track.get('id')} segmentations length mismatch: "
            f"expected {expected_length}, got "
            f"{len(segs) if isinstance(segs, list) else 'non-list'}"
        )
    bboxes = track.get("bboxes", None)
    if bboxes is not None and (not isinstance(bboxes, list) or len(bboxes) != expected_length):
        raise YouTubeVISAdapterError(
            f"annotation {track.get('id')} bboxes length mismatch: expected {expected_length}"
        )


def candidate_stats(
    data: dict[str, Any], *, video_id: int, category_name: str = "cat"
) -> dict[str, Any]:
    category_id = resolve_category_id(data, category_name)
    videos = _video_index(data)
    if int(video_id) not in videos:
        raise YouTubeVISAdapterError(f"unknown video id: {video_id}")
    video = videos[int(video_id)]
    width, height, length, _ = _validate_video(video)
    tracks = _annotations_for_video(data, video_id=int(video_id), category_id=category_id)
    for track in tracks:
        _validate_track_lengths(track, length)

    per_track_visible: dict[int, list[int]] = {}
    for track in tracks:
        ann_id = int(track["id"])
        per_track_visible[ann_id] = [
            i for i, seg in enumerate(track["segmentations"]) if _seg_visible(seg)
        ]

    visible_sets = {ann_id: set(indices) for ann_id, indices in per_track_visible.items()}
    co_visible_frames = 0
    bbox_overlap_frames = 0
    for frame_idx in range(length):
        visible_tracks = [
            track
            for track in tracks
            if frame_idx in visible_sets[int(track["id"])]
        ]
        if len(visible_tracks) >= 2:
            co_visible_frames += 1
        overlapping = False
        for i, left in enumerate(visible_tracks):
            lb = left.get("bboxes", [None] * length)[frame_idx] if left.get("bboxes") is not None else None
            for right in visible_tracks[i + 1 :]:
                rb = right.get("bboxes", [None] * length)[frame_idx] if right.get("bboxes") is not None else None
                if _bbox_iou_xywh(lb, rb) > 0:
                    overlapping = True
                    break
            if overlapping:
                break
        if overlapping:
            bbox_overlap_frames += 1

    gaps = [
        gap
        for indices in per_track_visible.values()
        for gap in _internal_gap_lengths(indices)
    ]
    visible_track_frames = sum(len(v) for v in per_track_visible.values())
    max_internal_gap = max(gaps, default=0)

    hints: list[str] = []
    if co_visible_frames > 0:
        hints.append("ordinary_continuity")
    if any(gap in {1, 2} for gap in gaps):
        hints.append("short_occlusion_candidate")
    if any(gap >= 3 for gap in gaps):
        hints.append("long_gap_reentry_candidate")
    if bbox_overlap_frames > 0:
        hints.append("crossing_close_interaction_candidate")

    return {
        "video_id": int(video_id),
        "width": width,
        "height": height,
        "length": length,
        "category_name": category_name,
        "category_id": category_id,
        "cat_instance_count": len(tracks),
        "annotation_ids": [int(t["id"]) for t in tracks],
        "visible_track_frames": visible_track_frames,
        "co_visible_frames": co_visible_frames,
        "bbox_overlap_frames": bbox_overlap_frames,
        "max_internal_gap_frames": max_internal_gap,
        "per_track_visible_frames": {
            str(k): len(v) for k, v in sorted(per_track_visible.items())
        },
        "stress_stratum_hints": hints,
    }


def inspect_candidates(
    data: dict[str, Any], *, category_name: str = "cat", min_instances: int = 2
) -> list[dict[str, Any]]:
    if min_instances < 1:
        raise YouTubeVISAdapterError("min_instances must be >= 1")
    videos = _video_index(data)
    candidates: list[dict[str, Any]] = []
    for video_id in sorted(videos):
        stats = candidate_stats(data, video_id=video_id, category_name=category_name)
        if stats["cat_instance_count"] >= min_instances:
            candidates.append(stats)
    candidates.sort(
        key=lambda row: (
            -int(row["cat_instance_count"]),
            -int(row["co_visible_frames"]),
            -int(row["max_internal_gap_frames"]),
            -int(row["bbox_overlap_frames"]),
            -int(row["visible_track_frames"]),
            int(row["video_id"]),
        )
    )
    for rank, row in enumerate(candidates, start=1):
        row["selection_rank"] = rank
        row["selection_rule_version"] = SELECTION_RULE_VERSION
    return candidates


def _decode_compressed_counts(encoded: str) -> list[int]:
    counts: list[int] = []
    p = 0
    while p < len(encoded):
        x = 0
        k = 0
        more = True
        while more:
            if p >= len(encoded):
                raise YouTubeVISAdapterError("truncated COCO compressed RLE")
            c = ord(encoded[p]) - 48
            if c < 0 or c > 63:
                raise YouTubeVISAdapterError("invalid COCO compressed RLE character")
            x |= (c & 0x1F) << (5 * k)
            more = bool(c & 0x20)
            p += 1
            k += 1
            if not more and (c & 0x10):
                x |= -1 << (5 * k)
        if len(counts) > 2:
            x += counts[-2]
        if x < 0:
            raise YouTubeVISAdapterError("COCO RLE decoded to a negative run length")
        counts.append(int(x))
    return counts


def _mask_from_counts(counts: list[int], *, height: int, width: int) -> np.ndarray:
    total = int(height) * int(width)
    if any(int(c) < 0 for c in counts):
        raise YouTubeVISAdapterError("COCO RLE contains a negative run length")
    if sum(int(c) for c in counts) != total:
        raise YouTubeVISAdapterError(
            f"COCO RLE length mismatch: runs sum to {sum(int(c) for c in counts)}, expected {total}"
        )
    flat = np.zeros(total, dtype=np.uint8)
    cursor = 0
    value = 0
    for raw_count in counts:
        count = int(raw_count)
        if value == 1 and count:
            flat[cursor : cursor + count] = 1
        cursor += count
        value = 1 - value
    return flat.reshape((height, width), order="F").astype(bool, copy=False)


def _decode_polygon_exact(segmentation: list[Any], *, height: int, width: int) -> np.ndarray:
    try:
        from pycocotools import mask as mask_utils  # type: ignore
    except Exception as exc:
        raise YouTubeVISAdapterError(
            "polygon segmentation requires pycocotools for exact COCO rasterisation"
        ) from exc
    try:
        rles = mask_utils.frPyObjects(segmentation, height, width)
        merged = mask_utils.merge(rles)
        decoded = mask_utils.decode(merged)
    except Exception as exc:
        raise YouTubeVISAdapterError("failed to rasterise COCO polygon segmentation") from exc
    arr = np.asarray(decoded)
    if arr.ndim == 3:
        arr = np.any(arr > 0, axis=2)
    return (arr > 0).astype(bool, copy=False)


def decode_segmentation(segmentation: Any, *, height: int, width: int) -> np.ndarray:
    if segmentation is None:
        return np.zeros((height, width), dtype=bool)
    if isinstance(segmentation, dict):
        size = segmentation.get("size", None)
        if not isinstance(size, (list, tuple)) or len(size) != 2:
            raise YouTubeVISAdapterError("COCO RLE missing [height, width] size")
        if [int(size[0]), int(size[1])] != [int(height), int(width)]:
            raise YouTubeVISAdapterError(
                f"COCO RLE size mismatch: {size} != [{height}, {width}]"
            )
        counts_raw = segmentation.get("counts", None)
        if isinstance(counts_raw, list):
            counts = [int(v) for v in counts_raw]
        elif isinstance(counts_raw, str):
            counts = _decode_compressed_counts(counts_raw)
        else:
            raise YouTubeVISAdapterError("COCO RLE counts must be a list or compressed string")
        return _mask_from_counts(counts, height=height, width=width)
    if isinstance(segmentation, list):
        if not segmentation:
            return np.zeros((height, width), dtype=bool)
        return _decode_polygon_exact(segmentation, height=height, width=width)
    raise YouTubeVISAdapterError(
        f"unsupported YouTube-VIS segmentation type: {type(segmentation).__name__}"
    )


def _safe_source_frame(frames_root: Path, relative_name: str) -> Path:
    root = frames_root.expanduser().resolve()
    candidate = (root / relative_name).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise YouTubeVISAdapterError(
            f"frame path escapes frames root: {relative_name!r}"
        ) from exc
    if not candidate.is_file():
        raise FileNotFoundError(f"YouTube-VIS frame not found: {candidate}")
    return candidate


def _assert_output_dir_empty(output_dir: Path) -> None:
    if output_dir.exists() and any(output_dir.iterdir()):
        raise YouTubeVISAdapterError(f"output directory is not empty: {output_dir}")


def convert_video(
    *,
    annotations_path: Path,
    frames_root: Path,
    output_dir: Path,
    video_id: int | None = None,
    category_name: str = "cat",
    min_instances: int = 2,
    sequence_name: str | None = None,
    source_uri: str | None = None,
) -> dict[str, Any]:
    data = load_annotations(annotations_path)
    candidates = inspect_candidates(
        data, category_name=category_name, min_instances=min_instances
    )
    if not candidates:
        raise YouTubeVISAdapterError(
            f"no {category_name!r} videos contain at least {min_instances} persistent instances"
        )
    if video_id is None:
        selected_stats = candidates[0]
        video_id = int(selected_stats["video_id"])
    else:
        matches = [row for row in candidates if int(row["video_id"]) == int(video_id)]
        if not matches:
            raise YouTubeVISAdapterError(
                f"video {video_id} is not eligible under {SELECTION_RULE_VERSION}"
            )
        selected_stats = matches[0]

    category_id = resolve_category_id(data, category_name)
    videos = _video_index(data)
    video = videos[int(video_id)]
    width, height, length, source_names = _validate_video(video)
    tracks = _annotations_for_video(
        data, video_id=int(video_id), category_id=category_id
    )
    if len(tracks) > 255:
        raise YouTubeVISAdapterError(
            f"DAVIS uint8 mask supports at most 255 foreground instances, got {len(tracks)}"
        )
    for track in tracks:
        _validate_track_lengths(track, length)
        if int(track["video_id"]) != int(video_id):
            raise YouTubeVISAdapterError("annotation/video identity mismatch")
        if int(track["category_id"]) != int(category_id):
            raise YouTubeVISAdapterError("annotation/category identity mismatch")

    output_dir = output_dir.expanduser().resolve()
    _assert_output_dir_empty(output_dir)
    frames_out = output_dir / "frames"
    annotations_out = output_dir / "annotations"
    frames_out.mkdir(parents=True, exist_ok=True)
    annotations_out.mkdir(parents=True, exist_ok=True)

    stable_id_by_annotation = {
        int(track["id"]): index
        for index, track in enumerate(tracks, start=1)
    }
    canonical_frame_names: list[str] = []
    source_frame_records: list[dict[str, Any]] = []
    mask_records: list[dict[str, Any]] = []

    for frame_idx, source_name in enumerate(source_names):
        source_path = _safe_source_frame(frames_root, source_name)
        suffix = source_path.suffix.lower() or ".jpg"
        canonical_name = f"frame_{frame_idx:06d}{suffix}"
        target_frame = frames_out / canonical_name
        shutil.copy2(source_path, target_frame)
        with Image.open(target_frame) as image:
            if image.size != (width, height):
                raise YouTubeVISAdapterError(
                    f"frame {source_name!r} size {image.size} != declared {(width, height)}"
                )
        canonical_frame_names.append(canonical_name)
        source_frame_records.append(
            {
                "index": frame_idx,
                "source_name": source_name,
                "source_sha256": sha256_file(source_path),
                "canonical_name": canonical_name,
                "canonical_sha256": sha256_file(target_frame),
            }
        )

        label_mask = np.zeros((height, width), dtype=np.uint8)
        visible_ids: list[int] = []
        for track in tracks:
            seg = track["segmentations"][frame_idx]
            if not _seg_visible(seg):
                continue
            object_mask = decode_segmentation(seg, height=height, width=width)
            if object_mask.shape != label_mask.shape:
                raise YouTubeVISAdapterError("decoded segmentation shape mismatch")
            overlap = object_mask & (label_mask > 0)
            if np.any(overlap):
                raise YouTubeVISAdapterError(
                    f"overlapping instance masks at video {video_id} frame {frame_idx}; "
                    "cannot convert to single-label DAVIS mask without changing ground truth"
                )
            stable_id = stable_id_by_annotation[int(track["id"])]
            label_mask[object_mask] = np.uint8(stable_id)
            visible_ids.append(stable_id)

        mask_path = annotations_out / f"frame_{frame_idx:06d}.png"
        Image.fromarray(label_mask).save(mask_path)
        mask_records.append(
            {
                "index": frame_idx,
                "mask_name": mask_path.name,
                "mask_sha256": sha256_file(mask_path),
                "visible_stable_ids": visible_ids,
            }
        )

    seq = str(sequence_name or f"youtubevis_{int(video_id)}").strip()
    if not seq:
        raise YouTubeVISAdapterError("sequence name cannot be empty")
    meta = {
        "sequence": seq,
        "davis_res": "raw",
        "frame_names": canonical_frame_names,
        "id_to_label": {
            str(stable_id): f"{category_name}_{stable_id}"
            for stable_id in stable_id_by_annotation.values()
        },
        "source_dataset": "YouTube-VIS",
        "source_video_id": int(video_id),
    }
    meta_path = output_dir / "meta.json"
    meta_path.write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    manifest = {
        "schema_version": OUTPUT_SCHEMA_VERSION,
        "selection_rule_version": SELECTION_RULE_VERSION,
        "dataset": "YouTube-VIS",
        "source_uri": source_uri,
        "source_annotations_name": annotations_path.name,
        "source_annotations_sha256": sha256_file(annotations_path),
        "category_name": category_name,
        "category_id": int(category_id),
        "video_id": int(video_id),
        "width": width,
        "height": height,
        "frame_count": length,
        "stable_id_by_source_annotation_id": {
            str(source_id): int(stable_id)
            for source_id, stable_id in stable_id_by_annotation.items()
        },
        "candidate_stats_before_scoring": selected_stats,
        "frames": source_frame_records,
        "masks": mask_records,
        "meta_sha256": sha256_file(meta_path),
        "quantitative_ready_for_remind_davis": True,
        "claims": {
            "persistent_ids_come_from_source_annotations": True,
            "remind_scoring_performed": False,
            "intent_inference_performed": False,
        },
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest


def _write_json(path: Path | None, payload: Any) -> None:
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if path is None:
        print(text, end="")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Inspect and convert YouTube-VIS cat tracks for ID1 REMIND DAVIS evaluation."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    inspect_parser = sub.add_parser("inspect", help="Rank feline videos using data-only pre-score criteria.")
    inspect_parser.add_argument("--annotations", required=True, type=Path)
    inspect_parser.add_argument("--category-name", default="cat")
    inspect_parser.add_argument("--min-instances", type=int, default=2)
    inspect_parser.add_argument("--output", type=Path, default=None)

    convert_parser = sub.add_parser("convert", help="Convert one feline video into REMIND's DAVIS-style input.")
    convert_parser.add_argument("--annotations", required=True, type=Path)
    convert_parser.add_argument("--frames-root", required=True, type=Path)
    convert_parser.add_argument("--output-dir", required=True, type=Path)
    convert_parser.add_argument("--video-id", type=int, default=None)
    convert_parser.add_argument("--category-name", default="cat")
    convert_parser.add_argument("--min-instances", type=int, default=2)
    convert_parser.add_argument("--sequence-name", default=None)
    convert_parser.add_argument("--source-uri", default=None)

    args = parser.parse_args()
    if args.command == "inspect":
        data = load_annotations(args.annotations)
        payload = {
            "schema_version": "ID1-YTVIS-candidates-v0",
            "selection_rule_version": SELECTION_RULE_VERSION,
            "category_name": args.category_name,
            "min_instances": args.min_instances,
            "source_annotations_sha256": sha256_file(args.annotations),
            "candidates": inspect_candidates(
                data,
                category_name=args.category_name,
                min_instances=args.min_instances,
            ),
            "remind_scoring_performed": False,
        }
        _write_json(args.output, payload)
        return 0

    if args.command == "convert":
        manifest = convert_video(
            annotations_path=args.annotations,
            frames_root=args.frames_root,
            output_dir=args.output_dir,
            video_id=args.video_id,
            category_name=args.category_name,
            min_instances=args.min_instances,
            sequence_name=args.sequence_name,
            source_uri=args.source_uri,
        )
        print(json.dumps(manifest, indent=2, sort_keys=True))
        return 0

    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
