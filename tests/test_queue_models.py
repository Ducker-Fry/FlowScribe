"""Tests for flowscribe.queue.models."""

from pathlib import Path

from flowscribe.app.models import SourceSpec
from flowscribe.queue.models import (
    BatchOutputStrategy,
    QueueItem,
    QueueItemSettings,
    generate_queue_item_id,
    _source_stem,
)


def test_generate_queue_item_id_deterministic():
    source = SourceSpec(kind="url", value="https://example.com/video.mp4")
    id1 = generate_queue_item_id(source)
    id2 = generate_queue_item_id(source)
    assert id1 == id2
    assert len(id1) == 12


def test_generate_queue_item_id_different_sources():
    s1 = SourceSpec(kind="url", value="https://example.com/a.mp4")
    s2 = SourceSpec(kind="url", value="https://example.com/b.mp4")
    assert generate_queue_item_id(s1) != generate_queue_item_id(s2)


def test_queue_item_display_label_url():
    source = SourceSpec(kind="url", value="https://example.com/video.mp4")
    item = QueueItem(
        item_id="abc123",
        source=source,
        settings=QueueItemSettings(),
    )
    assert item.display_label == "https://example.com/video.mp4"


def test_queue_item_display_label_local():
    source = SourceSpec(kind="local", value=r"C:\media\test.wav")
    item = QueueItem(
        item_id="abc123",
        source=source,
        settings=QueueItemSettings(),
    )
    assert item.display_label == "test.wav"


def test_queue_item_can_retry_when_failed():
    source = SourceSpec(kind="url", value="https://example.com/a.mp4")
    item = QueueItem(
        item_id="abc123",
        source=source,
        settings=QueueItemSettings(),
        status="failed",
        attempt_count=1,
        max_retries=2,
    )
    assert item.can_retry is True


def test_queue_item_cannot_retry_when_exhausted():
    source = SourceSpec(kind="url", value="https://example.com/a.mp4")
    item = QueueItem(
        item_id="abc123",
        source=source,
        settings=QueueItemSettings(),
        status="failed",
        attempt_count=3,
        max_retries=2,
    )
    assert item.can_retry is False


def test_queue_item_cannot_retry_when_completed():
    source = SourceSpec(kind="url", value="https://example.com/a.mp4")
    item = QueueItem(
        item_id="abc123",
        source=source,
        settings=QueueItemSettings(),
        status="completed",
        attempt_count=1,
        max_retries=2,
    )
    assert item.can_retry is False


def test_to_job_unified_strategy():
    source = SourceSpec(kind="url", value="https://example.com/video.mp4")
    settings = QueueItemSettings(output_dir=Path("out"), model_name="medium")
    strategy = BatchOutputStrategy(mode="unified", base_dir=Path("batch_out"))
    item = QueueItem(
        item_id="abc123",
        source=source,
        settings=settings,
        output_strategy=strategy,
    )
    job = item.to_job()
    assert job.output_dir == Path("batch_out")
    assert job.model_name == "medium"
    assert job.sources == (source,)


def test_to_job_per_source_strategy():
    source = SourceSpec(kind="url", value="https://example.com/my-video.mp4")
    strategy = BatchOutputStrategy(mode="per_source", base_dir=Path("batch_out"))
    item = QueueItem(
        item_id="abc123",
        source=source,
        settings=QueueItemSettings(),
        output_strategy=strategy,
    )
    job = item.to_job()
    assert job.output_dir == Path("batch_out/my-video")


def test_to_job_template_strategy():
    source = SourceSpec(kind="local", value=r"C:\media\lecture.wav")
    strategy = BatchOutputStrategy(
        mode="template", base_dir=Path("out"), name_template="transcript_{source_stem}"
    )
    item = QueueItem(
        item_id="abc123",
        source=source,
        settings=QueueItemSettings(),
        output_strategy=strategy,
    )
    job = item.to_job()
    assert job.output_name_base == "transcript_lecture"


def test_source_stem_url():
    assert _source_stem(SourceSpec(kind="url", value="https://example.com/path/video.mp4")) == "video"


def test_source_stem_url_no_path():
    assert _source_stem(SourceSpec(kind="url", value="https://example.com/")) == "download"


def test_source_stem_local():
    assert _source_stem(SourceSpec(kind="local", value=r"C:\media\test.wav")) == "test"
