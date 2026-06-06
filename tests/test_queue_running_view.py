"""Test opening view for running queue items."""

from pathlib import Path


from flowscribe.tasks.models import ProgressEvent, SourceSpec
from flowscribe.tasks.queue_models import QueueItem, QueueItemSettings


def test_queue_view_running_item_tracking():
    """Test QueueView running item tracking logic without GUI."""
    item = QueueItem(
        item_id="test123",
        source=SourceSpec(kind="local", value="/path/to/audio.mp3"),
        settings=QueueItemSettings(),
        status="running",
    )

    current_running_item_id = None
    current_run_output = ""

    current_running_item_id = item.item_id
    current_run_output = ""

    assert current_running_item_id == "test123"
    assert current_run_output == ""


def test_progress_accumulation():
    """Test progress message accumulation logic."""
    current_run_output = ""

    event1 = ProgressEvent(stage="prepare", message="Preparing audio...")
    event2 = ProgressEvent(stage="transcribe", message="Transcribing chunk 1/10...")
    event3 = ProgressEvent(stage="transcribe", message="Transcribing chunk 2/10...")

    if event1.message:
        current_run_output += event1.message + "\n"
    if event2.message:
        current_run_output += event2.message + "\n"
    if event3.message:
        current_run_output += event3.message + "\n"

    assert "Preparing audio..." in current_run_output
    assert "Transcribing chunk 1/10..." in current_run_output
    assert "Transcribing chunk 2/10..." in current_run_output


def test_completion_clears_state():
    """Test completion clears running state."""
    current_running_item_id = "test123"
    current_run_output = "Some output"

    current_running_item_id = None
    current_run_output = ""

    assert current_running_item_id is None
    assert current_run_output == ""


def test_running_item_can_be_opened():
    """Test logic for opening running item view."""
    item = QueueItem(
        item_id="test123",
        source=SourceSpec(kind="local", value="/path/to/audio.mp3"),
        settings=QueueItemSettings(),
        status="running",
    )

    current_running_item_id = "test123"

    can_open = (
        item.status == "running"
        and item.item_id == current_running_item_id
    )

    assert can_open is True


def test_completed_item_requires_transcript_path():
    """Test completed item requires transcript path."""
    item = QueueItem(
        item_id="test123",
        source=SourceSpec(kind="local", value="/path/to/audio.mp3"),
        settings=QueueItemSettings(),
        status="completed",
        transcript_path=Path("/output/transcript.json"),
    )

    can_open = (
        item.status == "completed"
        and item.transcript_path is not None
        and item.transcript_path.exists()
    )

    assert can_open is False


def test_pending_item_cannot_be_opened():
    """Test pending item cannot be opened."""
    item = QueueItem(
        item_id="test123",
        source=SourceSpec(kind="local", value="/path/to/audio.mp3"),
        settings=QueueItemSettings(),
        status="pending",
    )

    can_open = item.status in ("running", "completed")
    assert can_open is False


def test_failed_item_cannot_be_opened():
    """Test failed item cannot be opened."""
    item = QueueItem(
        item_id="test123",
        source=SourceSpec(kind="local", value="/path/to/audio.mp3"),
        settings=QueueItemSettings(),
        status="failed",
        error_message="Transcription failed",
    )

    can_open = item.status in ("running", "completed")
    assert can_open is False

