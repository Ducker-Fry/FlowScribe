"""Shared window coordination helpers for GUI actions."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices


def open_output_directory(path: Path) -> bool:
    return path.exists() and QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))


def open_multiple_output_directories(entries: list) -> tuple[int, int]:
    opened = 0
    missing = 0
    seen: set[Path] = set()
    for entry in entries:
        output_dir = Path(entry.output_dir)
        if output_dir in seen:
            continue
        seen.add(output_dir)
        if open_output_directory(output_dir):
            opened += 1
        else:
            missing += 1
    return opened, missing
