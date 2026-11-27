from __future__ import annotations

import argparse
import io
import json
import shutil
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

import numpy as np
from PIL import Image

from identity.youtubevis_adapter import SELECTION_RULE_VERSION, sha256_file


class YouTubeVOSArchiveError(ValueError):
    pass


OUTPUT_SCHEMA_VERSION = "ID1-YTVOS-DAVIS-v0"
SOURCE_DATASET = "YouTube-VOS-2019"
SOURCE_FORMAT = "youtube_vos_indexed_png_v0"


def _normalise_member(name: str) -> str:
    text = str(name).replace("\\", "/")
    path = PurePosixPath(text)
    if not text or path.is_absolute() or ".." in path.parts:
        raise YouTubeVOSArchiveError(f"unsafe ZIP member path: {name!r}")
    return str(path)


def _member_index(zf: zipfile.ZipFile) -> set[str]:
    out: set[str] = set()
    for raw in zf.namelist():
        name = _normalise_member(raw)
        if name in out:
            raise YouTubeVOSArchiveError(f"duplicate ZIP member path: {name}")
        out.add(name)
    return out


def locate_meta_member(zf: zipfile.ZipFile) -> str:
    matches: list[str] = []
    for raw in zf.namelist():
        name = _normalise_member(raw)
        p = PurePosixPath(name)
        if p.name == "meta.json" and "Annotations" not in p.parts:
            matches.append(name)
    if len(matches) != 1:
        raise YouTubeVOSArchiveError(
            f"expected exactly one source meta.json in archive, found {len(matches)}"
        )
    return matches[0]


def read_meta_from_archive(zf: zipfile.ZipFile, member: str) -> dict[str, Any]:
    try:
        raw = json.loads(zf.read(member).decode("utf-8"))
    except Exception as exc:
        raise YouTubeVOSArchiveError(f"failed to read {member} from archive") from exc
    if not isinstance(raw, dict) or not isinstance(raw.get("videos"), dict):
        raise YouTubeVOSArchiveError("YouTube-VOS meta.json must contain object field 'videos'")
    return raw


def _frame_sort_key(value: str) -> tuple[int, int | str, str]:
    text = str(value).strip()
    if text.isdigit():
        return (0, int(text), text)
    return (1, text, text)


def _validate_frame_id(value: Any) -> str:
    text = str(value).strip()
    p = PurePosixPath(text)
    if not text or p.is_absolute() or len(p.parts) != 1 or ".." in p.parts:
        raise YouTubeVOSArchiveError(f"unsafe frame id: {value!r}")
    if text.endswith((".jpg", ".jpeg", ".png")):
        text = PurePosixPath(text).stem
    if not text:
        raise YouTubeVOSArchiveError(f"empty frame id: {value!r}")
    return text


def _video_objects(meta: dict[str, Any], *, video_id: str) -> dict[int, dict[str, Any]]:
    videos = meta.get("videos", {})
    if video_id not in videos:
        raise YouTubeVOSArchiveError(f"unknown source video: {video_id}")
    video = videos[video_id]
    if not isinstance(video, dict) or not isinstance(video.get("objects"), dict):
        raise YouTubeVOSArchiveError(f"video {video_id!r} has no object map")
    out: dict[int, dict[str, Any]] = {}
    for raw_id, raw_obj in video["objects"].items():
        try:
            object_id = int(raw_id)
        except Exception as exc:
            raise YouTubeVOSArchiveError(
                f"video {video_id!r} has non-integer object id {raw_id!r}"
            ) from exc
        if not 1 <= object_id <= 255:
            raise YouTubeVOSArchiveError(
                f"video {video_id!r} object id {object_id} is outside uint8 indexed-mask range"
            )
        if object_id in out:
            raise YouTubeVOSArchiveError(f"duplicate object id {object_id} in {video_id}")
        if not isinstance(raw_obj, dict):
            raise YouTubeVOSArchiveError(f"object {object_id} in {video_id} must be an object")
        category = str(raw_obj.get("category", "")).strip()
        frames_raw = raw_obj.get("frames")
        if not category or not isinstance(frames_raw, list) or not frames_raw:
            raise YouTubeVOSArchiveError(
                f"object {object_id} in {video_id} requires category and non-empty frames"
            )
        frames = [_validate_frame_id(v) for v in frames_raw]
        if len(frames) != len(set(frames)):
            raise YouTubeVOSArchiveError(
                f"object {object_id} in {video_id} contains duplicate frame ids"
            )
        out[object_id] = {
            "category": category,
            "frames": sorted(frames, key=_frame_sort_key),
        }
    return out


