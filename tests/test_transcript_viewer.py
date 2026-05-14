from pathlib import Path

import pytest

from flowscribe.gui.transcript_viewer import (
    load_transcript_view,
    resolve_transcript_media_path,
    render_transcript_view,
    render_transcript_summary,
    search_transcript_view,
    transcript_media_binding_warning,
    transcript_segment_index_for_seconds,
    transcript_search_hit_seek_seconds,
    transcript_segment_seek_seconds,
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


def test_render_transcript_summary_formats_metadata(tmp_path: Path) -> None:
    path = tmp_path / "lesson.json"
    path.write_text('{"source": "lesson.mp4", "segments": []}', encoding="utf-8")

    summary = render_transcript_summary(load_transcript_view(path))

    assert "Transcript: lesson.json" in summary
    assert "Source: lesson.mp4" in summary
    assert "Segments: 0" in summary


def test_resolve_transcript_media_path_handles_relative_source(tmp_path: Path) -> None:
    media = tmp_path / "lesson.mp4"
    media.write_bytes(b"media")
    transcript = tmp_path / "lesson.json"
    transcript.write_text('{"source": "lesson.mp4", "segments": []}', encoding="utf-8")

    resolved = resolve_transcript_media_path(load_transcript_view(transcript))

    assert resolved == media.resolve()


def test_transcript_seek_helpers_prefer_start_time(tmp_path: Path) -> None:
    transcript = tmp_path / "lesson.json"
    transcript.write_text(
        """
{
  "source": "lesson.mp4",
  "segments": [
    {
      "text": "Hello world.",
      "start_seconds": 1.25,
      "end_seconds": 2.5,
      "words": [
        {"text": "Hello", "start_seconds": 1.25, "end_seconds": 1.6},
        {"text": "world", "start_seconds": 1.6, "end_seconds": 2.5}
      ]
    }
  ]
}
""".strip(),
        encoding="utf-8",
    )

    view = load_transcript_view(transcript)
    hits = search_transcript_view(transcript, view, "world")

    assert transcript_segment_seek_seconds(view.segments[0]) == 1.25
    assert transcript_search_hit_seek_seconds(hits[0]) == 1.6


def test_transcript_segment_index_for_seconds_follows_playback_position(tmp_path: Path) -> None:
    transcript = tmp_path / "lesson.json"
    transcript.write_text(
        """
{
  "source": "lesson.mp4",
  "segments": [
    {"text": "Intro", "start_seconds": 0.0, "end_seconds": 1.0},
    {"text": "Middle", "start_seconds": 1.2, "end_seconds": 2.5},
    {"text": "End", "start_seconds": 3.0, "end_seconds": 4.0}
  ]
}
""".strip(),
        encoding="utf-8",
    )

    view = load_transcript_view(transcript)

    assert transcript_segment_index_for_seconds(view, 0.4) == 0
    assert transcript_segment_index_for_seconds(view, 2.0) == 1
    assert transcript_segment_index_for_seconds(view, 2.8) == 1
    assert transcript_segment_index_for_seconds(view, 3.5) == 2


def test_transcript_media_binding_warning_flags_manual_mismatch(tmp_path: Path) -> None:
    expected_media = tmp_path / "lesson.mp4"
    expected_media.write_bytes(b"media")
    other_media = tmp_path / "other.mp4"
    other_media.write_bytes(b"media")
    transcript = tmp_path / "lesson.json"
    transcript.write_text(
        '{"source": "lesson.mp4", "segments": []}',
        encoding="utf-8",
    )

    view = load_transcript_view(transcript)

    assert transcript_media_binding_warning(view, expected_media) is None
    warning = transcript_media_binding_warning(view, other_media)
    assert warning is not None
    assert "lesson.mp4" in warning
    assert "other.mp4" in warning
