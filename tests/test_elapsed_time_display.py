"""Test elapsed time display formatting."""

from datetime import datetime


def format_elapsed_time(elapsed_seconds: float | None) -> str:
    """Format elapsed time for display."""
    if elapsed_seconds is None:
        return ""

    elapsed = elapsed_seconds
    if elapsed < 60:
        return f" (Time: {elapsed:.1f}s)"
    else:
        minutes = int(elapsed // 60)
        seconds = int(elapsed % 60)
        return f" (Time: {minutes}m {seconds}s)"


def test_format_elapsed_time_none():
    """Test formatting None elapsed time."""
    assert format_elapsed_time(None) == ""


def test_format_elapsed_time_seconds():
    """Test formatting elapsed time in seconds."""
    assert format_elapsed_time(5.5) == " (Time: 5.5s)"
    assert format_elapsed_time(30.0) == " (Time: 30.0s)"
    assert format_elapsed_time(59.9) == " (Time: 59.9s)"


def test_format_elapsed_time_minutes():
    """Test formatting elapsed time in minutes."""
    assert format_elapsed_time(60.0) == " (Time: 1m 0s)"
    assert format_elapsed_time(90.0) == " (Time: 1m 30s)"
    assert format_elapsed_time(125.5) == " (Time: 2m 5s)"
    assert format_elapsed_time(3661.0) == " (Time: 61m 1s)"


def test_elapsed_seconds_property():
    """Test TranscriptionResult.elapsed_seconds property."""
    from flowscribe.tasks.models import TranscriptionResult, TranscriptionJob
    from pathlib import Path

    # Create a job
    job = TranscriptionJob(
        sources=(),
        output_dir=Path("outputs"),
    )

    # Test with finished_at set
    started = datetime(2024, 1, 1, 10, 0, 0)
    finished = datetime(2024, 1, 1, 10, 2, 30)  # 2 minutes 30 seconds later

    result = TranscriptionResult(
        job=job,
        started_at=started,
        finished_at=finished,
    )

    assert result.elapsed_seconds == 150.0

    # Test with finished_at None
    result_unfinished = TranscriptionResult(
        job=job,
        started_at=started,
        finished_at=None,
    )

    assert result_unfinished.elapsed_seconds is None
