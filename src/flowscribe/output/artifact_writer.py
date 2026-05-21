"""Write all v1 transcript artifacts."""

from __future__ import annotations

from pathlib import Path

from flowscribe.core.models import OutputArtifacts, Transcript
from flowscribe.output.json_writer import JsonTranscriptWriter
from flowscribe.output.md_writer import MarkdownTranscriptWriter
from flowscribe.output.srt_writer import SrtTranscriptWriter
from flowscribe.output.txt_writer import TxtTranscriptWriter
from flowscribe.output.vtt_writer import VttTranscriptWriter


class TranscriptArtifactWriter:
    def __init__(
        self,
        *,
        formats: tuple[str, ...] = ("txt", "md"),
        txt_writer: TxtTranscriptWriter | None = None,
        md_writer: MarkdownTranscriptWriter | None = None,
        json_writer: JsonTranscriptWriter | None = None,
        srt_writer: SrtTranscriptWriter | None = None,
        vtt_writer: VttTranscriptWriter | None = None,
    ) -> None:
        self._formats = formats
        self._txt_writer = txt_writer or TxtTranscriptWriter()
        self._md_writer = md_writer or MarkdownTranscriptWriter()
        self._json_writer = json_writer or JsonTranscriptWriter()
        self._srt_writer = srt_writer or SrtTranscriptWriter()
        self._vtt_writer = vtt_writer or VttTranscriptWriter()

    def write_all(
        self,
        transcript: Transcript,
        output_dir: Path,
        media_path: Path | None = None,
        media_kind: str | None = None,
    ) -> OutputArtifacts:
        paths = []
        for output_format in self._formats:
            if output_format == "txt":
                paths.append(self._txt_writer.write(transcript, output_dir))
            elif output_format == "md":
                paths.append(self._md_writer.write(transcript, output_dir))
            elif output_format == "json":
                # Create JSON writer with media binding info
                json_writer = JsonTranscriptWriter(
                    path_builder=self._json_writer._path_builder,
                    media_path=media_path,
                    media_kind=media_kind,
                )
                paths.append(json_writer.write(transcript, output_dir))
            elif output_format == "srt":
                paths.append(self._srt_writer.write(transcript, output_dir))
            elif output_format == "vtt":
                paths.append(self._vtt_writer.write(transcript, output_dir))
            else:
                raise ValueError(f"Unsupported output format: {output_format}")
        return OutputArtifacts(paths=tuple(paths))
