"""Test queue item transcript path and run detail tracking."""

from pathlib import Path


from flowscribe.app.models import SourceSpec
from flowscribe.core.models import OutputArtifacts
from flowscribe.queue.models import QueueItem, QueueItemSettings
from flowscribe.queue.store import BatchQueueStore


def test_queue_item_with_transcript_path():
    """Test QueueItem can store transcript_path."""
    item = QueueItem(
        item_id="test123",
        source=SourceSpec(kind="local", value="/path/to/audio.mp3"),
        settings=QueueItemSettings(),
        transcript_path=Path("/path/to/transcript.json"),
        run_detail="Test run output",
    )
    assert item.transcript_path == Path("/path/to/transcript.json")
    assert item.run_detail == "Test run output"


def test_queue_item_without_transcript_path():
    """Test QueueItem defaults to None for transcript_path and run_detail."""
    item = QueueItem(
        item_id="test123",
        source=SourceSpec(kind="local", value="/path/to/audio.mp3"),
        settings=QueueItemSettings(),
    )
    assert item.transcript_path is None
    assert item.run_detail is None


def test_store_serialization_with_transcript_path(tmp_path):
    """Test BatchQueueStore can serialize and deserialize transcript_path."""
    store_path = tmp_path / "queue.json"
    store = BatchQueueStore(store_path)

    item = QueueItem(
        item_id="test123",
        source=SourceSpec(kind="local", value="/path/to/audio.mp3"),
        settings=QueueItemSettings(),
        status="completed",
        transcript_path=Path("/path/to/transcript.json"),
        run_detail="Transcription completed successfully\nDuration: 120s",
    )

    store.save_items([item])
    loaded = store.load_items()

    assert len(loaded) == 1
    assert loaded[0].transcript_path == Path("/path/to/transcript.json")
    assert loaded[0].run_detail == "Transcription completed successfully\nDuration: 120s"


def test_store_serialization_without_transcript_path(tmp_path):
    """Test BatchQueueStore handles None transcript_path correctly."""
    store_path = tmp_path / "queue.json"
    store = BatchQueueStore(store_path)

    item = QueueItem(
        item_id="test123",
        source=SourceSpec(kind="local", value="/path/to/audio.mp3"),
        settings=QueueItemSettings(),
        status="pending",
    )

    store.save_items([item])
    loaded = store.load_items()

    assert len(loaded) == 1
    assert loaded[0].transcript_path is None
    assert loaded[0].run_detail is None


def test_output_artifacts_json_path():
    """Test OutputArtifacts.json_path property."""
    artifacts = OutputArtifacts(
        paths=(
            Path("/output/transcript.txt"),
            Path("/output/transcript.md"),
            Path("/output/transcript.json"),
        )
    )
    assert artifacts.json_path == Path("/output/transcript.json")


def test_output_artifacts_json_path_not_found():
    """Test OutputArtifacts.json_path returns None when no JSON file."""
    artifacts = OutputArtifacts(
        paths=(
            Path("/output/transcript.txt"),
            Path("/output/transcript.md"),
        )
    )
    assert artifacts.json_path is None


def test_store_update_with_transcript_path(tmp_path):
    """Test BatchQueueStore.update_item can update transcript_path."""
    store_path = tmp_path / "queue.json"
    store = BatchQueueStore(store_path)

    item = QueueItem(
        item_id="test123",
        source=SourceSpec(kind="local", value="/path/to/audio.mp3"),
        settings=QueueItemSettings(),
        status="running",
    )

    store.save_items([item])

    updated = store.update_item(
        "test123",
        status="completed",
        transcript_path=Path("/output/transcript.json"),
        run_detail="Completed in 45s",
    )

    assert updated is not None
    assert updated.status == "completed"
    assert updated.transcript_path == Path("/output/transcript.json")
    assert updated.run_detail == "Completed in 45s"

    loaded = store.load_items()
    assert len(loaded) == 1
    assert loaded[0].transcript_path == Path("/output/transcript.json")
    assert loaded[0].run_detail == "Completed in 45s"
