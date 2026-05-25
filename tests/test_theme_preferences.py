"""Tests for theme preference in GUI state management."""

from __future__ import annotations

from flowscribe.gui.utils.state import (
    DEFAULT_GUI_PREFERENCES,
    GUI_THEME_OPTIONS,
    _gui_preferences_payload,
    _normalize_gui_preferences_payload,
)


def test_default_gui_preferences_includes_theme():
    """Test that default preferences include theme setting."""
    assert "theme" in DEFAULT_GUI_PREFERENCES
    assert DEFAULT_GUI_PREFERENCES["theme"] == "light"


def test_gui_theme_options():
    """Test that GUI_THEME_OPTIONS contains expected themes."""
    assert "light" in GUI_THEME_OPTIONS
    assert "dark" in GUI_THEME_OPTIONS
    assert len(GUI_THEME_OPTIONS) == 2


def test_normalize_gui_preferences_with_valid_theme():
    """Test normalizing preferences with valid theme."""
    payload = {"theme": "dark"}
    normalized = _normalize_gui_preferences_payload(payload)
    assert normalized["theme"] == "dark"


def test_normalize_gui_preferences_with_invalid_theme():
    """Test normalizing preferences with invalid theme defaults to light."""
    payload = {"theme": "invalid"}
    normalized = _normalize_gui_preferences_payload(payload)
    assert normalized["theme"] == "light"


def test_normalize_gui_preferences_without_theme():
    """Test normalizing preferences without theme defaults to light."""
    payload = {}
    normalized = _normalize_gui_preferences_payload(payload)
    assert normalized["theme"] == "light"


def test_gui_preferences_payload_includes_theme():
    """Test that preferences payload includes theme."""
    preferences = {"theme": "dark"}
    payload = _gui_preferences_payload(preferences)
    assert "theme" in payload
    assert payload["theme"] == "dark"


def test_normalize_gui_preferences_preserves_theme():
    """Test that theme is preserved through normalization."""
    original = {
        "theme": "dark",
        "output_dir": "outputs",
        "model_name": "small",
    }
    normalized = _normalize_gui_preferences_payload(original)
    assert normalized["theme"] == "dark"
    assert normalized["output_dir"] == "outputs"
    assert normalized["model_name"] == "small"
