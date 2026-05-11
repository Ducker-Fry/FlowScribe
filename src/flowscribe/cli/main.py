"""Command-line entry point for FlowScribe."""

from __future__ import annotations

import sys

from flowscribe.cli.args import parse_args
from flowscribe.config.settings import AppSettings
from flowscribe.core.errors import FlowScribeError
from flowscribe.core.pipeline import LocalTranscriptionPipeline
from flowscribe.core.runner import JobRunner
from flowscribe.input.local_source import LocalFileSource
from flowscribe.media.audio_extractor import FfmpegAudioExtractor
from flowscribe.output.artifact_writer import TranscriptArtifactWriter
from flowscribe.output.md_writer import MarkdownTranscriptWriter
from flowscribe.output.paths import OutputPathBuilder
from flowscribe.output.txt_writer import TxtTranscriptWriter
from flowscribe.transcription.local_whisper import LocalWhisperTranscriber


def main(argv: list[str] | None = None) -> int:
    options = parse_args(argv)
    settings = AppSettings.from_options(
        output_dir=options.output_dir,
        work_dir=options.work_dir,
        model_name=options.model_name,
        language=options.language,
        preset=options.preset,
        task=options.task,
        beam_size=options.beam_size,
        vad_filter=options.vad_filter,
        initial_prompt=options.initial_prompt,
        recursive=options.recursive,
        overwrite=options.overwrite,
        keep_audio=options.keep_audio,
    )

    path_builder = OutputPathBuilder(overwrite=settings.overwrite)
    input_source = LocalFileSource(options.inputs, recursive=settings.recursive)
    pipeline = LocalTranscriptionPipeline(
        media_preparer=FfmpegAudioExtractor(sample_rate=settings.sample_rate),
        transcriber=LocalWhisperTranscriber(
            model_name=settings.model_name,
            language=settings.language,
            task=settings.task,
            beam_size=settings.beam_size,
            vad_filter=settings.vad_filter,
            initial_prompt=settings.initial_prompt,
            preset=settings.preset,
        ),
        artifact_writer=TranscriptArtifactWriter(
            txt_writer=TxtTranscriptWriter(path_builder),
            md_writer=MarkdownTranscriptWriter(path_builder),
        ),
        work_dir=settings.work_dir,
        output_dir=settings.output_dir,
        keep_audio=settings.keep_audio,
    )
    runner = JobRunner(input_source=input_source, pipeline=pipeline, progress=print)

    try:
        result = runner.run()
    except FlowScribeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    print(f"Done. Succeeded: {result.succeeded}. Failed: {result.failed}.")
    if result.failures:
        print("Failures:")
        for failure in result.failures:
            print(f"- {failure.source}: {failure.message}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
