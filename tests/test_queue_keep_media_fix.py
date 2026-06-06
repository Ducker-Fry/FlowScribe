"""Integration test for queue item keep_media fix."""

from dataclasses import replace
from pathlib import Path

from flowscribe.tasks.models import SourceSpec
from flowscribe.tasks.queue_models import QueueItem, QueueItemSettings, generate_queue_item_id


def test_queue_item_source_update():
    """Test that queue item source can be updated with dataclasses.replace."""
    # Create a queue item with keep_media=False
    source = SourceSpec(
        kind="url",
        value="https://example.com/video",
        keep_media=False,
        url_media_kind="audio",
    )
    settings = QueueItemSettings(output_dir=Path("outputs"))
    item = QueueItem(
        item_id=generate_queue_item_id(source),
        source=source,
        settings=settings,
    )

    # Verify initial state
    assert item.source.keep_media is False

    # Update the source with keep_media=True
    updated_source = SourceSpec(
        kind=source.kind,
        value=source.value,
        recursive=source.recursive,
        keep_media=True,  # Changed
        url_media_kind="video",  # Changed
        media_output_dir=source.media_output_dir,
        auto_bind_media=True,  # Changed
        download_options=source.download_options,
    )

    # Update the item using dataclasses.replace
    updated_item = replace(item, source=updated_source)
    assert updated_item.source.keep_media is True
    assert updated_item.source.url_media_kind == "video"
    assert updated_item.source.auto_bind_media is True


def test_queue_item_to_job_preserves_keep_media():
    """Test that QueueItem.to_job() preserves keep_media from source."""
    source = SourceSpec(
        kind="url",
        value="https://example.com/video",
        keep_media=True,
        url_media_kind="video",
        auto_bind_media=True,
    )
    settings = QueueItemSettings(output_dir=Path("outputs"))
    item = QueueItem(
        item_id=generate_queue_item_id(source),
        source=source,
        settings=settings,
    )

    # Convert to job
    job = item.to_job()

    # Verify that the source in the job has keep_media=True
    assert len(job.sources) == 1
    job_source = job.sources[0]
    assert job_source.keep_media is True
    assert job_source.url_media_kind == "video"
    assert job_source.auto_bind_media is True

