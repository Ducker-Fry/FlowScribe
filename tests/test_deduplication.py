"""Tests for transcript deduplication."""

from datetime import datetime
from pathlib import Path

import pytest

from flowscribe.core.deduplication import TranscriptDeduplicator
from flowscribe.core.models import MediaItem, Transcript, TranscriptSegment, TranscriptWord


@pytest.fixture
def sample_media_item():
    return MediaItem(path=Path("test.mp3"))


def test_deduplicate_empty_transcript(sample_media_item):
    deduplicator = TranscriptDeduplicator()
    transcript = Transcript(source=sample_media_item, segments=())
    result = deduplicator.deduplicate(transcript)
    assert len(result.segments) == 0


def test_deduplicate_no_duplicates(sample_media_item):
    deduplicator = TranscriptDeduplicator()
    segments = (
        TranscriptSegment(text="Hello world", start_seconds=0.0, end_seconds=2.0),
        TranscriptSegment(text="How are you", start_seconds=2.5, end_seconds=4.5),
        TranscriptSegment(text="I am fine", start_seconds=5.0, end_seconds=7.0),
    )
    transcript = Transcript(source=sample_media_item, segments=segments)
    result = deduplicator.deduplicate(transcript)
    assert len(result.segments) == 3
    assert result.segments == segments


def test_deduplicate_exact_duplicates(sample_media_item):
    deduplicator = TranscriptDeduplicator()
    segments = (
        TranscriptSegment(text="Hello world", start_seconds=0.0, end_seconds=2.0),
        TranscriptSegment(text="Hello world", start_seconds=0.5, end_seconds=2.5),
        TranscriptSegment(text="How are you", start_seconds=3.0, end_seconds=5.0),
    )
    transcript = Transcript(source=sample_media_item, segments=segments)
    result = deduplicator.deduplicate(transcript)
    assert len(result.segments) == 2
    assert result.segments[0].text == "Hello world"
    assert result.segments[1].text == "How are you"


def test_deduplicate_substring_overlap(sample_media_item):
    deduplicator = TranscriptDeduplicator()
    segments = (
        TranscriptSegment(text="Hello world", start_seconds=0.0, end_seconds=2.0),
        TranscriptSegment(text="world", start_seconds=1.5, end_seconds=2.5),
        TranscriptSegment(text="How are you", start_seconds=3.0, end_seconds=5.0),
    )
    transcript = Transcript(source=sample_media_item, segments=segments)
    result = deduplicator.deduplicate(transcript)
    assert len(result.segments) == 2
    assert result.segments[0].text == "Hello world"
    assert result.segments[1].text == "How are you"


def test_deduplicate_keeps_better_timing(sample_media_item):
    deduplicator = TranscriptDeduplicator()
    word1 = TranscriptWord(text="Hello", start_seconds=0.0, end_seconds=0.5)
    word2 = TranscriptWord(text="world", start_seconds=0.5, end_seconds=1.0)
    segments = (
        TranscriptSegment(text="Hello world", start_seconds=0.0, end_seconds=2.0),
        TranscriptSegment(
            text="Hello world",
            start_seconds=0.5,
            end_seconds=2.5,
            words=(word1, word2),
        ),
        TranscriptSegment(text="How are you", start_seconds=3.0, end_seconds=5.0),
    )
    transcript = Transcript(source=sample_media_item, segments=segments)
    result = deduplicator.deduplicate(transcript)
    assert len(result.segments) == 2
    assert result.segments[0].text == "Hello world"
    assert len(result.segments[0].words) == 2


def test_deduplicate_no_timing_info(sample_media_item):
    deduplicator = TranscriptDeduplicator()
    segments = (
        TranscriptSegment(text="Hello world"),
        TranscriptSegment(text="Hello world"),
        TranscriptSegment(text="How are you"),
    )
    transcript = Transcript(source=sample_media_item, segments=segments)
    result = deduplicator.deduplicate(transcript)
    assert len(result.segments) == 2
    assert result.segments[0].text == "Hello world"
    assert result.segments[1].text == "How are you"


