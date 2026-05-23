"""Tests for transcription cancellation functionality."""

from pathlib import Path
from unittest.mock import Mock

import pytest

from flowscribe.app.models import ProgressEvent, SourceSpec, TranscriptionJob
from flowscribe.app.service import TranscriptionService
from flowscribe.core.errors import CancellationError
from flowscribe.core.models import PreparedAudio, Transcript, TranscriptSegment


@pytest.fixture
def mock_audio():
    """Create a mock PreparedAudio object."""
    return PreparedAudio(
        path=Path("/tmp/test.wav"),
        source=Path("/tmp/test.mp3"),
        sample_rate=16000,
    )


@pytest.fixture
def mock_transcript():
    """Create a mock Transcript object."""
    return Transcript(
        source=Path("/tmp/test.mp3"),
        segments=(
            TranscriptSegment(
                start_seconds=0.0,
                end_seconds=5.0,
                text="Test segment",
            ),
        ),
    )


def test_service_cancellation_before_transcription(tmp_path):
    """Test that cancellation is detected before transcription starts."""
    # Create a test file
    test_file = tmp_path / "test.mp3"
    test_file.write_bytes(b"fake audio")

    job = TranscriptionJob(
        sources=(SourceSpec(kind="local", value=str(test_file)),),
        output_dir=tmp_path / "output",
        work_dir=tmp_path / "work",
        output_formats=("json",),
    )

    def should_cancel():
        return True

    service = TranscriptionService()
    result = service.run(job, should_cancel=should_cancel)

    assert result.canceled is True
    assert len(result.outputs) == 0


def test_service_cancellation_during_progress(tmp_path):
    """Test that cancellation is detected during progress emission."""
    # Create a test file
    test_file = tmp_path / "test.mp3"
    test_file.write_bytes(b"fake audio")

    job = TranscriptionJob(
        sources=(SourceSpec(kind="local", value=str(test_file)),),
        output_dir=tmp_path / "output",
        work_dir=tmp_path / "work",
        output_formats=("json",),
    )

    cancel_after_first_progress = False

    def should_cancel():
        return cancel_after_first_progress

    def progress_callback(event: ProgressEvent):
        nonlocal cancel_after_first_progress
        if event.stage == "discover":
            cancel_after_first_progress = True

    service = TranscriptionService()
    result = service.run(job, progress=progress_callback, should_cancel=should_cancel)

    assert result.canceled is True


def test_transcriber_cancellation_during_segment_iteration(mock_audio, mock_transcript):
    """Test that transcriber checks cancellation during segment iteration."""
    from flowscribe.transcription.local_whisper import LocalWhisperTranscriber

    transcriber = LocalWhisperTranscriber(model_name="tiny")

    # Mock the model and segments
    mock_model = Mock()
    mock_segment = Mock()
    mock_segment.text = "Test segment"
    mock_segment.start = 0.0
    mock_segment.end = 5.0
    mock_segment.words = []

    # Create a generator that yields multiple segments
    def segment_generator():
        for _ in range(10):
            yield mock_segment

    mock_info = Mock()
    mock_info.language = "en"
    mock_model.transcribe.return_value = (segment_generator(), mock_info)

    transcriber._model = mock_model

    # Cancel after processing 3 segments
    segment_count = 0

    def should_cancel():
        nonlocal segment_count
        segment_count += 1
        return segment_count > 3

    with pytest.raises(CancellationError, match="Transcription canceled"):
        transcriber.transcribe(mock_audio, should_cancel=should_cancel)

    # Verify that we stopped early (not all 10 segments processed)
    assert segment_count <= 5


def test_progressive_executor_cancellation_between_chunks(mock_audio):
    """Test that progressive executor checks cancellation between chunks."""
    from flowscribe.core.progressive.executor import ProgressiveTranscriptionExecutor
    from flowscribe.core.models import TranscriptionChunk, TranscriptionChunkPlan, MediaDurationInfo

    mock_transcriber = Mock()
    mock_transcriber.transcribe_clip.return_value = Transcript(
        source=mock_audio.source,
        segments=(
            TranscriptSegment(
                start_seconds=0.0,
                end_seconds=5.0,
                text="Test",
            ),
        ),
    )

    executor = ProgressiveTranscriptionExecutor(transcriber=mock_transcriber)

    chunk_plan = TranscriptionChunkPlan(
        duration_info=MediaDurationInfo(
            source=mock_audio.source,
            prepared_audio_path=mock_audio.path,
            sample_rate=mock_audio.sample_rate,
            duration_seconds=60.0,
        ),
        chunks=(
            TranscriptionChunk(index=1, start_seconds=0.0, end_seconds=30.0),
            TranscriptionChunk(index=2, start_seconds=27.0, end_seconds=57.0),
            TranscriptionChunk(index=3, start_seconds=54.0, end_seconds=60.0),
        ),
        chunk_duration_seconds=30.0,
        chunk_overlap_seconds=3.0,
    )

    # Cancel after first chunk
    chunk_count = 0

    def should_cancel():
        nonlocal chunk_count
        chunk_count += 1
        return chunk_count > 1

    with pytest.raises(CancellationError, match="Progressive transcription canceled"):
        executor.execute(
            mock_audio,
            chunk_plan,
            max_workers=1,
            should_cancel=should_cancel,
        )

    # Verify we stopped early
    assert chunk_count <= 3
    assert mock_transcriber.transcribe_clip.call_count <= 2


def test_pipeline_passes_cancellation_to_transcriber(mock_audio, tmp_path):
    """Test that pipeline passes should_cancel callback to transcriber."""
    from flowscribe.core.pipeline import LocalTranscriptionPipeline
    from flowscribe.core.models import MediaItem

    mock_transcriber = Mock()
    mock_transcriber.transcribe.side_effect = CancellationError("Canceled")

    mock_preparer = Mock()
    mock_preparer.prepare.return_value = mock_audio

    mock_writer = Mock()

    pipeline = LocalTranscriptionPipeline(
        media_preparer=mock_preparer,
        transcriber=mock_transcriber,
        artifact_writer=mock_writer,
        work_dir=tmp_path / "work",
        output_dir=tmp_path / "output",
    )

    item = MediaItem(path=Path("/tmp/test.mp3"))

    def should_cancel():
        return True

    with pytest.raises(CancellationError):
        pipeline.process(item, should_cancel=should_cancel)

    # Verify should_cancel was passed to transcriber
    mock_transcriber.transcribe.assert_called_once()
    call_kwargs = mock_transcriber.transcribe.call_args[1]
    assert "should_cancel" in call_kwargs
    assert call_kwargs["should_cancel"] is should_cancel
