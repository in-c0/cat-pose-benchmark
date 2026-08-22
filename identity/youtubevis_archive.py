from __future__ import annotations

import argparse
import json
import shutil
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

from identity.youtubevis_adapter import (
    YouTubeVISAdapterError,
    convert_video,
    inspect_candidates,
    resolve_category_id,
    sha256_file,
)


class YouTubeVISArchiveError(YouTubeVISAdapterError):
    pass


def _normalise_member(name: str) -> str:
    text = str(name).replace("\\", "/")
    path = PurePosixPath(text)
    if not text or path.is_absolute() or ".." in path.parts:
        raise YouTubeVISArchiveError(f"unsafe ZIP member path: {name!r}")
    return str(path)


def locate_annotations_member(zf: zipfile.ZipFile) -> str:
    matches = []
    for raw in zf.namelist():
        name = _normalise_member(raw)
        if PurePosixPath(name).name == "train.json":
            matches.append(name)
    if len(matches) != 1:
        raise YouTubeVISArchiveError(
            f"expected exactly one train.json in archive, found {len(matches)}"
        )
    return matches[0]


def read_annotations_from_archive(zf: zipfile.ZipFile, member: str) -> dict[str, Any]:
    try:
        raw = json.loads(zf.read(member).decode("utf-8"))
    except Exception as exc:
        raise YouTubeVISArchiveError(f"failed to read {member} from archive") from exc
    if not isinstance(raw, dict):
        raise YouTubeVISArchiveError("train.json must contain a JSON object")
    return raw


def _source_frame_names(data: dict[str, Any], *, video_id: int) -> list[str]:
    videos = [
        v
        for v in data.get("videos", [])
        if isinstance(v, dict) and int(v.get("id", -1)) == int(video_id)
    ]
    if len(videos) != 1:
        raise YouTubeVISArchiveError(
            f"expected exactly one source video {video_id}, found {len(videos)}"
        )
    names = videos[0].get("file_names")
    if not isinstance(names, list) or not names:
        raise YouTubeVISArchiveError("selected video has no frame names")
    out = [str(name).replace("\\", "/").lstrip("/") for name in names]
    if any(not name or ".." in PurePosixPath(name).parts for name in out):
        raise YouTubeVISArchiveError("selected video contains unsafe frame paths")
    return out


def _index_frame_members(zf: zipfile.ZipFile, source_names: list[str]) -> dict[str, str]:
    wanted = set(source_names)
    matches: dict[str, list[str]] = {name: [] for name in source_names}
    for raw in zf.namelist():
        member = _normalise_member(raw)
        candidates = [member]
        marker = "/JPEGImages/"
        if marker in member:
            candidates.append(member.split(marker, 1)[1])
        for candidate in candidates:
            if candidate in wanted:
                matches[candidate].append(member)
                break
    resolved: dict[str, str] = {}
    for source_name in source_names:
        hits = matches[source_name]
        if len(hits) != 1:
            raise YouTubeVISArchiveError(
                f"expected exactly one archive member for frame {source_name!r}, found {len(hits)}"
            )
        resolved[source_name] = hits[0]
    return resolved


def _extract_member_to(zf: zipfile.ZipFile, member: str, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with zf.open(member, "r") as src, target.open("wb") as dst:
        shutil.copyfileobj(src, dst, length=1024 * 1024)


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
    if output_root.exists() and any(output_root.iterdir()):
        raise YouTubeVISArchiveError(f"output root is not empty: {output_root}")
    output_root.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(archive_path, "r", allowZip64=True) as zf:
        annotations_member = locate_annotations_member(zf)
        data = read_annotations_from_archive(zf, annotations_member)
        category_id = resolve_category_id(data, category_name)
        candidates = inspect_candidates(
            data,
            category_name=category_name,
            min_instances=min_instances,
        )
        if not candidates:
            raise YouTubeVISArchiveError(
                f"no {category_name!r} source video has at least {min_instances} persistent instances"
            )
        selected = candidates[0]
        video_id = int(selected["video_id"])
        source_names = _source_frame_names(data, video_id=video_id)
        frame_members = _index_frame_members(zf, source_names)

        source_annotations = output_root / "source_train.json"
        source_annotations.write_text(
            json.dumps(data, separators=(",", ":")),
            encoding="utf-8",
        )
        source_frames = output_root / "source_frames"
        for source_name in source_names:
            target = source_frames / PurePosixPath(source_name)
            _extract_member_to(zf, frame_members[source_name], target)

    selection = {
        "schema_version": "ID1-YTVIS-archive-selection-v0",
        "archive_name": archive_path.name,
        "archive_sha256": sha256_file(archive_path),
        "annotations_member": annotations_member,
        "source_annotations_sha256": sha256_file(source_annotations),
        "category_name": category_name,
        "category_id": category_id,
        "min_instances": min_instances,
        "selected": selected,
        "candidate_count": len(candidates),
        "top_candidates": candidates[:20],
        "remind_scoring_performed": False,
    }
    selection_path = output_root / "selection.json"
    selection_path.write_text(
        json.dumps(selection, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    davis_dir = output_root / "davis"
    manifest = convert_video(
        annotations_path=source_annotations,
        frames_root=source_frames,
        output_dir=davis_dir,
        video_id=int(selected["video_id"]),
        category_name=category_name,
        min_instances=min_instances,
        source_uri=source_uri,
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
            "Select and selectively materialize the frozen ID1 YouTube-VIS "
            "feline sequence from train.zip."
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
