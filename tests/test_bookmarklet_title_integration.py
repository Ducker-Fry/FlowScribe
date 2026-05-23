"""Integration test for bookmarklet title display."""

from pathlib import Path
from datetime import datetime
import pytest
import importlib
import importlib.util

from flowscribe.server.handlers import AddUrlHandler
from flowscribe.queue.store import BatchQueueStore


def test_bookmarklet_title_integration(tmp_path):
    """Test that bookmarklet-added URLs display with title in queue."""
    # Setup
    queue_file = tmp_path / "queue.json"
    output_dir = tmp_path / "outputs"
    output_dir.mkdir()

    handler = AddUrlHandler(
        queue_store_path=queue_file,
        default_output_dir=output_dir,
    )

    # Simulate bookmarklet adding URL with title
    url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    title = "Never Gonna Give You Up - Rick Astley"

    result = handler.add_url(url=url, title=title)

    # Verify result
    assert result["status"] == "queued"
    assert "position" in result

    # Load queue and verify item
    store = BatchQueueStore(queue_file)
    items = store.load_items()

    assert len(items) == 1
    item = items[0]

    # Verify title is stored
    assert item.title == title

    # Verify display_label uses title
    assert item.display_label == title
    assert item.display_label != url


def test_bookmarklet_without_title_fallback(tmp_path):
    """Test that URLs without title fall back to URL display."""
    # Setup
    queue_file = tmp_path / "queue.json"
    output_dir = tmp_path / "outputs"
    output_dir.mkdir()

    handler = AddUrlHandler(
        queue_store_path=queue_file,
        default_output_dir=output_dir,
    )

    # Add URL without title
    url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

    result = handler.add_url(url=url, title=None)

    # Verify result
    assert result["status"] == "queued"

    # Load queue and verify item
    store = BatchQueueStore(queue_file)
    items = store.load_items()

    assert len(items) == 1
    item = items[0]

    # Verify title is None
    assert item.title is None

    # Verify display_label falls back to URL
    assert item.display_label == url


def test_bookmarklet_batch_with_titles(tmp_path):
    """Test batch URL addition with titles."""
    # Setup
    queue_file = tmp_path / "queue.json"
    output_dir = tmp_path / "outputs"
    output_dir.mkdir()

    handler = AddUrlHandler(
        queue_store_path=queue_file,
        default_output_dir=output_dir,
    )

    # Simulate batch bookmarklet
    urls = [
        {"url": "https://www.youtube.com/watch?v=video1", "title": "Video 1 Title"},
        {"url": "https://www.youtube.com/watch?v=video2", "title": "Video 2 Title"},
        {"url": "https://www.youtube.com/watch?v=video3", "title": "Video 3 Title"},
    ]

    result = handler.add_urls(urls)

    # Verify result
    assert result["status"] == "completed"
    assert result["summary"]["queued"] == 3
    assert result["summary"]["duplicates"] == 0
    assert result["summary"]["errors"] == 0

    # Load queue and verify items
    store = BatchQueueStore(queue_file)
    items = store.load_items()

    assert len(items) == 3

    for i, item in enumerate(items):
        expected_title = f"Video {i+1} Title"
        assert item.title == expected_title
        assert item.display_label == expected_title


try:
    importlib.util.find_spec("PySide6")
    HAS_PYSIDE6 = True
except ImportError:
    HAS_PYSIDE6 = False


@pytest.mark.skipif(not HAS_PYSIDE6, reason="PySide6 not available")
def test_queue_view_format_with_bookmarklet_title(tmp_path):
    """Test that QueueView formats bookmarklet items with title."""
    from flowscribe.gui.views.queue_view import QueueView
    from flowscribe.app.models import SourceSpec
    from flowscribe.queue.models import QueueItem, QueueItemSettings
    from PySide6.QtWidgets import QApplication
    import sys

    # Ensure QApplication exists
    _ = QApplication.instance() or QApplication(sys.argv)

    # Create queue item as if added by bookmarklet
    source = SourceSpec(kind="url", value="https://www.bilibili.com/video/BV1xx411c7mD")
    settings = QueueItemSettings(
        output_dir=Path("outputs"),
        output_formats=("json",),
        model_name="small",
    )
    item = QueueItem(
        item_id="test123",
        source=source,
        settings=settings,
        status="pending",
        created_at=datetime.now(),
        title="【中文测试】这是一个B站视频标题",
    )

    # Create view with proper initialization
    view = QueueView({})
    display = view._format_item_display(item)

    # Should show Chinese title, not URL
    assert "【中文测试】这是一个B站视频标题" in display
    assert "[URL]" in display
    assert "bilibili.com" not in display
