"""Tests for flowscribe.tasks.queue_models."""

from pathlib import Path

from flowscribe.tasks.models import SourceSpec
from flowscribe.tasks.queue_models import (
    QueueItem,
    QueueItemSettings,
    generate_queue_item_id,
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


def test_to_job_creates_subdirectory_with_timestamp():
    from datetime import datetime
    source = SourceSpec(kind="url", value="https://example.com/video.mp4")
    settings = QueueItemSettings(
        output_dir=Path("out"),
        provider_name="native-engine",
        model_name="models/ggml-base.en.bin",
        native_threads=8,
    )
    created_at = datetime(2026, 5, 22, 14, 30, 45)
    item = QueueItem(
        item_id="abc123",
        source=source,
        settings=settings,
        created_at=created_at,
    )
    job = item.to_job()
    assert job.output_dir == Path("out/143045-video")
    assert job.provider_name == "native-engine"
    assert job.model_name == "models/ggml-base.en.bin"
    assert job.native_threads == 8
    assert job.sources == (source,)


def test_to_job_creates_subdirectory_for_local():
    from datetime import datetime
    source = SourceSpec(kind="local", value=r"C:\media\lecture.wav")
    settings = QueueItemSettings(output_dir=Path("out"))
    created_at = datetime(2026, 5, 22, 9, 5, 30)
    item = QueueItem(
        item_id="abc123",
        source=source,
        settings=settings,
        created_at=created_at,
    )
    job = item.to_job()
    assert job.output_dir == Path("out/090530-lecture")


def test_to_job_uses_settings_output_name_base():
    source = SourceSpec(kind="local", value=r"C:\media\lecture.wav")
    settings = QueueItemSettings(output_name_base="transcript_lecture")
    item = QueueItem(
        item_id="abc123",
        source=source,
        settings=settings,
    )
    job = item.to_job()
    assert job.output_name_base == "transcript_lecture"


def test_source_stem_url_with_path():
    from flowscribe.tasks.queue_models import _source_stem
    source = SourceSpec(kind="url", value="https://example.com/path/video.mp4")
    assert _source_stem(source) == "video"


def test_source_stem_url_no_path():
    from flowscribe.tasks.queue_models import _source_stem
    source = SourceSpec(kind="url", value="https://example.com/")
    stem = _source_stem(source)
    assert stem.startswith("url-")
    assert len(stem) == 16  # "url-" + 12 char hash


def test_source_stem_local():
    from flowscribe.tasks.queue_models import _source_stem
    source = SourceSpec(kind="local", value=r"C:\media\test.wav")
    assert _source_stem(source) == "test"


def test_sanitize_dirname_removes_forbidden_chars():
    from flowscribe.tasks.queue_models import _sanitize_dirname
    assert _sanitize_dirname("video:name") == "video-name"
    assert _sanitize_dirname("video/name") == "video-name"
    assert _sanitize_dirname("video<>name") == "video--name"


def test_sanitize_dirname_limits_length():
    from flowscribe.tasks.queue_models import _sanitize_dirname
    long_name = "a" * 150
    result = _sanitize_dirname(long_name)
    assert len(result) == 100
