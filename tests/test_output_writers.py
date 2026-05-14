import json
from pathlib import Path

from flowscribe.core.models import (
    MediaItem,
    Transcript,
    TranscriptSegment,
    TranscriptWord,
    TranscriptionOptions,
)
from flowscribe.output.artifact_writer import TranscriptArtifactWriter
from flowscribe.output.json_writer import JsonTranscriptWriter
from flowscribe.output.md_writer import MarkdownTranscriptWriter
from flowscribe.output.paths import OutputPathBuilder
from flowscribe.output.srt_writer import SrtTranscriptWriter
from flowscribe.output.txt_writer import TxtTranscriptWriter
from flowscribe.output.vtt_writer import VttTranscriptWriter


def build_transcript(tmp_path: Path) -> Transcript:
    source = MediaItem(path=tmp_path / "lesson.mp4")
    return Transcript(
        source=source,
        segments=(
            TranscriptSegment(
                text="Hello world.",
                start_seconds=0.0,
                end_seconds=1.5,
                words=(
                    TranscriptWord(
                        text="Hello",
                        start_seconds=0.0,
                        end_seconds=0.5,
                        confidence=0.91,
                    ),
                ),
                raw_words=(
                    TranscriptWord(
                        text="Hello",
                        start_seconds=0.0,
                        end_seconds=0.5,
                        confidence=0.91,
                    ),
                ),
            ),
            TranscriptSegment(text="Second segment.", start_seconds=1.5, end_seconds=3.25),
        ),
        language="en",
        model_name="test-model",
        options=TranscriptionOptions(
            model_name="test-model",
            language="en",
            task="transcribe",
            beam_size=5,
            vad_filter=True,
            initial_prompt="preserve source languages",
            preset=None,
            word_timestamps=True,
        ),
    )


def test_transcript_artifact_writer_writes_selected_formats(tmp_path: Path) -> None:
    transcript = build_transcript(tmp_path)
    path_builder = OutputPathBuilder(overwrite=True)
    writer = TranscriptArtifactWriter(
        formats=("txt", "md", "json", "srt", "vtt"),
        txt_writer=TxtTranscriptWriter(path_builder),
        md_writer=MarkdownTranscriptWriter(path_builder, include_timestamps=True),
        json_writer=JsonTranscriptWriter(path_builder),
        srt_writer=SrtTranscriptWriter(path_builder),
        vtt_writer=VttTranscriptWriter(path_builder),
    )

    artifacts = writer.write_all(transcript, tmp_path)

    assert {path.suffix for path in artifacts.paths} == {".txt", ".md", ".json", ".srt", ".vtt"}
    assert artifacts.txt_path is not None
    assert artifacts.md_path is not None
    assert artifacts.txt_path.read_text(encoding="utf-8") == "Hello world.\nSecond segment.\n"

    markdown = artifacts.md_path.read_text(encoding="utf-8")
    assert "# lesson" in markdown
    assert "- Task: `transcribe`" in markdown
    assert "[00:00:00.000 - 00:00:01.500] Hello world." in markdown

    payload = json.loads((tmp_path / "lesson.json").read_text(encoding="utf-8"))
    assert payload["schema_version"] == "1.1"
    assert payload["generator"]["name"] == "FlowScribe"
    assert payload["source"] == str(tmp_path / "lesson.mp4")
    assert payload["source_info"]["name"] == "lesson.mp4"
    assert payload["duration_seconds"] == 3.25
    assert payload["segment_count"] == 2
    assert payload["word_count"] == 1
    assert payload["raw_word_count"] == 1
    assert payload["segments"][0]["id"] == "seg-0001"
    assert payload["segments"][0]["index"] == 1
    assert payload["segments"][0]["start"] == 0.0
    assert payload["segments"][0]["end"] == 1.5
    assert payload["segments"][0]["duration_seconds"] == 1.5
    assert payload["segments"][0]["start_seconds"] == 0.0
    assert payload["options"]["word_timestamps"] is True
    assert payload["segments"][0]["raw_words"] == [
        {
            "index": 1,
            "word": "Hello",
            "text": "Hello",
            "start": 0.0,
            "end": 0.5,
            "start_seconds": 0.0,
            "end_seconds": 0.5,
            "duration_seconds": 0.5,
            "confidence": 0.91,
        }
    ]
    assert payload["segments"][0]["words"] == [
        {
            "index": 1,
            "word": "Hello",
            "text": "Hello",
            "start": 0.0,
            "end": 0.5,
            "start_seconds": 0.0,
            "end_seconds": 0.5,
            "duration_seconds": 0.5,
            "confidence": 0.91,
        }
    ]

    srt = (tmp_path / "lesson.srt").read_text(encoding="utf-8")
    assert "1\n00:00:00,000 --> 00:00:01,500\nHello world." in srt

    vtt = (tmp_path / "lesson.vtt").read_text(encoding="utf-8")
    assert vtt.startswith("WEBVTT\n\n")
    assert "00:00:00.000 --> 00:00:01.500\nHello world." in vtt


def test_transcript_artifact_writer_uses_custom_output_base_name(tmp_path: Path) -> None:
    transcript = build_transcript(tmp_path)
    path_builder = OutputPathBuilder(overwrite=True, base_name="custom-session")
    writer = TranscriptArtifactWriter(
        formats=("txt", "json"),
        txt_writer=TxtTranscriptWriter(path_builder),
        json_writer=JsonTranscriptWriter(path_builder),
    )

    artifacts = writer.write_all(transcript, tmp_path)

    assert {path.name for path in artifacts.paths} == {"custom-session.txt", "custom-session.json"}
    assert (tmp_path / "custom-session.txt").is_file()
    assert (tmp_path / "custom-session.json").is_file()
