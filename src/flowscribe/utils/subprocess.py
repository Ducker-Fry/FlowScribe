"""Helpers for launching background subprocesses."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any


def hidden_subprocess_kwargs() -> dict[str, Any]:
    """Return kwargs that suppress child tool consoles in windowed Windows apps."""
    if sys.platform != "win32":
        return {}
    if not _is_windowed_windows_process():
        return {}

    return {"creationflags": subprocess.CREATE_NO_WINDOW}


def _is_windowed_windows_process() -> bool:
    """Detect packaged/windowed Python processes that lack a parent console."""
    if bool(getattr(sys, "frozen", False)):
        return True
    return Path(sys.executable).name.lower() == "pythonw.exe"
