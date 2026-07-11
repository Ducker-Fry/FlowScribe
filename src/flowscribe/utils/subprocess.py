"""Helpers for launching background subprocesses."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

LOGGER = logging.getLogger(__name__)
TRACE_ENV_NAME = "FLOWSCRIBE_SUBPROCESS_TRACE"


def subprocess_trace_enabled() -> bool:
    value = os.environ.get(TRACE_ENV_NAME, "")
    return value.strip().lower() in {"1", "true", "yes", "on"}


def hidden_subprocess_kwargs() -> dict[str, Any]:
    """Return kwargs that suppress child tool consoles in windowed Windows apps."""
    if sys.platform != "win32":
        if subprocess_trace_enabled():
            LOGGER.info(
                "hidden_subprocess_kwargs: no-op because platform=%s executable=%s",
                sys.platform,
                sys.executable,
            )
        return {}
    is_windowed = _is_windowed_windows_process()
    if not is_windowed:
        if subprocess_trace_enabled():
            LOGGER.info(
                "hidden_subprocess_kwargs: no-op because process has console: frozen=%s executable=%s",
                bool(getattr(sys, "frozen", False)),
                sys.executable,
            )
        return {}

    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = subprocess.SW_HIDE
    kwargs = {
        "creationflags": subprocess.CREATE_NO_WINDOW,
        "startupinfo": startupinfo,
    }
    if subprocess_trace_enabled():
        LOGGER.info(
            "hidden_subprocess_kwargs: applying hidden child process flags: frozen=%s executable=%s kwargs=%s",
            bool(getattr(sys, "frozen", False)),
            sys.executable,
            kwargs,
        )
    return kwargs


def _is_windowed_windows_process() -> bool:
    """Detect packaged/windowed Python processes that lack a parent console."""
    if bool(getattr(sys, "frozen", False)):
        return True
    return Path(sys.executable).name.lower() == "pythonw.exe"
