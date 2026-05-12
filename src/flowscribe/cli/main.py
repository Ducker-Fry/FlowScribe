"""Command-line entry point for FlowScribe."""

from __future__ import annotations

import json
import shutil
import sys

from flowscribe.cli.args import parse_args
from flowscribe.cli.doctor import run_doctor
from flowscribe import __version__
from flowscribe.config.settings import AppSettings
from flowscribe.core.errors import FlowScribeError
from flowscribe.core.models import MediaItem
from flowscribe.input.file_filter import SUPPORTED_MEDIA_EXTENSIONS
from flowscribe.core.pipeline import LocalTranscriptionPipeline
from flowscribe.core.runner import JobRunner
from flowscribe.input.local_source import LocalFileSource
from flowscribe.input.url_downloader import UrlAudioDownloader
from flowscribe.media.audio_extractor import FfmpegAudioExtractor
from flowscribe.nlp.script_converter import simplify_chinese_transcript
from flowscribe.output.artifact_writer import TranscriptArtifactWriter
from flowscribe.output.json_writer import JsonTranscriptWriter
from flowscribe.output.md_writer import MarkdownTranscriptWriter
from flowscribe.output.paths import OutputPathBuilder
from flowscribe.output.srt_writer import SrtTranscriptWriter
from flowscribe.output.time_format import format_timestamp
from flowscribe.output.txt_writer import TxtTranscriptWriter
from flowscribe.output.vtt_writer import VttTranscriptWriter
from flowscribe.search.transcript_search import search_transcript_file
from flowscribe.transcription.local_whisper import LocalWhisperTranscriber


def main(argv: list[str] | None = None) -> int:
    options = parse_args(argv)
    if options.command == "doctor":
        return run_doctor(output_dir=options.output_dir, model_name=options.model_name)
    if options.command == "search":
        return run_search(options)
    if options.command == "url":
        return run_url(options)
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
    if options.command == "capture":
        print("System audio capture is planned but not implemented yet.")
        print("Future example: flowscribe capture --duration 10m -o outputs")
        return 2

    settings = build_settings(options)

    path_builder = OutputPathBuilder(overwrite=settings.overwrite)
    input_source = LocalFileSource(options.inputs, recursive=settings.recursive)
    pipeline = build_pipeline(settings, options.output_formats, options.timestamps, path_builder)
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


def build_settings(options) -> AppSettings:
    return AppSettings.from_options(
        output_dir=options.output_dir,
        work_dir=options.work_dir,
        model_name=options.model_name,
        language=options.language,
        preset=options.preset,
        task=options.task,
        beam_size=options.beam_size,
        vad_filter=options.vad_filter,
        initial_prompt=options.initial_prompt,
        word_timestamps=options.word_timestamps,
        recursive=options.recursive,
        overwrite=options.overwrite,
        keep_audio=options.keep_audio,
    )


def build_pipeline(
    settings: AppSettings,
    output_formats: tuple[str, ...],
    timestamps: bool,
    path_builder: OutputPathBuilder,
) -> LocalTranscriptionPipeline:
    return LocalTranscriptionPipeline(
        media_preparer=FfmpegAudioExtractor(sample_rate=settings.sample_rate),
        transcriber=LocalWhisperTranscriber(
            model_name=settings.model_name,
            language=settings.language,
            task=settings.task,
            beam_size=settings.beam_size,
            vad_filter=settings.vad_filter,
            initial_prompt=settings.initial_prompt,
            preset=settings.preset,
            word_timestamps=settings.word_timestamps,
        ),
        artifact_writer=TranscriptArtifactWriter(
            formats=output_formats,
            txt_writer=TxtTranscriptWriter(path_builder),
            md_writer=MarkdownTranscriptWriter(
                path_builder,
                include_timestamps=timestamps,
            ),
            json_writer=JsonTranscriptWriter(path_builder),
            srt_writer=SrtTranscriptWriter(path_builder),
            vtt_writer=VttTranscriptWriter(path_builder),
        ),
        work_dir=settings.work_dir,
        output_dir=settings.output_dir,
        keep_audio=settings.keep_audio,
        transcript_normalizer=(
            simplify_chinese_transcript
            if settings.language == "zh" or settings.preset == "zh"
            else None
        ),
    )


def run_url(options) -> int:
    settings = build_settings(_UrlSettingsAdapter(options))
    url_media_dir = settings.work_dir / ".url-media"
    downloader = UrlAudioDownloader(
        download_dir=url_media_dir,
        max_bytes=options.max_download_mb * 1024 * 1024,
        max_duration_seconds=options.max_duration_seconds,
        timeout_seconds=options.download_timeout_seconds,
    )

    try:
        print("Downloading/extracting remote audio...")
        download = downloader.download_audio(options.url)
        print(f"Remote audio ready: {download.path}")
        path_builder = OutputPathBuilder(overwrite=settings.overwrite)
        pipeline = build_pipeline(settings, options.output_formats, options.timestamps, path_builder)
        artifacts = pipeline.process(MediaItem(path=download.path))
    except FlowScribeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    finally:
        if "download" in locals() and not options.keep_media:
            shutil.rmtree(download.cleanup_dir, ignore_errors=True)

    for path in artifacts.paths:
        print(f"Wrote: {path}")
    print("Done. Succeeded: 1. Failed: 0.")
    return 0


def run_search(options) -> int:
    try:
        hits = search_transcript_file(
            options.transcript,
            options.query,
            context_chars=options.context_chars,
            limit=options.limit,
            after_seconds=options.after_seconds,
            before_seconds=options.before_seconds,
        )
    except FlowScribeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if options.json_output:
        print(json.dumps(_search_payload(options, hits), ensure_ascii=False, indent=2))
        return 0 if hits else 1

    if not hits:
        print(f"No matches found for: {options.query}")
        return 1

    for index, hit in enumerate(hits, start=1):
        print(f"[{index}]")
        print(f"File: {hit.file}")
        print(f"Match: {hit.matched_text}")
        print(f"Time: {format_timestamp(hit.start_seconds)} - {format_timestamp(hit.end_seconds)}")
        print(f"Context: {hit.context}")
        if index < len(hits):
            print("")
    return 0


def _search_payload(options, hits) -> dict:
    return {
        "transcript": str(options.transcript),
        "query": options.query,
        "filters": {
            "limit": options.limit,
            "after_seconds": options.after_seconds,
            "before_seconds": options.before_seconds,
            "context_chars": options.context_chars,
        },
        "count": len(hits),
        "hits": [
            {
                "file": str(hit.file),
                "query": hit.query,
                "matched_text": hit.matched_text,
                "start_seconds": hit.start_seconds,
                "end_seconds": hit.end_seconds,
                "start": format_timestamp(hit.start_seconds),
                "end": format_timestamp(hit.end_seconds),
                "context": hit.context,
            }
            for hit in hits
        ],
    }


class _UrlSettingsAdapter:
    def __init__(self, options) -> None:
        self.output_dir = options.output_dir
        self.work_dir = options.work_dir
        self.model_name = options.model_name
        self.language = options.language
        self.preset = options.preset
        self.task = options.task
        self.beam_size = options.beam_size
        self.vad_filter = options.vad_filter
        self.initial_prompt = options.initial_prompt
        self.word_timestamps = options.word_timestamps
        self.recursive = False
        self.overwrite = options.overwrite
        self.keep_audio = options.keep_audio


if __name__ == "__main__":
    raise SystemExit(main())
