"""Tests for queue batch edit settings functionality."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import QApplication

from flowscribe.tasks.models import SourceSpec
from flowscribe.gui.dialogs.queue_item_settings_dialog import QueueItemSettingsDialog
from flowscribe.gui.views.queue_view import QueueView
from flowscribe.tasks.queue_models import QueueItem, QueueItemSettings


@pytest.fixture
def qapp():
    """Ensure QApplication exists."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def queue_view(qapp):
    """Create QueueView instance."""
    settings = {"output_dir": "outputs"}
    view = QueueView(settings)
    return view


@pytest.fixture
def sample_items():
    """Create sample queue items."""
    items = []
    for i in range(3):
        source = SourceSpec(kind="url", value=f"https://example.com/video{i}")
        settings = QueueItemSettings(
            output_dir=Path("outputs"),
            model_name="small",
            language="en",
        )
        item = QueueItem(
            item_id=f"item-{i}",
            source=source,
            settings=settings,
            status="pending",
        )
        items.append(item)
    return items


def test_queue_view_emits_multiple_item_ids(queue_view, sample_items):
    """Test that QueueView emits list of item IDs when editing settings."""
    queue_view.refresh_queue(sample_items)

    # Check first two items
    queue_view._checked_item_ids.update({"item-0", "item-1"})
    queue_view._sync_all_card_check_states()

    # Connect signal to capture emitted value
    emitted_ids = []

    def capture_ids(ids):
        emitted_ids.append(ids)

    queue_view.edit_item_settings_requested.connect(capture_ids)

    # Trigger edit settings
    queue_view._on_edit_settings()

    # Verify signal emitted with list of IDs
    assert len(emitted_ids) == 1
    assert emitted_ids[0] == ["item-0", "item-1"]


def test_settings_dialog_batch_mode_title(qapp, sample_items):
    """Test that dialog shows batch mode title when is_batch=True."""
    item = sample_items[0]
    dialog = QueueItemSettingsDialog(
        None,
        item.settings,
        item.source,
        "3 items",
        is_batch=True,
    )
    assert "Batch Edit Settings" in dialog.windowTitle()
    assert "3 items" in dialog.windowTitle()


def test_settings_dialog_single_mode_title(qapp, sample_items):
    """Test that dialog shows single item title when is_batch=False."""
    item = sample_items[0]
    dialog = QueueItemSettingsDialog(
        None,
        item.settings,
        item.source,
        "https://example.com/video0",
        is_batch=False,
    )
    assert "Edit Settings -" in dialog.windowTitle()
    assert "https://example.com/video0" in dialog.windowTitle()


def test_batch_edit_applies_to_all_items(qapp, sample_items):
    """Test that batch edit applies settings to all selected items."""
    from flowscribe.tasks.queue_store import BatchQueueStore

    # Create mock store
    store = MagicMock(spec=BatchQueueStore)
    store.get_item.return_value = sample_items[0]

    # Simulate batch edit for 3 items
    item_ids = ["item-0", "item-1", "item-2"]

    # Get first item as template
    first_item = store.get_item(item_ids[0])
    assert first_item is not None

    # Create new settings
    new_settings = QueueItemSettings(
        output_dir=Path("new_outputs"),
        model_name="large-v3",
        language="zh",
    )

    # Apply to all items
    for item_id in item_ids:
        store.update_item(item_id, settings=new_settings)

    # Verify update_item called for each item
    assert store.update_item.call_count == 3
    for item_id in item_ids:
        store.update_item.assert_any_call(item_id, settings=new_settings)


def test_single_item_edit_backward_compatibility(queue_view, sample_items):
    """Test that single item edit still works (backward compatibility)."""
    queue_view.refresh_queue(sample_items)

    # Check only first item
    queue_view._checked_item_ids.add("item-0")
    queue_view._sync_all_card_check_states()

    # Connect signal to capture emitted value
    emitted_ids = []

    def capture_ids(ids):
        emitted_ids.append(ids)

    queue_view.edit_item_settings_requested.connect(capture_ids)

    # Trigger edit settings
    queue_view._on_edit_settings()

    # Verify signal emitted with single-item list
    assert len(emitted_ids) == 1
    assert emitted_ids[0] == ["item-0"]
