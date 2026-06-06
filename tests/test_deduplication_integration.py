"""Integration test for deduplication in progressive transcription."""

from pathlib import Path
from unittest.mock import Mock

import pytest

from flowscribe.pipeline.deduplication import TranscriptDeduplicator
from flowscribe.core.models import (
    MediaItem,
    PreparedAudio,
    Transcript,
    TranscriptSegment,
)
from flowscribe.pipeline.transcription import LocalTranscriptionPipeline


@pytest.fixture
def mock_media_preparer():
    preparer = Mock()
    preparer.prepare.return_value = PreparedAudio(
        source=MediaItem(path=Path("test.mp3")),
        path=Path("test.wav"),
        sample_rate=16000,
        duration_seconds=10.0,
    )
    return preparer


@pytest.fixture
def mock_transcriber_with_duplicates():
    """Mock transcriber that returns transcript with duplicate segments."""
    transcriber = Mock()
    # Simulate chunk overlap duplicates
    segments = (
        TranscriptSegment(text="Hello world", start_seconds=0.0, end_seconds=2.0),
        TranscriptSegment(text="How are you", start_seconds=2.5, end_seconds=4.5),
        TranscriptSegment(text="How are you", start_seconds=3.0, end_seconds=5.0),  # Duplicate
        TranscriptSegment(text="I am fine", start_seconds=5.5, end_seconds=7.0),
        TranscriptSegment(text="Thank you", start_seconds=7.5, end_seconds=9.0),
        TranscriptSegment(text="Thank you", start_seconds=8.0, end_seconds=9.5),  # Duplicate
    )
    transcriber.transcribe.return_value = Transcript(
        source=MediaItem(path=Path("test.mp3")),
        segments=segments,
    )
    return transcriber


@pytest.fixture
def mock_artifact_writer():
    writer = Mock()
    writer.write_all.return_value = Mock(paths=(Path("output.txt"),))
    return writer


def test_pipeline_deduplicates_transcript_by_default(
    tmp_path,
    mock_media_preparer,
    mock_transcriber_with_duplicates,
    mock_artifact_writer,
):
    """Test that pipeline automatically deduplicates transcript."""
    pipeline = LocalTranscriptionPipeline(
        media_preparer=mock_media_preparer,
        transcriber=mock_transcriber_with_duplicates,
        artifact_writer=mock_artifact_writer,
        work_dir=tmp_path / "work",
        output_dir=tmp_path / "output",
        enable_deduplication=True,
    )

    item = MediaItem(path=Path("test.mp3"))
    pipeline.process(item)

    # Check that artifact writer received deduplicated transcript
    call_args = mock_artifact_writer.write_all.call_args
    transcript = call_args[0][0]

    # Should have 4 unique segments instead of 6
    assert len(transcript.segments) == 4
    assert transcript.segments[0].text == "Hello world"
    assert transcript.segments[1].text == "How are you"
    assert transcript.segments[2].text == "I am fine"
    assert transcript.segments[3].text == "Thank you"


def test_pipeline_can_disable_deduplication(
    tmp_path,
    mock_media_preparer,
    mock_transcriber_with_duplicates,
    mock_artifact_writer,
):
    """Test that deduplication can be disabled."""
    pipeline = LocalTranscriptionPipeline(
        media_preparer=mock_media_preparer,
        transcriber=mock_transcriber_with_duplicates,
        artifact_writer=mock_artifact_writer,
        work_dir=tmp_path / "work",
        output_dir=tmp_path / "output",
        enable_deduplication=False,
    )

    item = MediaItem(path=Path("test.mp3"))
    pipeline.process(item)

    # Check that artifact writer received original transcript with duplicates
    call_args = mock_artifact_writer.write_all.call_args
    transcript = call_args[0][0]

    # Should have all 6 segments including duplicates
    assert len(transcript.segments) == 6


def test_deduplicator_standalone_usage():
    """Test using TranscriptDeduplicator directly."""
    deduplicator = TranscriptDeduplicator()

    segments = (
        TranscriptSegment(text="Hello world", start_seconds=0.0, end_seconds=2.0),
        TranscriptSegment(text="Hello world", start_seconds=0.5, end_seconds=2.5),
        TranscriptSegment(text="How are you", start_seconds=3.0, end_seconds=5.0),
    )
    transcript = Transcript(
        source=MediaItem(path=Path("test.mp3")),
        segments=segments,
    )

    result = deduplicator.deduplicate(transcript)

    assert len(result.segments) == 2
    assert result.segments[0].text == "Hello world"
    assert result.segments[1].text == "How are you"
