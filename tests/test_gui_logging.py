from types import ModuleType, SimpleNamespace

from flowscribe.gui.gui_logging import (
    GUI_LOG_MODE_ENV,
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
