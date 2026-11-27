from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class AdapterInfo:
    model_id: str
    version: str
    checkpoint: str
    commercial_status: str


class PoseAdapter(ABC):
    """Convert one model's native output into the common bake-off prediction contract."""

    info: AdapterInfo

    @abstractmethod
    def predict(self, clip_manifest: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    def predict_file(self, clip_manifest_path: Path) -> dict[str, Any]:
        import json

        manifest = json.loads(clip_manifest_path.read_text(encoding="utf-8"))
        return self.predict(manifest)
