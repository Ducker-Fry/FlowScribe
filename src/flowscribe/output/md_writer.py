"""Markdown transcript writer."""

from __future__ import annotations

from pathlib import Path

from flowscribe.core.errors import OutputError
from flowscribe.core.models import Transcript
from flowscribe.output.paths import OutputPathBuilder


class MarkdownTranscriptWriter:
    def __init__(self, path_builder: OutputPathBuilder | None = None) -> None:
        self._path_builder = path_builder or OutputPathBuilder()

    def write(self, transcript: Transcript, output_dir: Path) -> Path:
        path = self._path_builder.build(transcript.source, output_dir, ".md")
        content = self._render(transcript)
        try:
            path.write_text(content, encoding="utf-8")
        except OSError as exc:
            raise OutputError(f"Could not write Markdown transcript to {path}: {exc}") from exc
        return path

    def _render(self, transcript: Transcript) -> str:
        source = transcript.source.path
        language = transcript.language or "auto"
        model = transcript.model_name or "unknown"
        options = transcript.options
        lines = [
            f"# {source.stem}",
            "",
            "## Metadata",
            "",
            f"- Source: `{source}`",
            f"- Language: `{language}`",
            f"- Model: `{model}`",
            f"- Created At: `{transcript.created_at.isoformat(timespec='seconds')}`",
        ]
        if options is not None:
            lines.extend(
                [
                    f"- Task: `{options.task}`",
                    f"- Beam Size: `{options.beam_size}`",
                    f"- VAD Filter: `{options.vad_filter}`",
                    f"- Preset: `{options.preset or 'none'}`",
                    f"- Initial Prompt: `{options.initial_prompt or 'none'}`",
                ]
            )
        lines.extend(
            [
                "",
                "## Transcript",
                "",
                transcript.text,
                "",
            ]
        )
        return "\n".join(lines)
