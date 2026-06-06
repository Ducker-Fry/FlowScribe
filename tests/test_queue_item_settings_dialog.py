"""Tests for queue item settings dialog."""

from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QPushButton, QScrollArea

from flowscribe.tasks.models import SourceSpec
from flowscribe.gui.dialogs.queue_item_settings_dialog import QueueItemSettingsDialog
from flowscribe.tasks.queue_models import QueueItemSettings


@pytest.fixture(scope="module")
def qapp():
    """Create QApplication instance for tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


def test_dialog_loads_url_source_settings(qapp):
    """Test that dialog loads URL source settings correctly."""
    settings = QueueItemSettings(
        output_dir=Path("outputs"),
        model_name="small",
        language="en",
    )
    source = SourceSpec(
        kind="url",
        value="https://example.com/video",
        keep_media=True,
        url_media_kind="video",
        auto_bind_media=True,
    )

    dialog = QueueItemSettingsDialog(None, settings, source, "Test Item")

    # Verify URL media settings are loaded
    assert dialog.keep_media_check.isChecked() is True
    assert dialog.media_kind_combo.currentText() == "video"
    assert dialog.auto_bind_media_check.isChecked() is True


def test_dialog_hides_media_group_for_local_source(qapp):
    """Test that media group is hidden for local sources."""
    settings = QueueItemSettings()
    source = SourceSpec(kind="local", value="/path/to/file.mp3")

    dialog = QueueItemSettingsDialog(None, settings, source, "Test Item")

    # Verify media group is hidden
    assert dialog._media_group.isHidden() is True


def test_dialog_keeps_action_buttons_outside_scroll_area(qapp):
    """Long settings content should scroll while action buttons stay reachable."""
    settings = QueueItemSettings()
    source = SourceSpec(kind="url", value="https://example.com/video")

    dialog = QueueItemSettingsDialog(None, settings, source, "Test Item")

    assert dialog.minimumWidth() <= 520
    assert dialog.minimumHeight() <= 420
    assert dialog.isSizeGripEnabled() is True

    scroll_area = dialog.findChild(QScrollArea)
    assert scroll_area is not None
    assert scroll_area.widgetResizable() is True

    button_texts = {
        button.text()
        for button in dialog.findChildren(QPushButton)
        if button.parent() is dialog
    }
    assert {"Reset to Defaults", "Cancel", "Apply"}.issubset(button_texts)


def test_dialog_returns_updated_source(qapp):
    """Test that dialog returns updated source with new keep_media setting."""
    settings = QueueItemSettings()
    source = SourceSpec(
        kind="url",
        value="https://example.com/video",
        keep_media=False,
        url_media_kind="audio",
    )

    dialog = QueueItemSettingsDialog(None, settings, source, "Test Item")

    # Simulate user changing settings
    dialog.keep_media_check.setChecked(True)
    dialog.media_kind_combo.setCurrentText("video")
    dialog.auto_bind_media_check.setChecked(True)

    # Accept dialog
    dialog.accept()

    # Get updated settings and source
    result = dialog.get_settings()
    assert result is not None
    updated_settings, updated_source = result

    # Verify source was updated
    assert updated_source.keep_media is True
    assert updated_source.url_media_kind == "video"
    assert updated_source.auto_bind_media is True
    # Verify original source fields are preserved
    assert updated_source.kind == "url"
    assert updated_source.value == "https://example.com/video"


def test_dialog_preserves_source_fields(qapp):
    """Test that dialog preserves all source fields when updating."""
    settings = QueueItemSettings()
    source = SourceSpec(
        kind="url",
        value="https://example.com/video",
        recursive=False,
        keep_media=False,
        url_media_kind="audio",
        media_output_dir=Path("/custom/output"),
        auto_bind_media=False,
    )

    dialog = QueueItemSettingsDialog(None, settings, source, "Test Item")
    dialog.keep_media_check.setChecked(True)
    dialog.accept()

    result = dialog.get_settings()
    assert result is not None
    _, updated_source = result

    # Verify all fields are preserved
    assert updated_source.kind == source.kind
    assert updated_source.value == source.value
    assert updated_source.recursive == source.recursive
    assert updated_source.media_output_dir == source.media_output_dir
    # Only keep_media should change
    assert updated_source.keep_media is True
