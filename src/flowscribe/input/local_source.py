"""Local file and folder input source."""

from __future__ import annotations

from pathlib import Path

from flowscribe.core.errors import InputError
from flowscribe.core.models import MediaItem
from flowscribe.input.file_filter import is_supported_media


class LocalFileSource:
    def __init__(self, paths: list[Path], recursive: bool = False) -> None:
        self._paths = paths
        self._recursive = recursive

    def discover(self) -> list[MediaItem]:
        items: list[MediaItem] = []
        missing: list[Path] = []

        for raw_path in self._paths:
            path = raw_path.expanduser().resolve()
            if not path.exists():
                missing.append(path)
                continue

            if path.is_file():
                if is_supported_media(path):
                    items.append(MediaItem(path=path))
                continue

            if path.is_dir():
                iterator = path.rglob("*") if self._recursive else path.glob("*")
                items.extend(MediaItem(path=file_path) for file_path in iterator if is_supported_media(file_path))

        if missing:
            missing_text = ", ".join(str(path) for path in missing)
            raise InputError(f"Input path does not exist: {missing_text}")

        if not items:
            raise InputError("No supported media files were found.")

        return sorted(items, key=lambda item: str(item.path).lower())
