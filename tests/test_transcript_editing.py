from datetime import datetime
from pathlib import Path

import pytest

from flowscribe.transcript.editing import (
    load_editable_transcript,
    render_editable_segment_line,
    save_editable_transcript,
    suggested_corrected_transcript_path,
    update_editable_transcript_segment,
)


def test_load_editable_transcript_reads_segments_and_metadata(tmp_path: Path) -> None:
    transcript = tmp_path / "lesson.json"
    transcript.write_text(
        """
{
  "source": "lesson.mp4",
  "language": "zh",
  "model": "small",
  "segments": [
    {
      "id": "seg-0001",
      "index": 1,
      "text": "Hello world.",
      "start_seconds": 0.0,
      "end_seconds": 1.5
    }
  ]
}
""".strip(),
        encoding="utf-8",
    )

    document = load_editable_transcript(transcript)

    assert document.path == transcript.resolve()
    assert document.source == "lesson.mp4"
    assert document.language == "zh"
    assert document.model == "small"
    assert len(document.segments) == 1
    assert document.segments[0].original_text == "Hello world."
    assert document.dirty is False


def test_update_editable_transcript_segment_marks_dirty_and_preserves_timestamps(
    tmp_path: Path,
) -> None:
    transcript = tmp_path / "lesson.json"
    transcript.write_text(
        """
{
  "segments": [
    {
      "index": 1,
      "text": "Original line.",
      "start_seconds": 2.0,
      "end_seconds": 4.5
    }
  ]
}
""".strip(),
        encoding="utf-8",
    )

    updated = update_editable_transcript_segment(
        load_editable_transcript(transcript),
        0,
        "Corrected line.",
    )

    assert updated.dirty is True
    assert updated.segments[0].text == "Corrected line."
    assert updated.segments[0].start_seconds == 2.0
    assert updated.segments[0].end_seconds == 4.5


def test_save_editable_transcript_writes_correction_metadata_and_preserves_order(
    tmp_path: Path,
) -> None:
    transcript = tmp_path / "lesson.json"
    transcript.write_text(
        """
{
  "source": "lesson.mp4",
  "text": "First\\nSecond",
  "segments": [
    {
      "index": 1,
      "text": "First",
      "start_seconds": 0.0,
      "end_seconds": 1.0
    },
    {
      "index": 2,
      "text": "Second",
      "start_seconds": 1.2,
      "end_seconds": 2.0
    }
  ]
}
""".strip(),
        encoding="utf-8",
    )

    document = update_editable_transcript_segment(
        load_editable_transcript(transcript),
        1,
        "Second corrected",
    )
    saved_path = save_editable_transcript(
        document,
        corrected_at=datetime(2026, 5, 15, 12, 30, 0),
    )
    reloaded = load_editable_transcript(saved_path)

    assert saved_path == transcript.resolve()
    assert reloaded.segments[0].text == "First"
    assert reloaded.segments[1].text == "Second corrected"
    assert reloaded.segments[0].start_seconds == 0.0
    assert reloaded.segments[1].start_seconds == 1.2

    payload = transcript.read_text(encoding="utf-8")
    assert '"edited_segment_count": 1' in payload
    assert '"original_text": "Second"' in payload
    assert '"corrected_text": "Second corrected"' in payload


def test_save_editable_transcript_can_write_copy_without_overwriting_original(
    tmp_path: Path,
) -> None:
    transcript = tmp_path / "lesson.json"
    transcript.write_text(
        """
{
  "text": "Original",
  "segments": [
    {
      "index": 1,
      "text": "Original"
    }
  ]
}
""".strip(),
        encoding="utf-8",
    )

    document = update_editable_transcript_segment(
        load_editable_transcript(transcript),
        0,
        "Copy text",
    )
    copy_path = suggested_corrected_transcript_path(transcript)
    saved_path = save_editable_transcript(document, destination=copy_path)

    assert saved_path == copy_path.resolve()
    assert '"text": "Original"' in transcript.read_text(encoding="utf-8")
    assert '"text": "Copy text"' in saved_path.read_text(encoding="utf-8")


def test_load_editable_transcript_rejects_invalid_json_or_timestamps(tmp_path: Path) -> None:
    invalid = tmp_path / "invalid.json"
    invalid.write_text("{not json", encoding="utf-8")

    with pytest.raises(ValueError, match="not valid JSON"):
        load_editable_transcript(invalid)

    broken = tmp_path / "broken.json"
    broken.write_text(
        """
{
  "segments": [
    {
      "text": "Broken",
      "start_seconds": "bad"
    }
  ]
}
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="non-numeric"):
        load_editable_transcript(broken)


def test_render_editable_segment_line_marks_edited_segments(tmp_path: Path) -> None:
    transcript = tmp_path / "lesson.json"
    transcript.write_text(
        """
{
  "segments": [
    {
      "index": 1,
      "text": "Original",
      "start_seconds": 0.0,
      "end_seconds": 1.0
    }
  ]
}
""".strip(),
        encoding="utf-8",
    )

    document = update_editable_transcript_segment(
        load_editable_transcript(transcript),
        0,
        "Edited",
    )

    rendered = render_editable_segment_line(document.segments[0])
    assert "[00:00:00.000 - 00:00:01.000] Edited [edited]" == rendered
