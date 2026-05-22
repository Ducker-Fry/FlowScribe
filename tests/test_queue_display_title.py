"""Tests for queue item display with title."""

from pathlib import Path
from datetime import datetime
from unittest.mock import patch
import pytest
import importlib
import importlib.util

from flowscribe.app.models import SourceSpec
from flowscribe.queue.models import QueueItem, QueueItemSettings


try:
    importlib.util.find_spec("PySide6")
    HAS_PYSIDE6 = True
except ImportError:
    HAS_PYSIDE6 = False


@pytest.fixture
def mock_queue_item_with_title():
    """Create a queue item with title."""
    source = SourceSpec(kind="url", value="https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    settings = QueueItemSettings(
        output_dir=Path("outputs"),
        output_formats=("json",),
        model_name="small",
    )
    return QueueItem(
        item_id="test123",
        source=source,
        settings=settings,
        status="pending",
        created_at=datetime.now(),
        title="Never Gonna Give You Up - Rick Astley",
    )


@pytest.fixture
def mock_queue_item_without_title():
    """Create a queue item without title."""
    source = SourceSpec(kind="url", value="https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    settings = QueueItemSettings(
        output_dir=Path("outputs"),
        output_formats=("json",),
        model_name="small",
    )
    return QueueItem(
        item_id="test456",
        source=source,
        settings=settings,
        status="pending",
        created_at=datetime.now(),
        title=None,
    )


def test_queue_item_display_label_with_title(mock_queue_item_with_title):
    """Test that display_label returns title when available."""
    item = mock_queue_item_with_title
    assert item.display_label == "Never Gonna Give You Up - Rick Astley"


def test_queue_item_display_label_without_title(mock_queue_item_without_title):
    """Test that display_label returns URL when title is not available."""
    item = mock_queue_item_without_title
    assert item.display_label == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


@pytest.mark.skipif(not HAS_PYSIDE6, reason="PySide6 not available")
def test_format_item_display_with_title(mock_queue_item_with_title):
    """Test queue view formatting with title."""
    from flowscribe.gui.views.queue_view import QueueView

    # Mock Qt components
    with patch('PySide6.QtWidgets.QWidget.__init__', return_value=None):
        with patch.object(QueueView, '_setup_ui'):
            view = QueueView({})
            display = view._format_item_display(mock_queue_item_with_title)

            # Should show title, not URL
            assert "Never Gonna Give You Up - Rick Astley" in display
            assert "[URL]" in display
            assert "youtube.com" not in display  # URL should not be shown


@pytest.mark.skipif(not HAS_PYSIDE6, reason="PySide6 not available")
def test_format_item_display_without_title(mock_queue_item_without_title):
    """Test queue view formatting without title (fallback to URL)."""
    from flowscribe.gui.views.queue_view import QueueView

    # Mock Qt components
    with patch('PySide6.QtWidgets.QWidget.__init__', return_value=None):
        with patch.object(QueueView, '_setup_ui'):
            view = QueueView({})
            display = view._format_item_display(mock_queue_item_without_title)

            # Should show URL when no title
            assert "youtube.com" in display
            assert "[URL]" in display


@pytest.mark.skipif(not HAS_PYSIDE6, reason="PySide6 not available")
def test_format_item_display_truncates_long_title():
    """Test that long titles are truncated."""
    from flowscribe.gui.views.queue_view import QueueView

    # Create item with very long title
    source = SourceSpec(kind="url", value="https://example.com/video")
    settings = QueueItemSettings(
        output_dir=Path("outputs"),
        output_formats=("json",),
        model_name="small",
    )
    long_title = "A" * 100  # 100 character title
    item = QueueItem(
        item_id="test789",
        source=source,
        settings=settings,
        status="pending",
        created_at=datetime.now(),
        title=long_title,
    )

    # Mock Qt components
    with patch('PySide6.QtWidgets.QWidget.__init__', return_value=None):
        with patch.object(QueueView, '_setup_ui'):
            view = QueueView({})
            display = view._format_item_display(item)

            # Should be truncated to 80 chars (77 + "...")
            assert len(display) < len(long_title) + 20  # Account for icon and [URL] prefix
            assert "..." in display


@pytest.mark.skipif(not HAS_PYSIDE6, reason="PySide6 not available")
def test_local_file_display_unchanged():
    """Test that local file display is not affected by title changes."""
    from flowscribe.gui.views.queue_view import QueueView

    source = SourceSpec(kind="local", value="/path/to/video.mp4")
    settings = QueueItemSettings(
        output_dir=Path("outputs"),
        output_formats=("json",),
        model_name="small",
    )
    item = QueueItem(
        item_id="test999",
        source=source,
        settings=settings,
        status="pending",
        created_at=datetime.now(),
        title="Some Title",  # Title should be ignored for local files
    )

    # Mock Qt components
    with patch('PySide6.QtWidgets.QWidget.__init__', return_value=None):
        with patch.object(QueueView, '_setup_ui'):
            view = QueueView({})
            display = view._format_item_display(item)

            # Should show filename, not title
            assert "video.mp4" in display
            assert "[FILE]" in display
            assert "Some Title" not in display
