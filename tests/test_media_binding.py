"""Tests for media binding functionality."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from flowscribe.app.models import SourceSpec, DownloadOptions


class TestMediaBindingInJSON:
    """Test media binding information in JSON transcripts."""

    def test_json_with_media_binding(self, tmp_path):
        """Test that JSON includes media_binding field."""
        from flowscribe.output.json_writer import JsonTranscriptWriter
        from flowscribe.core.models import Transcript, MediaItem, TranscriptSegment

        # Create a simple transcript
        media_item = MediaItem(path=tmp_path / "audio.m4a")
        transcript = Transcript(
            source=media_item,
            segments=(
                TranscriptSegment(text="Hello world", start_seconds=0.0, end_seconds=1.0),
            ),
        )

        # Write with media binding
        media_path = tmp_path / "video.mp4"
        writer = JsonTranscriptWriter(media_path=media_path, media_kind="video")
        output_path = writer.write(transcript, tmp_path)

        # Read and verify
        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert "media_binding" in data
        assert data["media_binding"]["path"] == str(media_path)
        assert data["media_binding"]["kind"] == "video"

    def test_json_without_media_binding(self, tmp_path):
        """Test that JSON without media binding works normally."""
        from flowscribe.output.json_writer import JsonTranscriptWriter
        from flowscribe.core.models import Transcript, MediaItem, TranscriptSegment

        # Create a simple transcript
        media_item = MediaItem(path=tmp_path / "audio.m4a")
        transcript = Transcript(
            source=media_item,
            segments=(
                TranscriptSegment(text="Hello world", start_seconds=0.0, end_seconds=1.0),
            ),
        )

        # Write without media binding
        writer = JsonTranscriptWriter()
        output_path = writer.write(transcript, tmp_path)

        # Read and verify
        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert "media_binding" not in data


class TestResolveTranscriptMediaPath:
    """Test resolving media path from transcript."""

    def test_resolve_from_media_binding(self, tmp_path):
        """Test resolving media path from media_binding field."""
        from flowscribe.gui.transcript_viewer import resolve_transcript_media_path, TranscriptView

        # Create a JSON file with media_binding
        media_file = tmp_path / "video.mp4"
        media_file.touch()

        json_file = tmp_path / "transcript.json"
        data = {
            "source": "audio.m4a",
            "media_binding": {
                "path": str(media_file),
                "kind": "video",
            },
        }
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(data, f)

        # Create view
        view = TranscriptView(path=json_file, source="audio.m4a")

        # Resolve should return media_binding path
        resolved = resolve_transcript_media_path(view)
        assert resolved == media_file

    def test_resolve_fallback_to_source(self, tmp_path):
        """Test fallback to source field when media_binding not present."""
        from flowscribe.gui.transcript_viewer import resolve_transcript_media_path, TranscriptView

        # Create a source file
        source_file = tmp_path / "audio.m4a"
        source_file.touch()

        json_file = tmp_path / "transcript.json"
        data = {"source": str(source_file)}
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(data, f)

        # Create view
        view = TranscriptView(path=json_file, source=str(source_file))

        # Resolve should return source path
        resolved = resolve_transcript_media_path(view)
        assert resolved == source_file
