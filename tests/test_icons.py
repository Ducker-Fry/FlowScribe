"""Tests for icon system."""

from __future__ import annotations

import pytest


def test_get_icon_names():
    """Test that icon names are returned."""
    from flowscribe.gui.icons import get_icon_names

    names = get_icon_names()
    assert isinstance(names, list)
    assert len(names) > 0
    assert "play" in names
    assert "settings" in names
    assert "folder-open" in names


def test_get_icon_light_theme():
    """Test getting icon with light theme."""
    pytest.importorskip("PySide6")
    from PySide6.QtGui import QIcon

    from flowscribe.gui.icons import get_icon

    icon = get_icon("play", "light")
    assert isinstance(icon, QIcon)
    assert not icon.isNull()


def test_get_icon_dark_theme():
    """Test getting icon with dark theme."""
    pytest.importorskip("PySide6")
    from PySide6.QtGui import QIcon

    from flowscribe.gui.icons import get_icon

    icon = get_icon("play", "dark")
    assert isinstance(icon, QIcon)
    assert not icon.isNull()


def test_get_icon_invalid_name():
    """Test that invalid icon name raises ValueError."""
    pytest.importorskip("PySide6")
    from flowscribe.gui.icons import get_icon

    with pytest.raises(ValueError, match="Icon 'invalid' not found"):
        get_icon("invalid", "light")


def test_convenience_functions():
    """Test convenience functions for common icons."""
    pytest.importorskip("PySide6")
    from PySide6.QtGui import QIcon

    from flowscribe.gui.icons import (
        get_add_icon,
        get_delete_icon,
        get_library_icon,
        get_play_icon,
        get_queue_icon,
        get_settings_icon,
        get_stop_icon,
    )

    icons = [
        get_play_icon(),
        get_stop_icon(),
        get_settings_icon(),
        get_library_icon(),
        get_queue_icon(),
        get_add_icon(),
        get_delete_icon(),
    ]

    for icon in icons:
        assert isinstance(icon, QIcon)
        assert not icon.isNull()


def test_icon_size():
    """Test that icon size can be customized."""
    pytest.importorskip("PySide6")
    from PySide6.QtGui import QIcon

    from flowscribe.gui.icons import get_icon

    icon_small = get_icon("play", "light", size=16)
    icon_large = get_icon("play", "light", size=48)

    assert isinstance(icon_small, QIcon)
    assert isinstance(icon_large, QIcon)
    assert not icon_small.isNull()
    assert not icon_large.isNull()


def test_theme_color_difference():
    """Test that light and dark themes use different colors."""
    pytest.importorskip("PySide6")
    from flowscribe.gui.icons import get_icon

    # This test verifies that the function runs without error
    # Actual color verification would require pixel-level comparison
    icon_light = get_icon("play", "light")
    icon_dark = get_icon("play", "dark")

    assert not icon_light.isNull()
    assert not icon_dark.isNull()


def test_all_icon_names_valid():
    """Test that all icon names can be loaded."""
    pytest.importorskip("PySide6")
    from flowscribe.gui.icons import get_icon, get_icon_names

    names = get_icon_names()
    for name in names:
        icon = get_icon(name, "light")
        assert not icon.isNull()


def test_get_current_theme_default():
    """Test getting current theme with no app."""
    from flowscribe.gui.theme_manager import get_current_theme

    # Should return default "light" when no app is available
    theme = get_current_theme(None)
    assert theme == "light"


def test_get_current_theme_from_app(qtbot):
    """Test getting current theme from QApplication."""
    pytest.importorskip("pytest_qt")
    from PySide6.QtWidgets import QApplication

    from flowscribe.gui.theme_manager import apply_theme, get_current_theme

    app = QApplication.instance()
    if not app:
        pytest.skip("QApplication not available")

    # Apply dark theme
    apply_theme(app, "dark")

    # Get current theme
    theme = get_current_theme(app)
    assert theme == "dark"

    # Apply light theme
    apply_theme(app, "light")

    # Get current theme
    theme = get_current_theme(app)
    assert theme == "light"


def test_get_app_icon():
    """Test getting application icon."""
    pytest.importorskip("PySide6")
    from PySide6.QtGui import QIcon

    from flowscribe.gui.icons import get_app_icon

    icon = get_app_icon()
    assert isinstance(icon, QIcon)
    # Icon should not be null (either PNG exists or fallback to SVG)
    assert not icon.isNull()


def test_app_icon_path_exists():
    """Test that application icon file exists."""
    from pathlib import Path

    from flowscribe.gui.icons import _APP_ICON_PATH

    # Check if the icon path is correctly constructed
    assert isinstance(_APP_ICON_PATH, Path)
    # Icon should exist in the icons directory
    assert _APP_ICON_PATH.exists(), f"Application icon not found at {_APP_ICON_PATH}"
    assert _APP_ICON_PATH.suffix == ".png"
