"""GUI-specific logging and runtime noise control."""

from __future__ import annotations

import logging
import os
import sys
from typing import Literal

GuiLogMode = Literal["dev", "user"]

GUI_LOG_MODE_ENV = "FLOWSCRIBE_GUI_LOG_MODE"
GUI_LOGGER_NAME = "flowscribe.gui"


def resolve_gui_log_mode(
    env: dict[str, str] | None = None,
    *,
    frozen: bool | None = None,
) -> GuiLogMode:
    env = os.environ if env is None else env
    frozen = bool(getattr(sys, "frozen", False)) if frozen is None else frozen

    raw_value = env.get(GUI_LOG_MODE_ENV, "").strip().lower()
    if raw_value in {"dev", "user"}:
        return raw_value
    return "user" if frozen else "dev"


def qt_logging_filter_rules(mode: GuiLogMode) -> str:
    if mode == "dev":
        return ""
    return "\n".join(
        [
            "qt.multimedia.ffmpeg.debug=false",
            "qt.multimedia.ffmpeg.info=false",
            "qt.multimedia.debug=false",
            "qt.multimedia.info=false",
        ]
    )


def configure_gui_logging(mode: GuiLogMode | None = None) -> GuiLogMode:
    resolved_mode = resolve_gui_log_mode() if mode is None else mode
    _configure_python_logging(resolved_mode)
    _configure_qt_logging(resolved_mode)
    return resolved_mode


def get_gui_logger(name: str = GUI_LOGGER_NAME) -> logging.Logger:
    return logging.getLogger(name)


def _configure_python_logging(mode: GuiLogMode) -> None:
    logger = logging.getLogger(GUI_LOGGER_NAME)
    logger.setLevel(logging.DEBUG if mode == "dev" else logging.WARNING)
    if mode == "dev" and not logging.getLogger().handlers:
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(levelname)s %(name)s: %(message)s",
        )


def _configure_qt_logging(mode: GuiLogMode) -> None:
    rules = qt_logging_filter_rules(mode)
    if not rules:
        return

    try:
        from PySide6.QtCore import QLoggingCategory
    except ImportError:
        return

    QLoggingCategory.setFilterRules(rules)
