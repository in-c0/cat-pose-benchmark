from __future__ import annotations

import argparse
import hashlib
import json
import urllib.request
from pathlib import Path
from typing import Any


ALLOWED_SOURCE_KINDS = {"owned", "redistributable", "synthetic"}
ALLOWED_REDISTRIBUTION = {"allowed", "not_applicable"}


def materialize(manifest: dict[str, Any], *, root: Path) -> tuple[Path, str]:
    source = manifest["source"]
    licence = manifest["licence"]
    source_kind = source["kind"]
    redistribution = licence["redistribution"]

    if source_kind not in ALLOWED_SOURCE_KINDS:
        raise ValueError(
            f"Refusing to materialize source.kind={source_kind!r}; link-only media "
            "must remain external."
        )
    if redistribution not in ALLOWED_REDISTRIBUTION:
        raise ValueError(
            f"Refusing to materialize licence.redistribution={redistribution!r}."
        )

    relative_path = source.get("local_path")
    if not relative_path:
        raise ValueError("source.local_path is required for materialization")
    output = (root / relative_path).resolve()
    root_resolved = root.resolve()
    if root_resolved not in output.parents and output != root_resolved:
        raise ValueError("source.local_path escapes the repository root")

    url = source.get("url")
    if not url:
        if output.exists():
            return output, _sha256(output)
        raise ValueError("source.url is required when the local file does not exist")

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".part")
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "CatPoseBenchmark/0.1 (+https://github.com/in-c0/cat-pose-benchmark)"},
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response, temporary.open("wb") as destination:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                destination.write(chunk)
        temporary.replace(output)
    finally:
        if temporary.exists():
            temporary.unlink()

    digest = _sha256(output)
    expected = source.get("sha256")
    if expected and digest != expected:
        output.unlink(missing_ok=True)
        raise ValueError(
            f"SHA-256 mismatch for {output}: expected {expected}, got {digest}"
        )
    return output, digest


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description="Materialize a licence-approved bake-off clip.")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    output, digest = materialize(manifest, root=args.root)
    print(json.dumps({"path": str(output), "sha256": digest}, sort_keys=True))


if __name__ == "__main__":
    main()
