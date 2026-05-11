"""Output path helpers."""

from __future__ import annotations

from pathlib import Path

from flowscribe.core.models import MediaItem


class OutputPathBuilder:
    def __init__(self, *, overwrite: bool = False) -> None:
        self._overwrite = overwrite

    def build(self, item: MediaItem, output_dir: Path, suffix: str) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        candidate = output_dir / f"{item.path.stem}{suffix}"
        if self._overwrite or not candidate.exists():
            return candidate

        index = 1
        while True:
            numbered = output_dir / f"{item.path.stem}-{index}{suffix}"
            if not numbered.exists():
                return numbered
            index += 1