def _eligible_object_ids(
    meta: dict[str, Any], *, video_id: str, category_name: str
) -> tuple[list[int], dict[int, dict[str, Any]]]:
    objects = _video_objects(meta, video_id=video_id)
    wanted = str(category_name).strip().casefold()
    ids = [
        object_id
        for object_id, obj in objects.items()
        if str(obj["category"]).strip().casefold() == wanted
    ]
    return sorted(ids), objects


def _root_from_meta_member(meta_member: str) -> str:
    parent = str(PurePosixPath(meta_member).parent)
    return "" if parent == "." else parent


def _join_member(root: str, *parts: str) -> str:
    p = PurePosixPath(root) if root else PurePosixPath()
    for part in parts:
        p = p / str(part)
    return _normalise_member(str(p))


def _annotation_member(
    members: set[str], *, root: str, video_id: str, frame_id: str
) -> str:
    expected = _join_member(root, "Annotations", video_id, f"{frame_id}.png")
    if expected not in members:
        raise YouTubeVOSArchiveError(f"missing source annotation mask: {expected}")
    return expected


def _image_member(
    members: set[str], *, root: str, video_id: str, frame_id: str
) -> str:
    candidates = [
        _join_member(root, "JPEGImages", video_id, f"{frame_id}.jpg"),
        _join_member(root, "JPEGImages", video_id, f"{frame_id}.jpeg"),
        _join_member(root, "JPEGImages", video_id, f"{frame_id}.png"),
    ]
    hits = [name for name in candidates if name in members]
    if len(hits) != 1:
        raise YouTubeVOSArchiveError(
            f"expected exactly one source image for {video_id}/{frame_id}, found {len(hits)}"
        )
    return hits[0]


def _read_indexed_mask(zf: zipfile.ZipFile, member: str) -> np.ndarray:
    try:
        with Image.open(io.BytesIO(zf.read(member))) as image:
            arr = np.asarray(image)
    except Exception as exc:
        raise YouTubeVOSArchiveError(f"failed to read indexed mask {member}") from exc
    if arr.ndim != 2:
        raise YouTubeVOSArchiveError(
            f"indexed annotation mask {member} must be 2-D, got shape {arr.shape}"
        )
    if not np.issubdtype(arr.dtype, np.integer):
        raise YouTubeVOSArchiveError(f"indexed annotation mask {member} is not integer-valued")
    return arr.astype(np.int32, copy=False)


