"""Write all v1 transcript artifacts."""

from __future__ import annotations

from pathlib import Path

from flowscribe.core.models import OutputArtifacts, Transcript
from flowscribe.output.md_writer import MarkdownTranscriptWriter
from flowscribe.output.txt_writer import TxtTranscriptWriter


class TranscriptArtifactWriter:
    def __init__(
        self,
        *,
        txt_writer: TxtTranscriptWriter | None = None,
        md_writer: MarkdownTranscriptWriter | None = None,
    ) -> None:
        self._txt_writer = txt_writer or TxtTranscriptWriter()
        self._md_writer = md_writer or MarkdownTranscriptWriter()

    def write_all(self, transcript: Transcript, output_dir: Path) -> OutputArtifacts:
        txt_path = self._txt_writer.write(transcript, output_dir)
        md_path = self._md_writer.write(transcript, output_dir)
        return OutputArtifacts(txt_path=txt_path, md_path=md_path)
