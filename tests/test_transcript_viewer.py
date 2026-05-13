from pathlib import Path

import pytest

from flowscribe.gui.transcript_viewer import (
    load_transcript_view,
    render_transcript_view,
    search_transcript_view,
)


def test_load_transcript_view_reads_segments_and_timestamps(tmp_path: Path) -> None:
    path = tmp_path / "lesson.json"
    path.write_text(
        """
{
  "source": "lesson.mp4",
  "language": "zh",
  "model": "small",
  "segments": [
    {
      "index": 1,
      "text": "Hello world.",
      "start_seconds": 0.0,
      "end_seconds": 1.5
    },
    {
      "index": 2,
      "text": "Second segment.",
      "start": 2.0,
      "end": 4.25
    }
  ]
}
""".strip(),
        encoding="utf-8",
    )

    view = load_transcript_view(path)

    assert view.source == "lesson.mp4"
    assert view.language == "zh"
    assert view.model == "small"
    assert len(view.segments) == 2
    assert view.segments[0].text == "Hello world."
    assert view.segments[1].start_seconds == 2.0
    assert view.segments[1].end_seconds == 4.25


def test_render_transcript_view_formats_readable_lines(tmp_path: Path) -> None:
    path = tmp_path / "lesson.json"
    path.write_text(
        """
{
  "source": "lesson.mp4",
  "segments": [
    {
      "text": "Hello world.",
      "start_seconds": 0.0,
      "end_seconds": 1.5
    }
  ]
}
""".strip(),
        encoding="utf-8",
    )

    rendered = render_transcript_view(load_transcript_view(path))

    assert "Transcript: lesson.json" in rendered
    assert "Source: lesson.mp4" in rendered
    assert "Segments: 1" in rendered
    assert "[00:00:00.000 - 00:00:01.500] Hello world." in rendered


def test_load_transcript_view_rejects_invalid_segments(tmp_path: Path) -> None:
    path = tmp_path / "broken.json"
    path.write_text('{"segments": "nope"}', encoding="utf-8")

    with pytest.raises(ValueError, match="segments list"):
        load_transcript_view(path)


def test_search_transcript_view_maps_hits_to_segments(tmp_path: Path) -> None:
    path = tmp_path / "lesson.json"
    path.write_text(
        """
{
  "source": "lesson.mp4",
  "segments": [
    {
      "index": 1,
      "text": "First keyword.",
      "start_seconds": 0.0,
      "end_seconds": 1.0,
      "words": [
        {"text": "First", "start_seconds": 0.0, "end_seconds": 0.4},
        {"text": "keyword", "start_seconds": 0.4, "end_seconds": 1.0}
      ]
    },
    {
      "index": 2,
      "text": "Second keyword.",
      "start_seconds": 1.1,
      "end_seconds": 2.0,
      "words": [
        {"text": "Second", "start_seconds": 1.1, "end_seconds": 1.5},
        {"text": "keyword", "start_seconds": 1.5, "end_seconds": 2.0}
      ]
    }
  ]
}
""".strip(),
        encoding="utf-8",
    )

    hits = search_transcript_view(path, load_transcript_view(path), "keyword")

    assert len(hits) == 2
    assert hits[0].segment_index == 0
    assert hits[1].segment_index == 1
    assert "keyword" in hits[0].context