def _bbox(mask: np.ndarray) -> tuple[int, int, int, int] | None:
    ys, xs = np.nonzero(mask)
    if len(xs) == 0:
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def _bbox_intersects(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> bool:
    return min(a[2], b[2]) > max(a[0], b[0]) and min(a[3], b[3]) > max(a[1], b[1])


def candidate_stats(
    zf: zipfile.ZipFile,
    *,
    meta: dict[str, Any],
    meta_member: str,
    members: set[str],
    video_id: str,
    category_name: str = "cat",
) -> dict[str, Any]:
    object_ids, objects = _eligible_object_ids(
        meta, video_id=video_id, category_name=category_name
    )
    root = _root_from_meta_member(meta_member)
    frame_sets = {
        object_id: set(objects[object_id]["frames"])
        for object_id in object_ids
    }
    all_frames = sorted(
        set().union(*(frame_sets.values() or [set()])),
        key=_frame_sort_key,
    )
    frame_position = {frame: idx for idx, frame in enumerate(all_frames)}

    per_track_positions = {
        object_id: sorted(frame_position[frame] for frame in frames)
        for object_id, frames in frame_sets.items()
    }
    gaps = [
        b - a - 1
        for positions in per_track_positions.values()
        for a, b in zip(positions, positions[1:])
        if b - a > 1
    ]
    co_visible = [
        frame
        for frame in all_frames
        if sum(frame in frames for frames in frame_sets.values()) >= 2
    ]

    bbox_overlap_frames = 0
    for frame in co_visible:
        mask_member = _annotation_member(
            members, root=root, video_id=video_id, frame_id=frame
        )
        arr = _read_indexed_mask(zf, mask_member)
        visible_ids = [oid for oid in object_ids if frame in frame_sets[oid]]
        boxes: list[tuple[int, int, int, int]] = []
        for object_id in visible_ids:
            box = _bbox(arr == int(object_id))
            if box is None:
                raise YouTubeVOSArchiveError(
                    f"metadata/mask mismatch: video {video_id} object {object_id} "
                    f"declared visible at {frame} but absent from {mask_member}"
                )
            boxes.append(box)
        if any(
            _bbox_intersects(left, right)
            for idx, left in enumerate(boxes)
            for right in boxes[idx + 1 :]
        ):
            bbox_overlap_frames += 1

    for frame in all_frames:
        if frame in co_visible:
            continue
        mask_member = _annotation_member(
            members, root=root, video_id=video_id, frame_id=frame
        )
        arr = _read_indexed_mask(zf, mask_member)
        for object_id in object_ids:
            if frame in frame_sets[object_id] and not np.any(arr == int(object_id)):
                raise YouTubeVOSArchiveError(
                    f"metadata/mask mismatch: video {video_id} object {object_id} "
                    f"declared visible at {frame} but absent from {mask_member}"
                )

    hints: list[str] = []
    if co_visible:
        hints.append("ordinary_continuity")
    if any(gap in {1, 2} for gap in gaps):
        hints.append("short_occlusion_candidate")
    if any(gap >= 3 for gap in gaps):
        hints.append("long_gap_reentry_candidate")
    if bbox_overlap_frames:
        hints.append("crossing_close_interaction_candidate")

    return {
        "video_id": str(video_id),
        "category_name": category_name,
        "cat_instance_count": len(object_ids),
        "source_object_ids": object_ids,
        "visible_track_frames": sum(len(v) for v in frame_sets.values()),
        "co_visible_frames": len(co_visible),
        "bbox_overlap_frames": bbox_overlap_frames,
        "max_internal_gap_frames": max(gaps, default=0),
        "per_track_visible_frames": {
            str(object_id): len(frame_sets[object_id]) for object_id in object_ids
        },
        "selected_frame_count": len(all_frames),
        "stress_stratum_hints": hints,
        "source_consistency_validated": True,
    }


def inspect_candidates(
    zf: zipfile.ZipFile,
    *,
    meta: dict[str, Any],
    meta_member: str,
    members: set[str],
    category_name: str = "cat",
    min_instances: int = 2,
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    if min_instances < 1:
        raise YouTubeVOSArchiveError("min_instances must be >= 1")
    videos = meta.get("videos", {})
    candidates: list[dict[str, Any]] = []
    rejected: list[dict[str, str]] = []
    for raw_video_id in sorted(videos):
        video_id = str(raw_video_id)
        ids, _ = _eligible_object_ids(
            meta, video_id=video_id, category_name=category_name
        )
        if len(ids) < min_instances:
            continue
        try:
            stats = candidate_stats(
                zf,
                meta=meta,
                meta_member=meta_member,
                members=members,
                video_id=video_id,
                category_name=category_name,
            )
        except YouTubeVOSArchiveError as exc:
            rejected.append({"video_id": video_id, "reason": str(exc)})
            continue
        candidates.append(stats)

    candidates.sort(
        key=lambda row: (
            -int(row["cat_instance_count"]),
            -int(row["co_visible_frames"]),
            -int(row["max_internal_gap_frames"]),
            -int(row["bbox_overlap_frames"]),
            -int(row["visible_track_frames"]),
            str(row["video_id"]),
        )
    )
    for rank, row in enumerate(candidates, start=1):
        row["selection_rank"] = rank
        row["selection_rule_version"] = SELECTION_RULE_VERSION
    return candidates, rejected


def _copy_zip_member(zf: zipfile.ZipFile, member: str, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with zf.open(member, "r") as src, target.open("wb") as dst:
        shutil.copyfileobj(src, dst, length=1024 * 1024)


def _assert_empty_output(output_root: Path) -> None:
    if output_root.exists() and any(output_root.iterdir()):
        raise YouTubeVOSArchiveError(f"output root is not empty: {output_root}")


def materialize_selected_sequence(
    *,
    archive_path: Path,
    output_root: Path,
    category_name: str = "cat",
    min_instances: int = 2,
    source_uri: str | None = None,
) -> dict[str, Any]:
    archive_path = archive_path.expanduser().resolve()
    output_root = output_root.expanduser().resolve()
    _assert_empty_output(output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(archive_path, "r", allowZip64=True) as zf:
        members = _member_index(zf)
        meta_member = locate_meta_member(zf)
        meta = read_meta_from_archive(zf, meta_member)
        candidates, rejected = inspect_candidates(
            zf,
            meta=meta,
            meta_member=meta_member,
            members=members,
            category_name=category_name,
            min_instances=min_instances,
        )
        if not candidates:
            raise YouTubeVOSArchiveError(
                f"no source video has at least {min_instances} consistent "
                f"{category_name!r} instances"
            )
        selected = candidates[0]
        video_id = str(selected["video_id"])
        object_ids, objects = _eligible_object_ids(
            meta, video_id=video_id, category_name=category_name
        )
        selected_frames = sorted(
            set().union(*(set(objects[oid]["frames"]) for oid in object_ids)),
            key=_frame_sort_key,
        )
        root = _root_from_meta_member(meta_member)

        source_meta = output_root / "source_meta.json"
        source_meta.write_text(
            json.dumps(meta, separators=(",", ":")),
            encoding="utf-8",
        )
        frames_out = output_root / "davis" / "frames"
        masks_out = output_root / "davis" / "annotations"
        frames_out.mkdir(parents=True, exist_ok=True)
        masks_out.mkdir(parents=True, exist_ok=True)

        stable_by_source = {
            object_id: stable_id
            for stable_id, object_id in enumerate(object_ids, start=1)
        }
        canonical_names: list[str] = []
        frame_records: list[dict[str, Any]] = []
        mask_records: list[dict[str, Any]] = []
        width: int | None = None
        height: int | None = None

        for index, frame_id in enumerate(selected_frames):
            image_member = _image_member(
                members, root=root, video_id=video_id, frame_id=frame_id
            )
            mask_member = _annotation_member(
                members, root=root, video_id=video_id, frame_id=frame_id
            )
            suffix = PurePosixPath(image_member).suffix.lower() or ".jpg"
            canonical_name = f"frame_{index:06d}{suffix}"
            target_frame = frames_out / canonical_name
            _copy_zip_member(zf, image_member, target_frame)
            with Image.open(target_frame) as image:
                current_width, current_height = image.size
            if width is None:
                width, height = current_width, current_height
            elif (current_width, current_height) != (width, height):
                raise YouTubeVOSArchiveError(
                    f"source frame dimensions changed within video {video_id}"
                )

            raw_mask = _read_indexed_mask(zf, mask_member)
            if raw_mask.shape != (height, width):
                raise YouTubeVOSArchiveError(
                    f"mask/image shape mismatch at {video_id}/{frame_id}: "
                    f"{raw_mask.shape} != {(height, width)}"
                )
            label = np.zeros(raw_mask.shape, dtype=np.uint8)
            visible_stable_ids: list[int] = []
            for object_id in object_ids:
                object_mask = raw_mask == int(object_id)
                declared_visible = frame_id in set(objects[object_id]["frames"])
                if declared_visible and not np.any(object_mask):
                    raise YouTubeVOSArchiveError(
                        f"metadata/mask mismatch during conversion: video {video_id} "
                        f"object {object_id} frame {frame_id}"
                    )
                if not declared_visible and np.any(object_mask):
                    raise YouTubeVOSArchiveError(
                        f"mask/metadata mismatch during conversion: video {video_id} "
                        f"object {object_id} appears at undeclared frame {frame_id}"
                    )
                if np.any(object_mask):
                    stable_id = stable_by_source[object_id]
                    label[object_mask] = np.uint8(stable_id)
                    visible_stable_ids.append(stable_id)

            mask_name = f"frame_{index:06d}.png"
            mask_path = masks_out / mask_name
            Image.fromarray(label).save(mask_path)
            canonical_names.append(canonical_name)
            frame_records.append(
                {
                    "index": index,
                    "source_frame_id": frame_id,
                    "source_member": image_member,
                    "source_member_crc32": f"{zf.getinfo(image_member).CRC:08x}",
                    "canonical_name": canonical_name,
                    "canonical_sha256": sha256_file(target_frame),
                }
            )
            mask_records.append(
                {
                    "index": index,
                    "source_frame_id": frame_id,
                    "source_member": mask_member,
                    "source_member_crc32": f"{zf.getinfo(mask_member).CRC:08x}",
                    "mask_name": mask_name,
                    "mask_sha256": sha256_file(mask_path),
                    "visible_stable_ids": visible_stable_ids,
                }
            )

    if width is None or height is None:
        raise YouTubeVOSArchiveError("selected sequence produced no frames")

    davis_dir = output_root / "davis"
    sequence_name = f"youtubevos_{video_id}"
    meta_out = {
        "sequence": sequence_name,
        "davis_res": "raw",
        "frame_names": canonical_names,
        "id_to_label": {
            str(stable_id): f"{category_name}_{stable_id}"
            for stable_id in stable_by_source.values()
        },
        "source_dataset": SOURCE_DATASET,
        "source_video_id": video_id,
    }
    meta_path = davis_dir / "meta.json"
    meta_path.write_text(
        json.dumps(meta_out, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    selection = {
        "schema_version": "ID1-YTVOS-archive-selection-v0",
        "selection_rule_version": SELECTION_RULE_VERSION,
        "dataset": SOURCE_DATASET,
        "source_format": SOURCE_FORMAT,
        "archive_name": archive_path.name,
        "archive_sha256": sha256_file(archive_path),
        "metadata_member": meta_member,
        "source_metadata_sha256": sha256_file(source_meta),
        "category_name": category_name,
        "min_instances": min_instances,
        "selected": selected,
        "candidate_count": len(candidates),
        "rejected_candidate_count": len(rejected),
        "rejected_candidates": rejected[:50],
        "top_candidates": candidates[:20],
        "remind_scoring_performed": False,
        "source_correction": (
            "OpenDataLab repository is named YouTubeVIS2019, but the downloaded "
            "train.zip was verified before scoring to use the YouTube-VOS 2019 "
            "meta.json + indexed-PNG annotation format. The frozen ranking order "
            "is unchanged."
        ),
    }
    selection_path = output_root / "selection.json"
    selection_path.write_text(
        json.dumps(selection, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    manifest = {
        "schema_version": OUTPUT_SCHEMA_VERSION,
        "selection_rule_version": SELECTION_RULE_VERSION,
        "dataset": SOURCE_DATASET,
        "source_format": SOURCE_FORMAT,
        "source_uri": source_uri,
        "source_metadata_name": source_meta.name,
        "source_metadata_sha256": sha256_file(source_meta),
        "category_name": category_name,
        "video_id": video_id,
        "width": width,
        "height": height,
        "frame_count": len(canonical_names),
        "stable_id_by_source_object_id": {
            str(source_id): int(stable_id)
            for source_id, stable_id in stable_by_source.items()
        },
        "stable_id_by_source_annotation_id": {
            str(source_id): int(stable_id)
            for source_id, stable_id in stable_by_source.items()
        },
        "candidate_stats_before_scoring": selected,
        "frames": frame_records,
        "masks": mask_records,
        "meta_sha256": sha256_file(meta_path),
        "quantitative_ready_for_remind_davis": True,
        "claims": {
            "persistent_ids_come_from_source_annotations": True,
            "source_masks_used_as_detections": True,
            "remind_scoring_performed": False,
            "intent_inference_performed": False,
        },
    }
    manifest_path = davis_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {
        "selection": selection,
        "davis_manifest": manifest,
        "selection_path": str(selection_path),
        "davis_dir": str(davis_dir),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Select and selectively materialize the frozen ID1 feline sequence "
            "from the indexed-PNG YouTube-VOS-style train.zip."
        )
    )
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--category-name", default="cat")
    parser.add_argument("--min-instances", type=int, default=2)
    parser.add_argument("--source-uri", default=None)
    args = parser.parse_args()
    result = materialize_selected_sequence(
        archive_path=args.archive,
        output_root=args.output_root,
        category_name=args.category_name,
        min_instances=args.min_instances,
        source_uri=args.source_uri,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
