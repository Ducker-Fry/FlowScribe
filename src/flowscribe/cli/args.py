"""Command-line argument parsing."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CliOptions:
    command: str
    inputs: list[Path]
    output_dir: Path
    work_dir: Path | None
    model_name: str
    language: str | None
    preset: str | None
    task: str
    beam_size: int
    vad_filter: bool
    initial_prompt: str | None
    timestamps: bool
    word_timestamps: bool
    output_formats: tuple[str, ...]
    recursive: bool
    overwrite: bool
    keep_audio: bool


@dataclass(frozen=True)
class DoctorOptions:
    command: str
    output_dir: Path
    model_name: str


@dataclass(frozen=True)
class SearchOptions:
    command: str
    transcript: Path
    query: str
    context_chars: int
    limit: int | None
    after_seconds: float | None
    before_seconds: float | None
    json_output: bool


@dataclass(frozen=True)
class UrlOptions:
    command: str
    url: str
    output_dir: Path
    work_dir: Path | None
    model_name: str
    language: str | None
    preset: str | None
    task: str
    beam_size: int
    vad_filter: bool
    initial_prompt: str | None
    timestamps: bool
    word_timestamps: bool
    output_formats: tuple[str, ...]
    overwrite: bool
    keep_audio: bool
    keep_media: bool
    max_download_mb: int
    max_duration_seconds: float
    download_timeout_seconds: int


@dataclass(frozen=True)
class SimpleCommandOptions:
    command: str


def parse_args(
    argv: list[str] | None = None,
) -> CliOptions | DoctorOptions | SearchOptions | UrlOptions | SimpleCommandOptions:
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        return parse_transcribe_args(argv)

    command = argv[0]
    if command == "transcribe":
        return parse_transcribe_args(argv[1:], prog="flowscribe transcribe")
    if command == "doctor":
        return parse_doctor_args(argv[1:])
    if command == "search":
        return parse_search_args(argv[1:])
    if command == "url":
        return parse_url_args(argv[1:])
    if command in {"version", "formats", "models", "capture"}:
        return parse_simple_command_args(command, argv[1:])
    return parse_transcribe_args(argv)


def parse_transcribe_args(argv: list[str] | None = None, *, prog: str = "flowscribe") -> CliOptions:
    parser = argparse.ArgumentParser(
        prog=prog,
        description="Turn local audio/video files into raw TXT and Markdown transcripts.",
    )
    parser.add_argument(
        "inputs",
        nargs="+",
        type=Path,
        help="Local media file(s) or folder(s) to transcribe.",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=Path("outputs"),
        help="Directory for transcript outputs. Default: outputs",
    )
    parser.add_argument(
        "--work-dir",
        type=Path,
        default=None,
        help="Directory for temporary prepared audio. Default: <output-dir>/.flowscribe-work",
    )
    parser.add_argument(
        "-m",
        "--model",
        dest="model_name",
        default="small",
        help="Local faster-whisper model name or path. Default: small",
    )
    parser.add_argument(
        "-l",
        "--language",
        default=None,
        help="Optional language code, such as zh or en. Omit for auto-detection.",
    )
    parser.add_argument(
        "--preset",
        choices=["zh"],
        default=None,
        help="Apply a transcription preset. zh enables Chinese-oriented defaults.",
    )
    parser.add_argument(
        "--task",
        choices=["transcribe", "translate"],
        default="transcribe",
        help="Whisper task. Default: transcribe. Use translate only when explicitly needed.",
    )
    parser.add_argument(
        "--beam-size",
        type=int,
        default=5,
        help="Beam size for decoding. Higher can improve accuracy but may be slower. Default: 5",
    )
    parser.add_argument(
        "--vad-filter",
        action="store_true",
        help="Enable voice activity detection to reduce silence/noise segments.",
    )
    parser.add_argument(
        "--initial-prompt",
        default=None,
        help="Optional prompt to guide transcription terminology and language behavior.",
    )
    parser.add_argument(
        "--timestamps",
        action="store_true",
        help="Include segment-level timestamps in timestamp-aware output formats.",
    )
    parser.add_argument(
        "--word-timestamps",
        action="store_true",
        help=(
            "Request word-level timestamps from the transcription provider. "
            "This is most useful with --format json."
        ),
    )
    parser.add_argument(
        "--format",
        dest="output_formats",
        default="txt,md",
        help="Comma-separated output formats. Supported: txt,md,json,srt,vtt. Default: txt,md",
    )
    parser.add_argument(
        "-r",
        "--recursive",
        action="store_true",
        help="Recursively scan input folders.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing transcript files instead of creating numbered copies.",
    )
    parser.add_argument(
        "--keep-audio",
        action="store_true",
        help="Keep prepared WAV files in the work directory for debugging or reuse.",
    )
    namespace = parser.parse_args(argv)
    return CliOptions(
        command="transcribe",
        inputs=namespace.inputs,
        output_dir=namespace.output_dir,
        work_dir=namespace.work_dir,
        model_name=namespace.model_name,
        language=namespace.language,
        preset=namespace.preset,
        task=namespace.task,
        beam_size=namespace.beam_size,
        vad_filter=namespace.vad_filter,
        initial_prompt=namespace.initial_prompt,
        timestamps=namespace.timestamps,
        word_timestamps=namespace.word_timestamps,
        output_formats=parse_output_formats(namespace.output_formats),
        recursive=namespace.recursive,
        overwrite=namespace.overwrite,
        keep_audio=namespace.keep_audio,
    )


def add_transcription_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=Path("outputs"),
        help="Directory for transcript outputs. Default: outputs",
    )
    parser.add_argument(
        "--work-dir",
        type=Path,
        default=None,
        help="Directory for temporary prepared audio. Default: <output-dir>/.flowscribe-work",
    )
    parser.add_argument(
        "-m",
        "--model",
        dest="model_name",
        default="small",
        help="Local faster-whisper model name or path. Default: small",
    )
    parser.add_argument(
        "-l",
        "--language",
        default=None,
        help="Optional language code, such as zh or en. Omit for auto-detection.",
    )
    parser.add_argument(
        "--preset",
        choices=["zh"],
        default=None,
        help="Apply a transcription preset. zh enables Chinese-oriented defaults.",
    )
    parser.add_argument(
        "--task",
        choices=["transcribe", "translate"],
        default="transcribe",
        help="Whisper task. Default: transcribe. Use translate only when explicitly needed.",
    )
    parser.add_argument(
        "--beam-size",
        type=int,
        default=5,
        help="Beam size for decoding. Higher can improve accuracy but may be slower. Default: 5",
    )
    parser.add_argument(
        "--vad-filter",
        action="store_true",
        help="Enable voice activity detection to reduce silence/noise segments.",
    )
    parser.add_argument(
        "--initial-prompt",
        default=None,
        help="Optional prompt to guide transcription terminology and language behavior.",
    )
    parser.add_argument(
        "--timestamps",
        action="store_true",
        help="Include segment-level timestamps in timestamp-aware output formats.",
    )
    parser.add_argument(
        "--word-timestamps",
        action="store_true",
        help=(
            "Request word-level timestamps from the transcription provider. "
            "This is most useful with --format json."
        ),
    )
    parser.add_argument(
        "--format",
        dest="output_formats",
        default="txt,md",
        help="Comma-separated output formats. Supported: txt,md,json,srt,vtt. Default: txt,md",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing transcript files instead of creating numbered copies.",
    )
    parser.add_argument(
        "--keep-audio",
        action="store_true",
        help="Keep prepared WAV files in the work directory for debugging or reuse.",
    )


def parse_url_args(argv: list[str] | None = None) -> UrlOptions:
    parser = argparse.ArgumentParser(
        prog="flowscribe url",
        description="Download or extract remote audio from a public URL and transcribe it.",
    )
    parser.add_argument("url", help="Public http(s) audio/video URL or supported video page URL.")
    add_transcription_options(parser)
    parser.add_argument(
        "--keep-media",
        action="store_true",
        help="Keep downloaded or extracted URL media files instead of deleting them.",
    )
    parser.add_argument(
        "--max-download-mb",
        type=positive_int,
        default=2048,
        help="Maximum downloaded audio/intermediate media size in MB. Default: 2048",
    )
    parser.add_argument(
        "--max-duration",
        type=parse_time_value,
        default=4 * 60 * 60,
        help="Maximum remote media duration. Supports SS, MM:SS, HH:MM:SS. Default: 04:00:00",
    )
    parser.add_argument(
        "--download-timeout",
        type=positive_int,
        default=30,
        help="Download/network timeout in seconds. Default: 30",
    )
    namespace = parser.parse_args(argv)
    return UrlOptions(
        command="url",
        url=namespace.url,
        output_dir=namespace.output_dir,
        work_dir=namespace.work_dir,
        model_name=namespace.model_name,
        language=namespace.language,
        preset=namespace.preset,
        task=namespace.task,
        beam_size=namespace.beam_size,
        vad_filter=namespace.vad_filter,
        initial_prompt=namespace.initial_prompt,
        timestamps=namespace.timestamps,
        word_timestamps=namespace.word_timestamps,
        output_formats=parse_output_formats(namespace.output_formats),
        overwrite=namespace.overwrite,
        keep_audio=namespace.keep_audio,
        keep_media=namespace.keep_media,
        max_download_mb=namespace.max_download_mb,
        max_duration_seconds=namespace.max_duration,
        download_timeout_seconds=namespace.download_timeout,
    )


def parse_doctor_args(argv: list[str] | None = None) -> DoctorOptions:
    parser = argparse.ArgumentParser(
        prog="flowscribe doctor",
        description="Check whether the local FlowScribe environment is ready.",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=Path("outputs"),
        help="Directory to test for transcript output writes. Default: outputs",
    )
    parser.add_argument(
        "-m",
        "--model",
        dest="model_name",
        default="small",
        help="Local faster-whisper model name or path to check. Default: small",
    )
    namespace = parser.parse_args(argv)
    return DoctorOptions(
        command="doctor",
        output_dir=namespace.output_dir,
        model_name=namespace.model_name,
    )


def parse_search_args(argv: list[str] | None = None) -> SearchOptions:
    parser = argparse.ArgumentParser(
        prog="flowscribe search",
        description="Search a FlowScribe transcript JSON file and locate keyword timestamps.",
    )
    parser.add_argument("transcript", type=Path, help="Transcript JSON file to search.")
    parser.add_argument("query", help="Keyword or phrase to locate.")
    parser.add_argument(
        "--context-chars",
        type=non_negative_int,
        default=24,
        help="Number of context characters to show around each hit. Default: 24",
    )
    parser.add_argument(
        "--limit",
        type=positive_int,
        default=None,
        help="Maximum number of matches to display.",
    )
    parser.add_argument(
        "--after",
        type=parse_time_value,
        default=None,
        help="Only include matches after this time, such as 00:10:00.",
    )
    parser.add_argument(
        "--before",
        type=parse_time_value,
        default=None,
        help="Only include matches before this time, such as 00:30:00.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Write search results as JSON for GUI or automation use.",
    )
    namespace = parser.parse_args(argv)
    if (
        namespace.after is not None
        and namespace.before is not None
        and namespace.after > namespace.before
    ):
        parser.error("--after must be earlier than or equal to --before.")
    return SearchOptions(
        command="search",
        transcript=namespace.transcript,
        query=namespace.query,
        context_chars=namespace.context_chars,
        limit=namespace.limit,
        after_seconds=namespace.after,
        before_seconds=namespace.before,
        json_output=namespace.json_output,
    )


def parse_simple_command_args(command: str, argv: list[str]) -> SimpleCommandOptions:
    descriptions = {
        "version": "Show FlowScribe version information.",
        "formats": "List supported local media file extensions.",
        "models": "Show recommended local transcription models.",
        "capture": "Placeholder for future system audio capture.",
    }
    parser = argparse.ArgumentParser(
        prog=f"flowscribe {command}",
        description=descriptions[command],
    )
    parser.parse_args(argv)
    return SimpleCommandOptions(command=command)


def parse_output_formats(value: str) -> tuple[str, ...]:
    supported = {"txt", "md", "json", "srt", "vtt"}
    formats = tuple(dict.fromkeys(part.strip().lower() for part in value.split(",") if part.strip()))
    if not formats:
        raise argparse.ArgumentTypeError("At least one output format is required.")

    unsupported = [output_format for output_format in formats if output_format not in supported]
    if unsupported:
        joined = ", ".join(unsupported)
        supported_joined = ",".join(sorted(supported))
        raise argparse.ArgumentTypeError(
            f"Unsupported output format(s): {joined}. Supported: {supported_joined}"
        )
    return formats


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("Value must be greater than zero.")
    return parsed


def non_negative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("Value cannot be negative.")
    return parsed


def parse_time_value(value: str) -> float:
    parts = value.strip().split(":")
    if not parts or len(parts) > 3:
        raise argparse.ArgumentTypeError("Time must be SS, MM:SS, or HH:MM:SS.")

    try:
        numbers = [float(part) for part in parts]
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Time must contain only numbers and ':'.") from exc

    if any(number < 0 for number in numbers):
        raise argparse.ArgumentTypeError("Time cannot be negative.")
    if len(numbers) == 1:
        return numbers[0]
    if len(numbers) == 2:
        minutes, seconds = numbers
        return minutes * 60 + seconds
    hours, minutes, seconds = numbers
    return hours * 3600 + minutes * 60 + seconds
