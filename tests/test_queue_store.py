"""Tests for flowscribe.tasks.queue_store."""


import pytest

from flowscribe.tasks.models import SourceSpec
from flowscribe.tasks.queue_models import (
    QueueItem,
    QueueItemSettings,
    generate_queue_item_id,
)
from flowscribe.tasks.queue_store import BatchQueueStore


@pytest.fixture
def store(tmp_path):
    return BatchQueueStore(tmp_path / "queue.json")


def _make_item(url="https://example.com/a.mp4", status="pending"):
    source = SourceSpec(kind="url", value=url)
    return QueueItem(
        item_id=generate_queue_item_id(source),
        source=source,
        settings=QueueItemSettings(),
        status=status,
    )


def test_load_empty(store):
    assert store.load_items() == []


def test_enqueue_and_load(store):
    item = _make_item()
    result = store.enqueue(item)
    assert result is not None
    items = store.load_items()
    assert len(items) == 1
    assert items[0].item_id == item.item_id
    assert items[0].source.value == "https://example.com/a.mp4"


def test_enqueue_deduplication(store):
    item = _make_item()
    store.enqueue(item)
    duplicate = store.enqueue(item)
    assert duplicate is None
    assert len(store.load_items()) == 1


def test_dequeue_returns_first_pending(store):
    store.enqueue(_make_item("https://example.com/1.mp4"))
    store.enqueue(_make_item("https://example.com/2.mp4"))
    dequeued = store.dequeue()
    assert dequeued is not None
    assert dequeued.source.value == "https://example.com/1.mp4"
    assert dequeued.status == "running"


def test_dequeue_skips_non_pending(store):
    store.enqueue(_make_item("https://example.com/1.mp4"))
    store.dequeue()  # marks first as running
    store.enqueue(_make_item("https://example.com/2.mp4"))
    dequeued = store.dequeue()
    assert dequeued is not None
    assert dequeued.source.value == "https://example.com/2.mp4"


def test_dequeue_returns_none_when_empty(store):
    assert store.dequeue() is None


def test_update_item(store):
    item = _make_item()
    store.enqueue(item)
    updated = store.update_item(item.item_id, status="completed", error_message="done")
    assert updated is not None
    assert updated.status == "completed"
    assert updated.error_message == "done"
    reloaded = store.load_items()
    assert reloaded[0].status == "completed"


def test_remove_item(store):
    item = _make_item()
    store.enqueue(item)
    assert store.remove_item(item.item_id) is True
    assert store.load_items() == []


def test_remove_item_not_found(store):
    assert store.remove_item("nonexistent") is False


def test_remove_completed(store):
    store.enqueue(_make_item("https://example.com/1.mp4"))
    store.enqueue(_make_item("https://example.com/2.mp4"))
    items = store.load_items()
    store.update_item(items[0].item_id, status="completed")
    removed = store.remove_completed()
    assert removed == 1
    remaining = store.load_items()
    assert len(remaining) == 1
    assert remaining[0].source.value == "https://example.com/2.mp4"


def test_reorder(store):
    store.enqueue(_make_item("https://example.com/1.mp4"))
    store.enqueue(_make_item("https://example.com/2.mp4"))
    store.enqueue(_make_item("https://example.com/3.mp4"))
    items = store.load_items()
    reversed_ids = [items[2].item_id, items[1].item_id, items[0].item_id]
    store.reorder(reversed_ids)
    reloaded = store.load_items()
    assert reloaded[0].source.value == "https://example.com/3.mp4"
    assert reloaded[1].source.value == "https://example.com/2.mp4"
    assert reloaded[2].source.value == "https://example.com/1.mp4"


def test_pending_count(store):
    store.enqueue(_make_item("https://example.com/1.mp4"))
    store.enqueue(_make_item("https://example.com/2.mp4"))
    assert store.pending_count() == 2
    store.dequeue()
    assert store.pending_count() == 1


def test_find_duplicate(store):
    item = _make_item()
    store.enqueue(item)
    source = SourceSpec(kind="url", value="https://example.com/a.mp4")
    found = store.find_duplicate(source)
    assert found is not None
    assert found.item_id == item.item_id


def test_find_duplicate_ignores_completed(store):
    item = _make_item()
    store.enqueue(item)
    store.update_item(item.item_id, status="completed")
    source = SourceSpec(kind="url", value="https://example.com/a.mp4")
    assert store.find_duplicate(source) is None


def test_corrupt_file_recovery(store, tmp_path):
    store_path = tmp_path / "queue.json"
    store_path.write_text("not valid json", encoding="utf-8")
    items = store.load_items()
    assert items == []
    backups = list(tmp_path.glob("*.corrupt-*"))
    assert len(backups) == 1


def test_persistence_roundtrip(store):
    source = SourceSpec(kind="url", value="https://example.com/a.mp4")
    item = QueueItem(
        item_id=generate_queue_item_id(source),
        source=source,
        settings=QueueItemSettings(
            provider_name="native-engine",
            model_name="models/ggml-base.en.bin",
            native_threads=6,
        ),
    )
    store.enqueue(item)
    new_store = BatchQueueStore(store._path)
    items = new_store.load_items()
    assert len(items) == 1
    assert items[0].item_id == item.item_id
    assert items[0].source.kind == "url"
    assert items[0].settings.provider_name == "native-engine"
    assert items[0].settings.model_name == "models/ggml-base.en.bin"
    assert items[0].settings.native_threads == 6


def test_load_legacy_queue_settings_defaults_provider(store):
    source = SourceSpec(kind="url", value="https://example.com/a.mp4")
    item = _make_item()
    store.enqueue(item)
    payload = store._path.read_text(encoding="utf-8")
    payload = payload.replace('          "provider_name": "local-whisper",\n', "")
    payload = payload.replace('          "native_threads": null\n', '          "legacy_marker": true\n')
    store._path.write_text(payload, encoding="utf-8")

    items = store.load_items()

    assert len(items) == 1
    assert items[0].source.value == source.value
    assert items[0].settings.provider_name == "local-whisper"
    assert items[0].settings.native_threads is None
