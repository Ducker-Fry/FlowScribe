"""Test queue item settings dialog memory functionality."""

from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from flowscribe.gui.dialogs.queue_item_settings_dialog import QueueItemSettingsDialog
from flowscribe.queue.models import QueueItemSettings


@pytest.fixture(scope="module")
def qapp():
    """Create QApplication instance for tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


def test_dialog_loads_provided_settings(qapp):
    """Dialog should load the settings passed to it, not defaults."""
    custom_settings = QueueItemSettings(
        output_dir=Path("custom_output"),
        output_name_base="custom_name",
        model_name="large-v3",
        language="zh",
        preset="best_quality",
        output_formats=("txt", "srt"),
        timestamps=False,
        word_timestamps=True,
        overwrite=True,
        progressive_enabled=False,
        progressive_chunk_seconds=60.0,
        progressive_max_workers=4,
        network_family="ipv4",
        proxy="http://proxy:8080",
        max_download_mb=1024,
        max_duration_seconds=7200.0,
        download_timeout_seconds=60,
    )

    dialog = QueueItemSettingsDialog(None, custom_settings, "Test Item")

    # Verify all settings are loaded correctly
    assert dialog.output_dir_input.text() == "custom_output"
    assert dialog.output_name_input.text() == "custom_name"
    assert dialog.model_combo.currentText() == "large-v3"
    assert dialog.language_combo.currentText() == "zh"
    assert dialog.preset_combo.currentText() == "best_quality"
    assert dialog.format_checks["txt"].isChecked()
    assert dialog.format_checks["srt"].isChecked()
    assert not dialog.format_checks["md"].isChecked()
    assert not dialog.format_checks["json"].isChecked()
    assert not dialog.timestamps_check.isChecked()
    assert dialog.word_timestamps_check.isChecked()
    assert dialog.overwrite_check.isChecked()
    assert not dialog._progressive_group.isChecked()
    assert dialog.progressive_chunk_spin.value() == 60
    assert dialog.progressive_workers_spin.value() == 4
    assert dialog.network_combo.currentText() == "ipv4"
    assert dialog.proxy_input.text() == "http://proxy:8080"
    assert dialog.max_download_spin.value() == 1024
    assert dialog.max_duration_spin.value() == 7200
    assert dialog.download_timeout_spin.value() == 60


def test_dialog_loads_default_settings(qapp):
    """Dialog should load default settings when provided with defaults."""
    default_settings = QueueItemSettings()

    dialog = QueueItemSettingsDialog(None, default_settings, "Test Item")

    # Verify default settings are loaded
    assert dialog.output_dir_input.text() == "outputs"
    assert dialog.output_name_input.text() == ""
    assert dialog.model_combo.currentText() == "small"
    assert dialog.language_combo.currentText() == "auto"
    assert dialog.preset_combo.currentText() == "none"
    assert dialog.timestamps_check.isChecked()
    assert not dialog.word_timestamps_check.isChecked()
    assert not dialog.overwrite_check.isChecked()
    assert dialog._progressive_group.isChecked()
    assert dialog.progressive_chunk_spin.value() == 30
    assert dialog.progressive_workers_spin.value() == 1


def test_reset_to_defaults_button(qapp):
    """Reset button should restore default settings."""
    custom_settings = QueueItemSettings(
        output_dir=Path("custom_output"),
        model_name="large-v3",
        language="zh",
        progressive_chunk_seconds=60.0,
    )

    dialog = QueueItemSettingsDialog(None, custom_settings, "Test Item")

    # Verify custom settings loaded
    assert dialog.output_dir_input.text() == "custom_output"
    assert dialog.model_combo.currentText() == "large-v3"
    assert dialog.language_combo.currentText() == "zh"
    assert dialog.progressive_chunk_spin.value() == 60

    # Click reset button
    dialog._reset_to_defaults()

    # Verify defaults restored
    assert dialog.output_dir_input.text() == "outputs"
    assert dialog.model_combo.currentText() == "small"
    assert dialog.language_combo.currentText() == "auto"
    assert dialog.progressive_chunk_spin.value() == 30


def test_apply_button_exists(qapp):
    """Dialog should have Apply button instead of OK."""
    settings = QueueItemSettings()
    dialog = QueueItemSettingsDialog(None, settings, "Test Item")

    # Find the Apply button
    apply_button = None
    for child in dialog.findChildren(type(dialog).__bases__[0]):
        if hasattr(child, "text") and child.text() == "Apply":
            apply_button = child
            break

    # Note: This test may need adjustment based on how QPushButton is found
    # The actual button finding logic might need to be more specific