def test_deduplicate_far_apart_same_text(sample_media_item):
    deduplicator = TranscriptDeduplicator(time_overlap_threshold_seconds=2.0)
    segments = (
        TranscriptSegment(text="Hello world", start_seconds=0.0, end_seconds=2.0),
        TranscriptSegment(text="Hello world", start_seconds=10.0, end_seconds=12.0),
    )
    transcript = Transcript(source=sample_media_item, segments=segments)
    result = deduplicator.deduplicate(transcript)
    # Should keep both because they're far apart in time
    assert len(result.segments) == 2


def test_deduplicate_whitespace_normalization(sample_media_item):
    deduplicator = TranscriptDeduplicator()
    segments = (
        TranscriptSegment(text="Hello   world", start_seconds=0.0, end_seconds=2.0),
        TranscriptSegment(text="Hello world", start_seconds=0.5, end_seconds=2.5),
        TranscriptSegment(text="How are you", start_seconds=3.0, end_seconds=5.0),
    )
    transcript = Transcript(source=sample_media_item, segments=segments)
    result = deduplicator.deduplicate(transcript)
    assert len(result.segments) == 2


def test_deduplicate_chinese_text(sample_media_item):
    deduplicator = TranscriptDeduplicator()
    segments = (
        TranscriptSegment(text="你好世界", start_seconds=0.0, end_seconds=2.0),
        TranscriptSegment(text="你好世界", start_seconds=0.5, end_seconds=2.5),
        TranscriptSegment(text="你好吗", start_seconds=3.0, end_seconds=5.0),
    )
    transcript = Transcript(source=sample_media_item, segments=segments)
    result = deduplicator.deduplicate(transcript)
    assert len(result.segments) == 2
    assert result.segments[0].text == "你好世界"
    assert result.segments[1].text == "你好吗"


def test_deduplicate_preserves_metadata(sample_media_item):
    deduplicator = TranscriptDeduplicator()
    segments = (
        TranscriptSegment(text="Hello world", start_seconds=0.0, end_seconds=2.0),
        TranscriptSegment(text="Hello world", start_seconds=0.5, end_seconds=2.5),
    )
    created_at = datetime(2024, 1, 1, 12, 0, 0)
    transcript = Transcript(
        source=sample_media_item,
        segments=segments,
        language="en",
        model_name="small",
        created_at=created_at,
    )
    result = deduplicator.deduplicate(transcript)
    assert result.language == "en"
    assert result.model_name == "small"
    assert result.created_at == created_at


def test_deduplicate_keeps_repeated_words_in_content(sample_media_item):
    """Test that repeated words in original content are preserved."""
    deduplicator = TranscriptDeduplicator()
    segments = (
        TranscriptSegment(text="爸爸妈妈", start_seconds=0.0, end_seconds=2.0),
        TranscriptSegment(text="爸爸说", start_seconds=3.0, end_seconds=5.0),
        TranscriptSegment(text="妈妈说", start_seconds=6.0, end_seconds=8.0),
        TranscriptSegment(text="爸爸妈妈都很好", start_seconds=20.0, end_seconds=22.0),
    )
    transcript = Transcript(source=sample_media_item, segments=segments)
    result = deduplicator.deduplicate(transcript)
    # All segments should be kept because they have different text or are far apart in time
    assert len(result.segments) == 4
    assert result.segments[0].text == "爸爸妈妈"
    assert result.segments[1].text == "爸爸说"
    assert result.segments[2].text == "妈妈说"
    assert result.segments[3].text == "爸爸妈妈都很好"


def test_deduplicate_keeps_same_text_far_apart(sample_media_item):
    """Test that same text appearing far apart in time is preserved."""
    deduplicator = TranscriptDeduplicator(time_overlap_threshold_seconds=2.0)
    segments = (
        TranscriptSegment(text="你好", start_seconds=0.0, end_seconds=1.0),
        TranscriptSegment(text="我很好", start_seconds=2.0, end_seconds=4.0),
        TranscriptSegment(text="你好", start_seconds=50.0, end_seconds=51.0),  # Same text, far away
    )
    transcript = Transcript(source=sample_media_item, segments=segments)
    result = deduplicator.deduplicate(transcript)
    # All 3 segments should be kept because the two "你好" are 50 seconds apart
    assert len(result.segments) == 3
    assert result.segments[0].text == "你好"
    assert result.segments[1].text == "我很好"
    assert result.segments[2].text == "你好"
