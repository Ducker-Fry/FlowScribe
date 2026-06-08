"""Runtime logging helpers shared by GUI and CLI entry points."""

from __future__ import annotations

import io
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

from flowscribe.utils.runtime_layout import resolve_runtime_layout

LOG_DIR_ENV = "FLOWSCRIBE_LOG_DIR"
LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
MAX_LOG_BYTES = 5 * 1024 * 1024


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

    log_path = select_log_path(log_dir, app_name)
    handler_key = str(log_path.resolve()).lower()
    root_logger = logging.getLogger()
    root_logger.setLevel(min(root_logger.level or root_level, root_level))

    for handler in root_logger.handlers:
        if getattr(handler, "_flowscribe_log_path", None) == handler_key:
            return log_path

    try:
        handler = logging.FileHandler(log_path, encoding="utf-8")
    except OSError:
        return None

    handler.setLevel(file_level)
    handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT))
    handler._flowscribe_log_path = handler_key  # type: ignore[attr-defined]
    root_logger.addHandler(handler)
    return log_path


def active_log_file_path(app_name: str | None = None) -> Path | None:
    """Return the currently attached FlowScribe file log path when available."""
    root_logger = logging.getLogger()
    normalized_app_name = app_name.lower() if app_name is not None else None
    for handler in reversed(root_logger.handlers):
        log_path = getattr(handler, "baseFilename", None)
        if not log_path:
            continue
        path = Path(str(log_path))
        if normalized_app_name is not None and not path.name.lower().startswith(normalized_app_name.lower()):
            continue
        return path
    return None


def select_log_path(
    log_dir: Path,
    app_name: str,
    *,
    now: datetime | None = None,
    max_bytes: int = MAX_LOG_BYTES,
) -> Path:
    current_time = datetime.now() if now is None else now
    date_prefix = current_time.strftime("%Y-%m-%d")
    extension = ".log"
    base_name = f"{app_name}-{date_prefix}"

    candidate = log_dir / f"{base_name}{extension}"
    if not _needs_log_rollover(candidate, max_bytes):
        return candidate

    index = 1
    while True:
        candidate = log_dir / f"{base_name}-{index}{extension}"
        if not _needs_log_rollover(candidate, max_bytes):
            return candidate
        index += 1


def _needs_log_rollover(log_path: Path, max_bytes: int) -> bool:
    try:
        return log_path.exists() and log_path.stat().st_size >= max_bytes
    except OSError:
        return False


def flowscribe_log_dir(env: dict[str, str] | None = None) -> Path:
    env = os.environ if env is None else env
    override = env.get(LOG_DIR_ENV)
    if override:
        return Path(override).expanduser()
    return _default_log_dir()


def _default_log_dir() -> Path:
    layout = resolve_runtime_layout()
    if layout.frozen:
        return layout.app_root / "logs"
    return layout.source_root / "logs"
