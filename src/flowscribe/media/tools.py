"""Runtime lookup for external media tools."""

from __future__ import annotations

import shutil
from pathlib import Path

from flowscribe.utils.runtime_layout import resolve_runtime_layout


def resolve_tool_path(name: str) -> str:
    """Resolve a bundled tool first, then fall back to PATH."""

    candidates = []
    layout = resolve_runtime_layout()
    for root in (layout.core_dir, layout.app_root):
        candidates.append(root / f"{name}.exe")
        candidates.append(root / name)

    for candidate in candidates:
        if candidate.exists():
            return str(candidate)

    found = shutil.which(name)
    return found or name
