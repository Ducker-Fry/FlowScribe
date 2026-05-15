import json
from pathlib import Path

import pytest

from flowscribe.transcript.reexport import reexport_transcript_json


def test_reexport_transcript_json_writes_selected_formats_with_corrected_text(
    tmp_path: Path,
) -> None:
    transcript = tmp_path / "lesson.corrected.json"
    transcript.write_text(
        """
{
  "source": "lesson.mp4",
  "language": "en",
  "model": "small",
  "options": {
    "model_name": "small",
    "language": "en",
    "task": "transcribe",
    "beam_size": 5,
    "vad_filter": false,
    "word_timestamps": true
  },
  "text": "Corrected first line.\\nSecond line.",
  "corrections": {
    "edited_segment_count": 1
  },
  "segments": [
    {
      "index": 1,
      "text": "Corrected first line.",
      "start_seconds": 0.0,
      "end_seconds": 1.5,
      "correction": {
        "edited": true,
        "original_text": "First line."
      }
    },
    {
      "index": 2,
      "text": "Second line.",
      "start_seconds": 1.5,
      "end_seconds": 3.0
    }
  ]
}
""".strip(),
        encoding="utf-8",
    )
    output_dir = tmp_path / "exports"

    artifacts = reexport_transcript_json(
        transcript,
        output_dir=output_dir,
        output_formats=("txt", "md", "json", "srt", "vtt"),
        include_timestamps=True,
        overwrite=True,
    )

    assert {path.suffix for path in artifacts.paths} == {".txt", ".md", ".json", ".srt", ".vtt"}
    assert (output_dir / "lesson.corrected.txt").read_text(encoding="utf-8") == (
        "Corrected first line.\nSecond line.\n"
    )
    markdown = (output_dir / "lesson.corrected.md").read_text(encoding="utf-8")
    assert "Corrected first line." in markdown
    assert "[00:00:00.000 - 00:00:01.500] Corrected first line." in markdown
    srt = (output_dir / "lesson.corrected.srt").read_text(encoding="utf-8")
    assert "Corrected first line." in srt
    vtt = (output_dir / "lesson.corrected.vtt").read_text(encoding="utf-8")
    assert "Corrected first line." in vtt

    copied_json = json.loads((output_dir / "lesson.corrected.json").read_text(encoding="utf-8"))
    assert copied_json["segments"][0]["text"] == "Corrected first line."
    assert copied_json["segments"][0]["correction"]["edited"] is True


def test_reexport_transcript_json_supports_custom_base_name(tmp_path: Path) -> None:
    transcript = tmp_path / "lesson.json"
    transcript.write_text(
        """
{
  "source": "lesson.mp4",
  "text": "Hello world.",
  "segments": [
    {
      "index": 1,
      "text": "Hello world.",
      "start_seconds": 0.0,
      "end_seconds": 1.0
    }
  ]
}
""".strip(),
        encoding="utf-8",
    )

    artifacts = reexport_transcript_json(
        transcript,
        output_dir=tmp_path / "exports",
        output_formats=("txt", "json"),
        output_name_base="review-copy",
        overwrite=True,
    )

    assert {path.name for path in artifacts.paths} == {"review-copy.txt", "review-copy.json"}


def test_reexport_transcript_json_rejects_invalid_payload(tmp_path: Path) -> None:
    broken = tmp_path / "broken.json"
    broken.write_text('{"segments": "bad"}', encoding="utf-8")

    with pytest.raises(ValueError, match="segments list"):
        reexport_transcript_json(
            broken,
            output_dir=tmp_path / "exports",
            output_formats=("txt",),
        )
