"""Tests for settings dialog tab structure."""

from __future__ import annotations

import pytest


def test_settings_dialog_has_tabs(qtbot):
    """Test that settings dialog has tab widget."""
    pytest.importorskip("pytest_qt")
    from PySide6.QtWidgets import QApplication, QTabWidget

    from flowscribe.gui.dialogs.settings_dialog import SettingsDialog

    app = QApplication.instance()
    if not app:
        pytest.skip("QApplication not available")

    settings = {
        "theme": "light",
        "output_dir": "outputs",
        "model_name": "small",
        "language": "auto",
        "preset": "none",
        "output_formats": ("txt", "md", "json"),
        "timestamps": True,
        "word_timestamps": False,
        "overwrite": False,
        "network_family": "auto",
        "proxy": None,
        "cookies_path": None,
        "progressive_enabled": True,
        "progressive_resume": True,
        "progressive_chunk_seconds": 30.0,
        "progressive_max_workers": 1,
    }

    dialog = SettingsDialog(None, settings)
    qtbot.addWidget(dialog)

    # Check that tabs widget exists
    assert hasattr(dialog, "tabs")
    assert isinstance(dialog.tabs, QTabWidget)

    # Check that all expected tabs exist
    assert dialog.tabs.count() == 4
    tab_names = [dialog.tabs.tabText(i) for i in range(dialog.tabs.count())]
    assert "Appearance" in tab_names
    assert "Transcription" in tab_names
    assert "Network" in tab_names
    assert "Advanced" in tab_names


def test_appearance_tab_has_theme_selector(qtbot):
    """Test that appearance tab has theme selector."""
    pytest.importorskip("pytest_qt")
    from PySide6.QtWidgets import QApplication, QComboBox

    from flowscribe.gui.dialogs.settings_dialog import SettingsDialog

    app = QApplication.instance()
    if not app:
        pytest.skip("QApplication not available")

    settings = {"theme": "dark"}

    dialog = SettingsDialog(None, settings)
    qtbot.addWidget(dialog)

    # Check that theme combo exists
    assert hasattr(dialog, "theme_combo")
    assert isinstance(dialog.theme_combo, QComboBox)

    # Check that theme combo has correct options
    assert dialog.theme_combo.count() == 2
    assert dialog.theme_combo.itemText(0) == "light"
    assert dialog.theme_combo.itemText(1) == "dark"

    # Check that current theme is loaded
    assert dialog.theme_combo.currentText() == "dark"


def test_transcription_tab_has_model_settings(qtbot):
    """Test that transcription tab has model settings."""
    pytest.importorskip("pytest_qt")
    from PySide6.QtWidgets import QApplication, QComboBox

    from flowscribe.gui.dialogs.settings_dialog import SettingsDialog

    app = QApplication.instance()
    if not app:
        pytest.skip("QApplication not available")

    settings = {"model_name": "small", "language": "auto", "preset": "none"}

    dialog = SettingsDialog(None, settings)
    qtbot.addWidget(dialog)

    # Check that model combo exists
    assert hasattr(dialog, "model_combo")
    assert isinstance(dialog.model_combo, QComboBox)

    # Check that language combo exists
    assert hasattr(dialog, "language_combo")
    assert isinstance(dialog.language_combo, QComboBox)

    # Check that preset combo exists
    assert hasattr(dialog, "preset_combo")
    assert isinstance(dialog.preset_combo, QComboBox)


def test_network_tab_has_network_settings(qtbot):
    """Test that network tab has network settings."""
    pytest.importorskip("pytest_qt")
    from PySide6.QtWidgets import QApplication, QComboBox, QLineEdit

    from flowscribe.gui.dialogs.settings_dialog import SettingsDialog

    app = QApplication.instance()
    if not app:
        pytest.skip("QApplication not available")

    settings = {"network_family": "auto", "proxy": None, "cookies_path": None}

    dialog = SettingsDialog(None, settings)
    qtbot.addWidget(dialog)

    # Check that network combo exists
    assert hasattr(dialog, "network_combo")
    assert isinstance(dialog.network_combo, QComboBox)

    # Check that proxy input exists
    assert hasattr(dialog, "proxy_input")
    assert isinstance(dialog.proxy_input, QLineEdit)

    # Check that cookies input exists
    assert hasattr(dialog, "cookies_input")
    assert isinstance(dialog.cookies_input, QLineEdit)


