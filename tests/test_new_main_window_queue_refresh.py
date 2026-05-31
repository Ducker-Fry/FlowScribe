"""Tests for queue state synchronization in the stacked main window."""

from datetime import datetime
from pathlib import Path

from flowscribe.tasks.models import SourceSpec
from flowscribe.tasks.queue_models import QueueItem, QueueItemSettings, generate_queue_item_id
from flowscribe.tasks.queue_store import BatchQueueStore


def test_new_main_window_loads_existing_queue_on_startup(monkeypatch, qtbot, tmp_path):
    """Queue items already on disk should be visible before adding new items."""
    queue_path = tmp_path / "batch-queue.json"
    source = SourceSpec(kind="url", value="https://example.com/already-queued")
    existing_item = QueueItem(
        item_id=generate_queue_item_id(source),
        source=source,
        settings=QueueItemSettings(output_dir=Path("outputs")),
        status="pending",
        created_at=datetime.now(),
        title="Already Queued",
    )
    BatchQueueStore(queue_path).save_items([existing_item])

    from flowscribe.gui import new_main_window

    monkeypatch.setattr(
        new_main_window,
        "batch_queue_store",
        lambda: BatchQueueStore(queue_path),
    )

    window = new_main_window.NewMainWindow()
    qtbot.addWidget(window)

    assert window._queue_view._queue_list.count() == 1
    assert "1 total | 1 pending" in window._queue_view._queue_summary_label.text()


def test_new_main_window_watches_queue_directory_before_file_exists(
    monkeypatch,
    qtbot,
    tmp_path,
):
    """External queue file creation should be picked up after startup."""
    queue_path = tmp_path / "batch-queue.json"

    from flowscribe.gui import new_main_window

    monkeypatch.setattr(
        new_main_window,
        "batch_queue_store",
        lambda: BatchQueueStore(queue_path),
    )

    window = new_main_window.NewMainWindow()
    qtbot.addWidget(window)

    assert window._queue_view._queue_list.count() == 0
    assert window._queue_file_watcher is not None
    assert str(queue_path.parent) in window._queue_file_watcher.directories()

    source = SourceSpec(kind="url", value="https://example.com/newly-created")
    item = QueueItem(
        item_id=generate_queue_item_id(source),
        source=source,
        settings=QueueItemSettings(output_dir=Path("outputs")),
        status="pending",
        created_at=datetime.now(),
        title="Newly Created",
    )
    BatchQueueStore(queue_path).save_items([item])

    window._on_queue_directory_changed(str(queue_path.parent))

    assert window._queue_view._queue_list.count() == 1
    assert str(queue_path) in window._queue_file_watcher.files()
