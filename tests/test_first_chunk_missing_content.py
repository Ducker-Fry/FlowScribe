"""Test for bug: first 30 seconds missing from transcription."""

import warnings
from pathlib import Path
from unittest.mock import Mock


from flowscribe.core.models import (
    MediaItem,
    PreparedAudio,
    Transcript,
    TranscriptSegment,
    TranscriptionChunk,
)
from flowscribe.core.progressive.executor import ProgressiveTranscriptionExecutor
from flowscribe.core.progressive.merger import ConservativeChunkMergePolicy


def test_first_chunk_segments_not_dropped():
    """
    Bug: First chunk segments starting from 0s should not be dropped.

    Scenario:
    - First chunk (index=1) transcribes [0s - 30s]
    - Whisper returns segments starting from 0s
    - These segments should appear in final transcript
    """
    # Mock transcriber that returns segments starting from 0s
    mock_transcriber = Mock()

    # First chunk: [0s - 30s] with segments starting from 0s
    first_chunk_transcript = Transcript(
        source=MediaItem(path=Path("test.mp3")),
        segments=(
            TranscriptSegment(text="Hello", start_seconds=0.0, end_seconds=1.5),
            TranscriptSegment(text="World", start_seconds=1.5, end_seconds=3.0),
            TranscriptSegment(text="This is the beginning", start_seconds=3.0, end_seconds=6.0),
        ),
    )

    mock_transcriber.transcribe_clip.return_value = first_chunk_transcript

    # Create executor with merge policy
    merge_policy = ConservativeChunkMergePolicy()
    ProgressiveTranscriptionExecutor(
        transcriber=mock_transcriber,
        merge_policy=merge_policy,
    )

    # Test _prepare_segments for first chunk (index=1)
    first_chunk = TranscriptionChunk(
        index=1,
        start_seconds=0.0,
        end_seconds=30.0,
        overlap_seconds=3.0,
    )

    prepared = merge_policy._prepare_segments(
        first_chunk_transcript.segments,
        chunk=first_chunk,
    )

    # First chunk should keep all segments
    assert len(prepared) == 3
    assert prepared[0].text == "Hello"
    assert prepared[0].start_seconds == 0.0
    assert prepared[1].text == "World"
    assert prepared[2].text == "This is the beginning"


def test_first_chunk_with_late_start_timestamp():
    """
    Bug scenario: First chunk returns segments with late start timestamps.

    This might happen if:
    - VAD filter skips initial silence
    - Whisper model skips initial audio
    - Timestamp normalization issue
    """
    merge_policy = ConservativeChunkMergePolicy()

    # First chunk but segments start at 28.58s (bug scenario from screenshot)
    first_chunk = TranscriptionChunk(
        index=1,
        start_seconds=0.0,
        end_seconds=30.0,
        overlap_seconds=3.0,
    )

    # Segments with late start (missing 0-28s content)
    late_segments = (
        TranscriptSegment(text="I'm a big fan of you.", start_seconds=28.58, end_seconds=29.98),
        TranscriptSegment(text="We got a party", start_seconds=30.0, end_seconds=32.0),
    )

    prepared = merge_policy._prepare_segments(late_segments, chunk=first_chunk)

    # Should keep all segments even if they start late
    # (The bug is NOT in merge policy - it's in transcription or VAD)
    assert len(prepared) == 2
    assert prepared[0].start_seconds == 28.58
    assert prepared[0].text == "I'm a big fan of you."


def test_first_chunk_late_start_warning():
    """
    Test that validation warns when first chunk has late-starting segments.
    """
    # Create transcript with late-starting segments (bug scenario)
    transcript = Transcript(
        source=MediaItem(path=Path("test.mp3")),
        segments=(
            TranscriptSegment(text="I'm a big fan of you.", start_seconds=28.58, end_seconds=29.98),
            TranscriptSegment(text="We got a party", start_seconds=30.0, end_seconds=32.0),
        ),
    )

    chunk = TranscriptionChunk(
        index=1,
        start_seconds=0.0,
        end_seconds=30.0,
        overlap_seconds=3.0,
    )

    audio = PreparedAudio(
        source=MediaItem(path=Path("test.mp3")),
        path=Path("test.wav"),
        sample_rate=16000,
    )

    # Should emit warning about late start
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        result = ProgressiveTranscriptionExecutor._validate_first_chunk_segments(
            transcript, chunk=chunk, audio=audio
        )

        # Check that warning was issued
        assert len(w) == 1
        assert issubclass(w[0].category, UserWarning)
        assert "28.6s" in str(w[0].message) or "28.58" in str(w[0].message) or "28" in str(w[0].message)
        assert "missing content" in str(w[0].message).lower()

    # Transcript should be returned unchanged
    assert result == transcript


def test_first_chunk_normal_start_no_warning():
    """
    Test that validation does NOT warn when first chunk starts normally.
    """
    # Create transcript with normal start (< 5s)
    transcript = Transcript(
        source=MediaItem(path=Path("test.mp3")),
        segments=(
            TranscriptSegment(text="Hello", start_seconds=0.5, end_seconds=1.5),
            TranscriptSegment(text="World", start_seconds=1.5, end_seconds=3.0),
        ),
    )

    chunk = TranscriptionChunk(
        index=1,
        start_seconds=0.0,
        end_seconds=30.0,
        overlap_seconds=3.0,
    )

    audio = PreparedAudio(
        source=MediaItem(path=Path("test.mp3")),
        path=Path("test.wav"),
        sample_rate=16000,
    )

    # Should NOT emit warning
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        result = ProgressiveTranscriptionExecutor._validate_first_chunk_segments(
            transcript, chunk=chunk, audio=audio
        )

        # No warning should be issued
        assert len(w) == 0

    # Transcript should be returned unchanged
    assert result == transcript


def test_deduplication_should_not_drop_first_segments():
    """
    Verify that deduplication doesn't incorrectly drop first segments.
    """
    from flowscribe.core.deduplication import TranscriptDeduplicator

    deduplicator = TranscriptDeduplicator()

    # Transcript with segments starting from 0s
    transcript = Transcript(
        source=MediaItem(path=Path("test.mp3")),
        segments=(
            TranscriptSegment(text="Hello", start_seconds=0.0, end_seconds=1.5),
            TranscriptSegment(text="World", start_seconds=1.5, end_seconds=3.0),
            TranscriptSegment(text="Hello", start_seconds=30.0, end_seconds=31.5),  # Duplicate text but different time
        ),
    )

    result = deduplicator.deduplicate(transcript)

    # First segment should never be dropped
    assert len(result.segments) >= 1
    assert result.segments[0].text == "Hello"
    assert result.segments[0].start_seconds == 0.0

    # All three segments should be kept (different timestamps)
    assert len(result.segments) == 3
