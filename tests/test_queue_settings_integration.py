"""Integration test for queue item settings editing workflow."""

from pathlib import Path

import pytest

from flowscribe.app.models import SourceSpec
from flowscribe.queue.models import QueueItem, QueueItemSettings, generate_queue_item_id
from flowscribe.queue.store import BatchQueueStore


def test_queue_item_settings_persistence(tmp_path):
    """Test that edited settings persist in queue store."""
    # Create queue store
    queue_file = tmp_path / "test_queue.json"
    store = BatchQueueStore(queue_file)

    # Create item with default settings
    source = SourceSpec(kind="local", value=str(tmp_path / "test.mp3"))
    default_settings = QueueItemSettings()
    item = QueueItem(
        item_id=generate_queue_item_id(source),
        source=source,
        settings=default_settings,
    )
    store.enqueue(item)

    # Verify item was added with default settings
    retrieved_item = store.get_item(item.item_id)
    assert retrieved_item is not None
    assert retrieved_item.settings.model_name == "small"
    assert retrieved_item.settings.language is None
    assert retrieved_item.settings.progressive_chunk_seconds == 30.0

    # Simulate editing settings (what the dialog would do)
    updated_settings = QueueItemSettings(
        output_dir=Path("custom_output"),
        model_name="large-v3",
        language="zh",
        progressive_chunk_seconds=60.0,
        output_formats=("txt", "srt"),
    )

    # Update item with new settings
    store.update_item(item.item_id, settings=updated_settings)

    # Retrieve again and verify settings persisted
    final_item = store.get_item(item.item_id)
    assert final_item is not None
    assert final_item.settings.model_name == "large-v3"
    assert final_item.settings.language == "zh"
    assert final_item.settings.progressive_chunk_seconds == 60.0
    assert final_item.settings.output_formats == ("txt", "srt")
    assert str(final_item.settings.output_dir) == "custom_output"

    # Simulate opening dialog again - should load the updated settings
    # (This is what QueueItemSettingsDialog does in __init__)
    reopened_settings = final_item.settings
    assert reopened_settings.model_name == "large-v3"
    assert reopened_settings.language == "zh"
    assert reopened_settings.progressive_chunk_seconds == 60.0


def test_multiple_edits_preserve_latest_settings(tmp_path):
    """Test that multiple edits preserve the latest settings."""
    queue_file = tmp_path / "test_queue.json"
    store = BatchQueueStore(queue_file)

    source = SourceSpec(kind="local", value=str(tmp_path / "test.mp3"))
    item = QueueItem(
        item_id=generate_queue_item_id(source),
        source=source,
        settings=QueueItemSettings(),
    )
    store.enqueue(item)

    # First edit
    item1 = store.get_item(item.item_id)
    settings1 = QueueItemSettings(model_name="base", language="en")
    store.update_item(item1.item_id, settings=settings1)

    # Second edit
    item2 = store.get_item(item.item_id)
    assert item2.settings.model_name == "base"
    assert item2.settings.language == "en"

    settings2 = QueueItemSettings(model_name="large-v3", language="zh")
    store.update_item(item2.item_id, settings=settings2)

    # Third edit
    item3 = store.get_item(item.item_id)
    assert item3.settings.model_name == "large-v3"
    assert item3.settings.language == "zh"

    settings3 = QueueItemSettings(model_name="medium", language="ja")
    store.update_item(item3.item_id, settings=settings3)

    # Final verification
    final = store.get_item(item.item_id)
    assert final.settings.model_name == "medium"
    assert final.settings.language == "ja"


def test_settings_independent_between_items(tmp_path):
    """Test that settings are independent between different queue items."""
    queue_file = tmp_path / "test_queue.json"
    store = BatchQueueStore(queue_file)

    # Create two items
    source1 = SourceSpec(kind="local", value=str(tmp_path / "test1.mp3"))
    source2 = SourceSpec(kind="local", value=str(tmp_path / "test2.mp3"))

    item1 = QueueItem(
        item_id=generate_queue_item_id(source1),
        source=source1,
        settings=QueueItemSettings(model_name="small"),
    )
    item2 = QueueItem(
        item_id=generate_queue_item_id(source2),
        source=source2,
        settings=QueueItemSettings(model_name="base"),
    )

    store.enqueue(item1)
    store.enqueue(item2)

    # Edit item1
    retrieved1 = store.get_item(item1.item_id)
    store.update_item(retrieved1.item_id, settings=QueueItemSettings(model_name="large-v3"))

    # Verify item1 changed but item2 didn't
    final1 = store.get_item(item1.item_id)
    final2 = store.get_item(item2.item_id)

    assert final1.settings.model_name == "large-v3"
    assert final2.settings.model_name == "base"
