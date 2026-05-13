"""Command-line entry point for FlowScribe."""

from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path
from urllib.parse import urlparse

from flowscribe.app.models import ProgressEvent, SourceSpec, TranscriptionJob
from flowscribe.app.service import TranscriptionService
from flowscribe.cli.args import parse_args
from flowscribe.cli.doctor import run_doctor
from flowscribe import __version__
from flowscribe.core.errors import FlowScribeError
from flowscribe.input.file_filter import SUPPORTED_MEDIA_EXTENSIONS
from flowscribe.input.url_inspector import UrlInspector
from flowscribe.media.inspector import LocalMediaInspector
from flowscribe.output.time_format import format_timestamp
from flowscribe.search.transcript_search import search_transcript_file


def main(argv: list[str] | None = None) -> int:
    options = parse_args(argv)
    if options.command == "doctor":
        return run_doctor(output_dir=options.output_dir, model_name=options.model_name)
    if options.command == "search":
        return run_search(options)
    if options.command == "inspect":
        return run_inspect(options)
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

    return run_transcribe(options)


def run_transcribe(options) -> int:
    job = _job_from_transcribe_options(options)
    result = TranscriptionService().run(job, progress=_print_cli_progress)

    print(f"Done. Succeeded: {result.succeeded}. Failed: {result.failed}.")
    if result.errors:
        print("Failures:")
        for error in result.errors:
            print(f"- {error.source}: {error.message}")
        return 1
    return 0


def run_url(options) -> int:
    job = _job_from_url_options(options)
    result = TranscriptionService().run(job, progress=_print_cli_progress)
    if result.errors:
        for error in result.errors:
            print(f"Error: {error.message}", file=sys.stderr)
        return 2
    print(f"Done. Succeeded: {result.succeeded}. Failed: {result.failed}.")
    return 0


def run_inspect(options) -> int:
    try:
        if _is_http_url(options.source):
            inspection = UrlInspector(
                timeout_seconds=options.timeout_seconds,
                network_family=options.network_family,
                cookies_path=options.cookies,
            ).inspect(options.source)
            payload = {"type": "url", **asdict(inspection)}
        else:
            inspection = LocalMediaInspector(timeout_seconds=options.timeout_seconds).inspect(
                Path(options.source)
            )
            payload = {"type": "local", **asdict(inspection)}
            payload["source"] = str(payload["source"])
    except FlowScribeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if options.json_output:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    _print_inspection(payload)
    return 0


def _print_inspection(payload: dict) -> None:
    print("FlowScribe inspect")
    print("===================")
    print(f"Type: {payload['type']}")
    print(f"Source: {payload['source']}")

    if payload["type"] == "local":
        print(f"Exists: {_yes_no(payload['exists'])}")
        print(f"Duration: {_format_optional_duration(payload['duration_seconds'])}")
        print(f"Audio streams: {payload['audio_streams']}")
        print(f"Video streams: {payload['video_streams']}")
        print(f"Format: {payload['format_name'] or 'unknown'}")
        print(f"Size: {_format_size(payload['size_bytes'])}")
        print(f"Ready for transcription: {_yes_no(payload['has_audio'])}")
        if not payload["has_audio"]:
            print("Suggestion: use media that contains an audio stream.")
        return

    print(f"Kind: {payload['kind']}")
    print(f"Title: {payload['title'] or 'unknown'}")
    print(f"Duration: {_format_optional_duration(payload['duration_seconds'])}")
    print(f"Formats: {payload['format_count']}")
    print(f"Audio-only stream: {_yes_no(payload['has_audio_only'])}")
    print(f"Combined media stream: {_yes_no(payload['has_combined_media'])}")
    print(f"Planned strategy: {payload['selected_strategy']}")
    selected = payload.get("selected_format")
    if selected:
        print("Selected format:")
        print(f"  id: {selected.get('format_id') or 'unknown'}")
        print(f"  ext: {selected.get('extension') or 'unknown'}")
        print(f"  protocol: {selected.get('protocol') or 'unknown'}")
        print(f"  resolution: {selected.get('resolution') or 'unknown'}")
        print(f"  audio codec: {selected.get('audio_codec') or 'unknown'}")
        print(f"  video codec: {selected.get('video_codec') or 'unknown'}")
        print(f"  bitrate: {selected.get('bitrate') or 'unknown'}")
        print(f"  size: {_format_size(selected.get('size_bytes'))}")
    if not payload["has_audio_only"] and payload["has_combined_media"]:
        print("Note: no standalone audio stream was found; FlowScribe will stream combined media and save only extracted audio.")


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


def _job_from_transcribe_options(options) -> TranscriptionJob:
    return TranscriptionJob(
        sources=tuple(
            SourceSpec(kind="local", value=str(input_path), recursive=options.recursive)
            for input_path in options.inputs
        ),
        output_dir=options.output_dir,
        work_dir=options.work_dir,
        model_name=options.model_name,
        language=options.language,
        preset=options.preset,
        task=options.task,
        beam_size=options.beam_size,
        vad_filter=options.vad_filter,
        no_vad_filter=options.no_vad_filter,
        initial_prompt=options.initial_prompt,
        timestamps=options.timestamps,
        word_timestamps=options.word_timestamps,
        output_formats=options.output_formats,
        overwrite=options.overwrite,
        keep_audio=options.keep_audio,
    )


def _job_from_url_options(options) -> TranscriptionJob:
    return TranscriptionJob(
        sources=(SourceSpec(kind="url", value=options.url, keep_media=options.keep_media),),
        output_dir=options.output_dir,
        work_dir=options.work_dir,
        model_name=options.model_name,
        language=options.language,
        preset=options.preset,
        task=options.task,
        beam_size=options.beam_size,
        vad_filter=options.vad_filter,
        no_vad_filter=options.no_vad_filter,
        initial_prompt=options.initial_prompt,
        timestamps=options.timestamps,
        word_timestamps=options.word_timestamps,
        output_formats=options.output_formats,
        overwrite=options.overwrite,
        keep_audio=options.keep_audio,
        max_download_mb=options.max_download_mb,
        max_duration_seconds=options.max_duration_seconds,
        download_timeout_seconds=options.download_timeout_seconds,
        network_family=options.network_family,
        cookies_path=options.cookies,
    )


def _print_cli_progress(event: ProgressEvent) -> None:
    if event.stage == "complete":
        return
    if event.stage == "error":
        return
    if event.stage == "discover" and event.source is None:
        return
    print(event.message)


def _is_http_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"


def _format_optional_duration(value: float | None) -> str:
    if value is None:
        return "unknown"
    return format_timestamp(value)


def _format_size(value: int | None) -> str:
    if value is None:
        return "unknown"
    if value < 1024:
        return f"{value} B"
    if value < 1024 * 1024:
        return f"{value / 1024:.1f} KiB"
    return f"{value / (1024 * 1024):.1f} MiB"

if __name__ == "__main__":
    raise SystemExit(main())
