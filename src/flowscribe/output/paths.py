"""Output path helpers."""

from __future__ import annotations

from pathlib import Path

from flowscribe.core.models import MediaItem


class OutputPathBuilder:
    def __init__(self, *, overwrite: bool = False, base_name: str | None = None) -> None:
        self._overwrite = overwrite
        self._base_name = sanitize_output_base_name(base_name)

    def build(self, item: MediaItem, output_dir: Path, suffix: str) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        stem = self._base_name or item.path.stem
        candidate = output_dir / f"{stem}{suffix}"
        if self._overwrite or not candidate.exists():
            return candidate

        index = 1
        while True:
            numbered = output_dir / f"{stem}-{index}{suffix}"
            if not numbered.exists():
                return numbered
            index += 1


def sanitize_output_base_name(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None

    forbidden = '<>:"/\\|?*'
    cleaned = "".join("-" if char in forbidden else char for char in text)
    cleaned = cleaned.strip(" .")
    return cleaned or "transcript"
