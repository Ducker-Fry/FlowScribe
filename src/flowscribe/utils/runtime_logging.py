"""Runtime logging helpers shared by GUI and CLI entry points."""

from __future__ import annotations

import io
import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import TextIO

LOG_DIR_ENV = "FLOWSCRIBE_LOG_DIR"
LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
MAX_LOG_BYTES = 5 * 1024 * 1024
BACKUP_COUNT = 3


class NullTextIO(io.TextIOBase):
    """Writable text stream used when a windowed app has no console streams."""

    encoding = "utf-8"

    def writable(self) -> bool:
        return True

    def write(self, text: str) -> int:
        return len(text)

    def flush(self) -> None:
        return None


def install_null_standard_streams() -> None:
    """Ensure sys.stdout/sys.stderr are writable in PyInstaller windowed builds."""
    if sys.stdout is None:
        sys.stdout = NullTextIO()
    if sys.stderr is None:
        sys.stderr = NullTextIO()


def configure_runtime_logging(
    app_name: str,
    *,
    file_level: int = logging.DEBUG,
    root_level: int = logging.INFO,
) -> Path | None:
    """Attach a rotating log file handler and return the log path when available."""
    install_null_standard_streams()
    log_dir = flowscribe_log_dir()
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        return None

    log_path = log_dir / f"{app_name}.log"
    handler_key = str(log_path.resolve()).lower()
    root_logger = logging.getLogger()
    root_logger.setLevel(min(root_logger.level or root_level, root_level))

    for handler in root_logger.handlers:
        if getattr(handler, "_flowscribe_log_path", None) == handler_key:
            return log_path

    try:
        handler = RotatingFileHandler(
            log_path,
            maxBytes=MAX_LOG_BYTES,
            backupCount=BACKUP_COUNT,
            encoding="utf-8",
        )
    except OSError:
        return None

    handler.setLevel(file_level)
    handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT))
    handler._flowscribe_log_path = handler_key  # type: ignore[attr-defined]
    root_logger.addHandler(handler)
    return log_path


def flowscribe_log_dir(env: dict[str, str] | None = None) -> Path:
    env = os.environ if env is None else env
    override = env.get(LOG_DIR_ENV)
    if override:
        return Path(override).expanduser()
    return _default_log_dir()


def _default_log_dir() -> Path:
    if bool(getattr(sys, "frozen", False)):
        return Path(sys.executable).resolve().parent / "logs"
    return Path(__file__).resolve().parents[3] / "logs"
