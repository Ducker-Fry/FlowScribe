"""Command-line entry point for FlowScribe."""

from __future__ import annotations

import sys

from flowscribe.cli.args import parse_args
from flowscribe.cli.doctor import run_doctor
from flowscribe import __version__
from flowscribe.config.settings import AppSettings
from flowscribe.core.errors import FlowScribeError
from flowscribe.input.file_filter import SUPPORTED_MEDIA_EXTENSIONS
from flowscribe.core.pipeline import LocalTranscriptionPipeline
from flowscribe.core.runner import JobRunner
from flowscribe.input.local_source import LocalFileSource
from flowscribe.media.audio_extractor import FfmpegAudioExtractor
from flowscribe.output.artifact_writer import TranscriptArtifactWriter
from flowscribe.output.json_writer import JsonTranscriptWriter
from flowscribe.output.md_writer import MarkdownTranscriptWriter
from flowscribe.output.paths import OutputPathBuilder
from flowscribe.output.srt_writer import SrtTranscriptWriter
from flowscribe.output.txt_writer import TxtTranscriptWriter
from flowscribe.transcription.local_whisper import LocalWhisperTranscriber


def main(argv: list[str] | None = None) -> int:
    options = parse_args(argv)
    if options.command == "doctor":
        return run_doctor(output_dir=options.output_dir, model_name=options.model_name)
    if options.command == "version":
        print(f"FlowScribe {__version__}")
        print(f"Python {sys.version.split()[0]}")
        return 0
    if options.command == "formats":
        print("Supported local media extensions:")
        for extension in sorted(SUPPORTED_MEDIA_EXTENSIONS):
            print(f"- {extension}")
        return 0
    if options.command == "models":
        print("Recommended local transcription models:")
        print("- tiny: quick smoke tests only; fastest and least accurate")
        print("- small: recommended starting point for real use")
        print("- medium: better accuracy, slower and heavier")
        print("- large-v3 / large-v3-turbo: highest local accuracy, requires more resources")
        print("")
        print("Examples:")
        print("  flowscribe transcribe video.mp4 --model small --preset zh")
        print("  flowscribe transcribe video.mp4 --model medium --language en")
        return 0
    if options.command == "url":
        print("URL input is planned but not implemented yet.")
        print("Future example: flowscribe url \"https://example.com/video\" -o outputs")
        return 2
    if options.command == "capture":
        print("System audio capture is planned but not implemented yet.")
        print("Future example: flowscribe capture --duration 10m -o outputs")
        return 2

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
            formats=options.output_formats,
            txt_writer=TxtTranscriptWriter(path_builder),
            md_writer=MarkdownTranscriptWriter(
                path_builder,
                include_timestamps=options.timestamps,
            ),
            json_writer=JsonTranscriptWriter(path_builder),
            srt_writer=SrtTranscriptWriter(path_builder),
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
