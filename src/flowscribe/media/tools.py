"""Runtime lookup for external media tools."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path


def resolve_tool_path(name: str) -> str:
    """Resolve a bundled tool first, then fall back to PATH."""

    candidates = []
    executable_dir = Path(sys.executable).resolve().parent
    candidates.append(executable_dir / f"{name}.exe")
    candidates.append(executable_dir / name)

    for candidate in candidates:
        if candidate.exists():
            return str(candidate)

    found = shutil.which(name)
    return found or name
