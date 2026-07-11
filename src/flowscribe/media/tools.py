"""Runtime lookup for external media tools."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

from flowscribe.utils.runtime_layout import resolve_runtime_layout


def resolve_tool_path(name: str) -> str:
    """Resolve a bundled tool first, then fall back to PATH."""

    candidates = []
    executable_path = Path(sys.executable)
    executable_stem = executable_path.stem.lower()
    if executable_stem in {"flowscribe", "flowscribegui", "flowscribeurl", "gui-core", "cli-core"}:
        executable_dir = executable_path.resolve().parent
        candidates.append(executable_dir / f"{name}.exe")
        candidates.append(executable_dir / name)

    layout = resolve_runtime_layout()
    for root in (layout.core_dir, layout.app_root):
        candidates.append(root / f"{name}.exe")
        candidates.append(root / name)

    for candidate in candidates:
        if candidate.exists():
            return str(candidate)

    found = shutil.which(name)
    return found or name
