from types import ModuleType, SimpleNamespace
import logging
import sys
from datetime import datetime

from flowscribe.gui.gui_logging import (
    GUI_LOG_MODE_ENV,
    THIRD_PARTY_LOGGER_LEVELS,
    configure_gui_logging,
    qt_logging_filter_rules,
    resolve_gui_log_mode,
)


def test_resolve_gui_log_mode_defaults_to_dev_for_source_runs() -> None:
    assert resolve_gui_log_mode({}, frozen=False) == "dev"


def test_resolve_gui_log_mode_defaults_to_user_for_frozen_runs() -> None:
    assert resolve_gui_log_mode({}, frozen=True) == "user"


def test_resolve_gui_log_mode_honors_environment_override() -> None:
    env = {GUI_LOG_MODE_ENV: "user"}

    assert resolve_gui_log_mode(env, frozen=False) == "user"


def test_qt_logging_filter_rules_are_empty_in_dev_mode() -> None:
    assert qt_logging_filter_rules("dev") == ""


def test_qt_logging_filter_rules_disable_multimedia_noise_in_user_mode() -> None:
    rules = qt_logging_filter_rules("user")

    assert "qt.multimedia.ffmpeg.info=false" in rules
    assert "qt.multimedia.info=false" in rules


def test_configure_gui_logging_applies_qt_filter_rules_in_user_mode(monkeypatch) -> None:
    captured: dict[str, str] = {}

    fake_qtcore = ModuleType("PySide6.QtCore")
    fake_qtcore.QLoggingCategory = SimpleNamespace(
        setFilterRules=lambda rules: captured.setdefault("rules", rules)
    )
    monkeypatch.setitem(__import__("sys").modules, "PySide6.QtCore", fake_qtcore)

    mode = configure_gui_logging("user")

    assert mode == "user"
    assert "qt.multimedia.ffmpeg.info=false" in captured["rules"]


def test_configure_gui_logging_keeps_runtime_info_and_limits_third_party(monkeypatch) -> None:
    root_logger = logging.getLogger()
    original_handlers = list(root_logger.handlers)
    original_root_level = root_logger.level
    gui_logger_name = "flowscribe.gui"
    saved_levels = {
        name: logging.getLogger(name).level
        for name in [gui_logger_name, *THIRD_PARTY_LOGGER_LEVELS.keys()]
    }

    root_logger.handlers.clear()
    root_logger.setLevel(logging.NOTSET)
    try:
        mode = configure_gui_logging("dev")

        assert mode == "dev"
        assert logging.getLogger().level == logging.INFO
        assert logging.getLogger(gui_logger_name).level == logging.DEBUG
        for logger_name, level in THIRD_PARTY_LOGGER_LEVELS.items():
            assert logging.getLogger(logger_name).level == level
    finally:
        root_logger.handlers[:] = original_handlers
        root_logger.setLevel(original_root_level)
        for logger_name, level in saved_levels.items():
            logging.getLogger(logger_name).setLevel(level)


def test_configure_gui_logging_installs_writable_streams(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("FLOWSCRIBE_LOG_DIR", str(tmp_path))
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)

    configure_gui_logging("user")

    assert sys.stdout.write("progress") == len("progress")
    assert sys.stderr.write("error") == len("error")
    expected_name = f"FlowScribeGUI-{datetime.now().strftime('%Y-%m-%d')}.log"
    assert (tmp_path / expected_name).exists()
