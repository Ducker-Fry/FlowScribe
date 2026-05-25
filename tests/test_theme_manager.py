"""Tests for theme management system."""

from __future__ import annotations

import pytest

from flowscribe.gui.theme_manager import (
    apply_theme,
    get_available_themes,
    load_theme_stylesheet,
)


def test_get_available_themes():
    """Test that available themes are returned correctly."""
    themes = get_available_themes()
    assert isinstance(themes, tuple)
    assert "light" in themes
    assert "dark" in themes
    assert len(themes) == 2


def test_load_theme_stylesheet_light():
    """Test loading light theme stylesheet."""
    stylesheet = load_theme_stylesheet("light")
    assert isinstance(stylesheet, str)
    assert len(stylesheet) > 0
    assert "FlowScribe Light Theme" in stylesheet
    assert "QWidget" in stylesheet
    assert "QPushButton" in stylesheet


def test_load_theme_stylesheet_dark():
    """Test loading dark theme stylesheet."""
    stylesheet = load_theme_stylesheet("dark")
    assert isinstance(stylesheet, str)
    assert len(stylesheet) > 0
    assert "FlowScribe Dark Theme" in stylesheet
    assert "QWidget" in stylesheet
    assert "QPushButton" in stylesheet


def test_load_theme_stylesheet_invalid():
    """Test that loading invalid theme raises ValueError."""
    with pytest.raises(ValueError, match="Invalid theme"):
        load_theme_stylesheet("invalid_theme")


def test_load_theme_stylesheet_nonexistent():
    """Test that loading nonexistent theme file raises FileNotFoundError."""
    import tempfile
    from pathlib import Path
    from unittest.mock import patch

    with tempfile.TemporaryDirectory() as tmpdir:
        fake_theme_dir = Path(tmpdir)
        with patch("flowscribe.gui.theme_manager.THEME_DIR", fake_theme_dir):
            with pytest.raises(FileNotFoundError):
                load_theme_stylesheet("light")


def test_apply_theme_light(qtbot):
    """Test applying light theme to QApplication."""
    pytest.importorskip("pytest_qt")
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if not app:
        pytest.skip("QApplication not available")

    apply_theme(app, "light")
    stylesheet = app.styleSheet()
    assert len(stylesheet) > 0
    assert "FlowScribe Light Theme" in stylesheet


def test_apply_theme_dark(qtbot):
    """Test applying dark theme to QApplication."""
    pytest.importorskip("pytest_qt")
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if not app:
        pytest.skip("QApplication not available")

    apply_theme(app, "dark")
    stylesheet = app.styleSheet()
    assert len(stylesheet) > 0
    assert "FlowScribe Dark Theme" in stylesheet


def test_apply_theme_invalid(qtbot):
    """Test that applying invalid theme raises ValueError."""
    pytest.importorskip("pytest_qt")
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if not app:
        pytest.skip("QApplication not available")

    with pytest.raises(ValueError, match="Invalid theme"):
        apply_theme(app, "invalid_theme")
