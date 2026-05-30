"""Test queue URL addition functionality."""
import pytest
from unittest.mock import Mock, patch
from pathlib import Path
from PySide6.QtWidgets import QApplication
from flowscribe.gui.views.queue_view import QueueView
from flowscribe.tasks.queue_models import QueueItem, QueueItemSettings
from flowscribe.tasks.models import SourceSpec


@pytest.fixture
def qt_app():
    """Ensure QApplication exists for Qt widgets."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def queue_view(qt_app):
    """Create QueueView instance."""
    settings = {
        "output_dir": "outputs",
        "model_name": "small",
        "language": None,
        "preset": None,
        "output_formats": ("txt", "json"),
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
    view = QueueView(settings)
    yield view
    view.deleteLater()


def test_add_urls_button_emits_signal(queue_view):
    """Test that Add URLs button emits signal with text."""
    # Setup signal spy
    signal_received = []
    queue_view.enqueue_urls_requested.connect(lambda text: signal_received.append(text))

    # Set URL text
    test_url = "https://www.youtube.com/watch?v=test"
    queue_view._url_input.setPlainText(test_url)

    # Click Add URLs button
    queue_view._add_urls_btn.click()

    # Verify signal was emitted
    assert len(signal_received) == 1
    assert signal_received[0] == test_url

    # Verify input was cleared
    assert queue_view._url_input.toPlainText() == ""


def test_add_urls_empty_input_shows_message(queue_view):
    """Test that empty input shows error message."""
    # Clear input
    queue_view._url_input.clear()

    # Click Add URLs button
    queue_view._add_urls_btn.click()

    # Verify status message
    assert "Please enter at least one URL" in queue_view._status_label.text()


def test_add_urls_with_multiple_urls(queue_view):
    """Test adding multiple URLs at once."""
    # Setup signal spy
    signal_received = []
    queue_view.enqueue_urls_requested.connect(lambda text: signal_received.append(text))

    # Set multiple URLs
    test_urls = "https://www.youtube.com/watch?v=test1\nhttps://www.youtube.com/watch?v=test2"
    queue_view._url_input.setPlainText(test_urls)

    # Click Add URLs button
    queue_view._add_urls_btn.click()

    # Verify signal was emitted with all URLs
    assert len(signal_received) == 1
    assert "test1" in signal_received[0]
    assert "test2" in signal_received[0]


def test_ctrl_enter_triggers_add_urls(queue_view):
    """Test that Ctrl+Enter triggers URL addition."""
    from PySide6.QtCore import Qt, QEvent
    from PySide6.QtGui import QKeyEvent
    from PySide6.QtWidgets import QApplication

    # Setup signal spy
    signal_received = []
    queue_view.enqueue_urls_requested.connect(lambda text: signal_received.append(text))

    # Set URL text
    test_url = "https://www.youtube.com/watch?v=test"
    queue_view._url_input.setPlainText(test_url)

    # Simulate Ctrl+Enter key press through eventFilter
    key_event = QKeyEvent(
        QEvent.Type.KeyPress,
        Qt.Key.Key_Return,
        Qt.KeyboardModifier.ControlModifier
    )
    # Call eventFilter directly since we're testing the filter logic
    result = queue_view.eventFilter(queue_view._url_input, key_event)

    # Verify event was handled
    assert result is True

    # Verify signal was emitted
    assert len(signal_received) == 1
    assert signal_received[0] == test_url