def test_advanced_tab_has_progressive_settings(qtbot):
    """Test that advanced tab has progressive transcription settings."""
    pytest.importorskip("pytest_qt")
    from PySide6.QtWidgets import QApplication, QCheckBox, QSpinBox

    from flowscribe.gui.dialogs.settings_dialog import SettingsDialog

    app = QApplication.instance()
    if not app:
        pytest.skip("QApplication not available")

    settings = {
        "progressive_enabled": True,
        "progressive_resume": True,
        "progressive_chunk_seconds": 30.0,
        "progressive_max_workers": 1,
    }

    dialog = SettingsDialog(None, settings)
    qtbot.addWidget(dialog)

    # Check that progressive enabled checkbox exists
    assert hasattr(dialog, "progressive_enabled_check")
    assert isinstance(dialog.progressive_enabled_check, QCheckBox)

    # Check that progressive resume checkbox exists
    assert hasattr(dialog, "progressive_resume_check")
    assert isinstance(dialog.progressive_resume_check, QCheckBox)

    # Check that chunk seconds spin box exists
    assert hasattr(dialog, "progressive_chunk_seconds_spin")
    assert isinstance(dialog.progressive_chunk_seconds_spin, QSpinBox)

    # Check that max workers spin box exists
    assert hasattr(dialog, "progressive_max_workers_spin")
    assert isinstance(dialog.progressive_max_workers_spin, QSpinBox)


def test_theme_change_applies_immediately(qtbot):
    """Test that theme change applies immediately."""
    pytest.importorskip("pytest_qt")
    from PySide6.QtWidgets import QApplication

    from flowscribe.gui.dialogs.settings_dialog import SettingsDialog

    app = QApplication.instance()
    if not app:
        pytest.skip("QApplication not available")

    settings = {"theme": "light"}

    dialog = SettingsDialog(None, settings)
    qtbot.addWidget(dialog)

    # Change theme to dark
    dialog.theme_combo.setCurrentText("dark")

    # Check that theme was applied (stylesheet should change)
    stylesheet = app.styleSheet()
    assert len(stylesheet) > 0
    assert "FlowScribe Dark Theme" in stylesheet


def test_settings_collection_includes_all_tabs(qtbot):
    """Test that settings collection includes settings from all tabs."""
    pytest.importorskip("pytest_qt")
    from PySide6.QtWidgets import QApplication

    from flowscribe.gui.dialogs.settings_dialog import SettingsDialog

    app = QApplication.instance()
    if not app:
        pytest.skip("QApplication not available")

    settings = {
        "theme": "light",
        "output_dir": "outputs",
        "model_name": "small",
        "language": "auto",
        "preset": "none",
        "output_formats": ("txt", "md", "json"),
        "timestamps": True,
        "word_timestamps": False,
        "overwrite": False,
        "network_family": "auto",
        "proxy": None,
        "cookies_path": None,
        "progressive_enabled": True,
        "progressive_resume": True,
        "progressive_chunk_seconds": 30.0,
        "progressive_max_workers": 1,
    }

    dialog = SettingsDialog(None, settings)
    qtbot.addWidget(dialog)

    # Collect settings
    collected = dialog._collect_settings()

    # Check that all settings are present
    assert "theme" in collected
    assert "output_dir" in collected
    assert "model_name" in collected
    assert "language" in collected
    assert "preset" in collected
    assert "output_formats" in collected
    assert "timestamps" in collected
    assert "word_timestamps" in collected
    assert "overwrite" in collected
    assert "network_family" in collected
    assert "proxy" in collected
    assert "cookies_path" in collected
    assert "progressive_enabled" in collected
    assert "progressive_resume" in collected
    assert "progressive_chunk_seconds" in collected
    assert "progressive_max_workers" in collected
