"""Command-line argument parsers."""

from __future__ import annotations

import argparse
from pathlib import Path

from .options import (
    CliOptions,
    DoctorOptions,
    InstallCommandOptions,
    InspectOptions,
    ModelCommandOptions,
    RemoteCommandOptions,
    SearchOptions,
    ServeOptions,
    SimpleCommandOptions,
    UrlOptions,
)
from .validators import (
    non_negative_float,
    non_negative_int,
    parse_output_formats,
    parse_time_value,
    positive_float,
    positive_int,
)


def add_progressive_options(parser: argparse.ArgumentParser) -> None:
    progressive_group = parser.add_mutually_exclusive_group()
    progressive_group.add_argument(
        "--progressive",
        action="store_const",
        const="enabled",
        dest="progressive_mode",
        help="Force progressive chunked transcription for longer-running media.",
    )
    progressive_group.add_argument(
        "--no-progressive",
        action="store_const",
        const="disabled",
        dest="progressive_mode",
        help="Force the classic one-shot transcription path.",
    )
    parser.set_defaults(progressive_mode="auto")
    parser.add_argument(
        "--chunk-seconds",
        type=positive_float,
        dest="progressive_chunk_seconds",
        default=30.0,
        help="Progressive chunk size in seconds. Default: 30",
    )
    parser.add_argument(
        "--chunk-overlap-seconds",
        type=non_negative_float,
        dest="progressive_chunk_overlap_seconds",
        default=3.0,
        help="Progressive chunk overlap in seconds. Default: 3",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        dest="progressive_resume",
        help="Resume from progressive chunk cache when it is available.",
    )
    parser.add_argument(
        "--max-workers",
        type=non_negative_int,
        dest="progressive_max_workers",
        default=1,
        help="Maximum progressive chunk workers. Use 0 for auto. Default: 1",
    )


def add_remote_execution_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--execution",
        choices=["local", "remote"],
        default="local",
        dest="execution_mode",
        help="Execution mode. Use remote to submit work to a FlowScribe server. Default: local",
    )
    parser.add_argument(
        "--server",
        dest="server_target",
        default=None,
        help="Remote server profile name or base URL when --execution remote is used.",
    )
    parser.add_argument(
        "--remote-token",
        default=None,
        help="Optional bearer token override for remote execution.",
    )
    parser.add_argument(
        "--remote-poll-seconds",
        type=positive_float,
        default=1.0,
        help="Polling interval for remote task status and event refresh. Default: 1.0",
    )
    artifact_group = parser.add_mutually_exclusive_group()
    artifact_group.add_argument(
        "--download-artifacts",
        action="store_true",
        dest="download_artifacts",
        default=None,
        help="Download remote result artifacts to the local output directory.",
    )
    artifact_group.add_argument(
        "--no-download-artifacts",
        action="store_false",
        dest="download_artifacts",
        default=None,
        help="Skip downloading remote result artifacts after task completion.",
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
        "--provider",
        dest="provider_name",
        choices=["local-whisper", "native-engine", "paraformer"],
        default=None,
        help=(
            "Transcription provider. Use local-whisper for faster-whisper model names like "
            "`small`, native-engine for a local whisper.cpp ggml .bin model path, or "
            "paraformer for Chinese-first FunASR transcription. Default: local-whisper "
            "(auto-selects paraformer with --preset zh when omitted)."
        ),
    )
    parser.add_argument(
        "-m",
        "--model",
        dest="model_name",
        default="small",
        help=(
            "Model name or path. local-whisper accepts names like `small` or a local path; "
            "native-engine requires a local whisper.cpp ggml .bin file path; paraformer "
            "accepts `paraformer-zh`. Default: small"
        ),
    )
    parser.add_argument(
        "-l",
        "--language",
        default=None,
        help="Optional language code, such as zh or en. Omit for auto-detection.",
    )
    parser.add_argument(
        "--preset",
        choices=["speed", "quality", "zh"],
        default=None,
        help=(
            "Apply a transcription preset. "
            "speed: optimize for fast transcription (beam_size=1, vad_filter=True, int8). "
            "quality: optimize for accuracy (beam_size=5, vad_filter=False). "
            "zh: Chinese-oriented defaults."
        ),
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
    vad_group = parser.add_mutually_exclusive_group()
    vad_group.add_argument(
        "--vad-filter",
        action="store_true",
        help="Enable voice activity detection to reduce silence/noise segments.",
    )
    vad_group.add_argument(
        "--no-vad-filter",
        action="store_true",
        help="Disable voice activity detection, overriding preset defaults.",
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
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Write structured task results as JSON for agent and automation use.",
    )
    parser.add_argument(
        "--events",
        choices=["jsonl"],
        default=None,
        dest="event_stream",
        help="Write structured progress events to stdout as JSONL.",
    )
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Disable human-oriented status output and use automation-safe output only.",
    )
    parser.add_argument(
        "--task-id",
        default=None,
        help="Explicit stable task id for agent workflows.",
    )
    parser.add_argument(
        "--resume-token",
        default=None,
        help="Explicit resume token for an existing progressive task.",
    )
    parser.add_argument(
        "--checkpoint-id",
        default=None,
        help="Explicit checkpoint id for an existing progressive task.",
    )
    add_remote_execution_options(parser)
    add_progressive_options(parser)


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
        "--provider",
        dest="provider_name",
        choices=["local-whisper", "native-engine", "paraformer"],
        default=None,
        help=(
            "Transcription provider. Use local-whisper for faster-whisper model names like "
            "`small`, native-engine for a local whisper.cpp ggml .bin model path, or "
            "paraformer for Chinese-first FunASR transcription. Default: local-whisper "
            "(auto-selects paraformer with --preset zh when omitted)."
        ),
    )
    parser.add_argument(
        "-m",
        "--model",
        dest="model_name",
        default="small",
        help=(
            "Model name or path. local-whisper accepts names like `small` or a local path; "
            "native-engine requires a local whisper.cpp ggml .bin file path; paraformer "
            "accepts `paraformer-zh`. Default: small"
        ),
    )
    parser.add_argument(
        "-l",
        "--language",
        default=None,
        help="Optional language code, such as zh or en. Omit for auto-detection.",
    )
    parser.add_argument(
        "--preset",
        choices=["speed", "quality", "zh"],
        default=None,
        help=(
            "Apply a transcription preset. "
            "speed: optimize for fast transcription (beam_size=1, vad_filter=True, int8). "
            "quality: optimize for accuracy (beam_size=5, vad_filter=False). "
            "zh: Chinese-oriented defaults."
        ),
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
    vad_group = parser.add_mutually_exclusive_group()
    vad_group.add_argument(
        "--vad-filter",
        action="store_true",
        help="Enable voice activity detection to reduce silence/noise segments.",
    )
    vad_group.add_argument(
        "--no-vad-filter",
        action="store_true",
        help="Disable voice activity detection, overriding preset defaults.",
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
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Write structured task results as JSON for agent and automation use.",
    )
    parser.add_argument(
        "--events",
        choices=["jsonl"],
        default=None,
        dest="event_stream",
        help="Write structured progress events to stdout as JSONL.",
    )
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Disable human-oriented status output and use automation-safe output only.",
    )
    parser.add_argument(
        "--task-id",
        default=None,
        help="Explicit stable task id for agent workflows.",
    )
    parser.add_argument(
        "--resume-token",
        default=None,
        help="Explicit resume token for an existing progressive task.",
    )
    parser.add_argument(
        "--checkpoint-id",
        default=None,
        help="Explicit checkpoint id for an existing progressive task.",
    )
    add_remote_execution_options(parser)
    add_progressive_options(parser)
    namespace = parser.parse_args(argv)
    return CliOptions(
        command="transcribe",
        inputs=namespace.inputs,
        output_dir=namespace.output_dir,
        work_dir=namespace.work_dir,
        provider_name=namespace.provider_name,
        model_name=namespace.model_name,
        language=namespace.language,
        preset=namespace.preset,
        task=namespace.task,
        beam_size=namespace.beam_size,
        vad_filter=namespace.vad_filter,
        no_vad_filter=namespace.no_vad_filter,
        initial_prompt=namespace.initial_prompt,
        timestamps=namespace.timestamps,
        word_timestamps=namespace.word_timestamps,
        output_formats=parse_output_formats(namespace.output_formats),
        recursive=namespace.recursive,
        overwrite=namespace.overwrite,
        keep_audio=namespace.keep_audio,
        progressive_mode=namespace.progressive_mode,
        progressive_chunk_seconds=namespace.progressive_chunk_seconds,
        progressive_chunk_overlap_seconds=namespace.progressive_chunk_overlap_seconds,
        progressive_resume=namespace.progressive_resume,
        progressive_max_workers=namespace.progressive_max_workers,
        execution_mode=namespace.execution_mode,
        server_target=namespace.server_target,
        remote_token=namespace.remote_token,
        remote_poll_seconds=namespace.remote_poll_seconds,
        download_artifacts=namespace.download_artifacts,
        json_output=namespace.json_output,
        event_stream=namespace.event_stream,
        non_interactive=namespace.non_interactive,
        task_id=namespace.task_id,
        resume_token=namespace.resume_token,
        checkpoint_id=namespace.checkpoint_id,
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
    parser.add_argument(
        "--network-family",
        choices=["auto", "ipv4", "ipv6"],
        default="auto",
        help="Network address family for URL resolution/downloads. Default: auto",
    )
    parser.add_argument(
        "--cookies",
        type=Path,
        default=None,
        help="Explicit Netscape cookies.txt file for login-required media.",
    )
    parser.add_argument(
        "--proxy",
        default=None,
        help="Proxy URL for URL media access, such as http://127.0.0.1:7890.",
    )
    parser.add_argument(
        "--download-quality",
        choices=["best", "high", "medium", "low"],
        default="best",
        help="Download quality preference. Default: best",
    )
    parser.add_argument(
        "--download-format",
        default=None,
        help="Preferred download format (e.g., mp4, webm, mp3, m4a, opus). Default: auto",
    )
    namespace = parser.parse_args(argv)
    return UrlOptions(
        command="url",
        url=namespace.url,
        output_dir=namespace.output_dir,
        work_dir=namespace.work_dir,
        provider_name=namespace.provider_name,
        model_name=namespace.model_name,
        language=namespace.language,
        preset=namespace.preset,
        task=namespace.task,
        beam_size=namespace.beam_size,
        vad_filter=namespace.vad_filter,
        no_vad_filter=namespace.no_vad_filter,
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
        network_family=namespace.network_family,
        cookies=namespace.cookies,
        proxy=namespace.proxy,
        progressive_mode=namespace.progressive_mode,
        progressive_chunk_seconds=namespace.progressive_chunk_seconds,
        progressive_chunk_overlap_seconds=namespace.progressive_chunk_overlap_seconds,
        progressive_resume=namespace.progressive_resume,
        progressive_max_workers=namespace.progressive_max_workers,
        execution_mode=namespace.execution_mode,
        server_target=namespace.server_target,
        remote_token=namespace.remote_token,
        remote_poll_seconds=namespace.remote_poll_seconds,
        download_artifacts=namespace.download_artifacts,
        download_quality=namespace.download_quality,
        download_format=namespace.download_format,
        json_output=namespace.json_output,
        event_stream=namespace.event_stream,
        non_interactive=namespace.non_interactive,
        task_id=namespace.task_id,
        resume_token=namespace.resume_token,
        checkpoint_id=namespace.checkpoint_id,
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
        "--provider",
        choices=["local-whisper", "native-engine", "paraformer"],
        default="local-whisper",
        help="Provider to validate. Default: local-whisper",
    )
    parser.add_argument(
        "-m",
        "--model",
        dest="model_name",
        default="small",
        help=(
            "Model name or path to check. local-whisper accepts names like `small`; "
            "native-engine requires a local whisper.cpp ggml .bin file path; "
            "paraformer accepts `paraformer-zh`. Default: small"
        ),
    )
    parser.add_argument(
        "--hello-smoke",
        action="store_true",
        help="For native-engine, launch the engine and verify a hello round-trip.",
    )
    parser.add_argument(
        "--skip-model-access",
        action="store_true",
        help="Skip remote model reachability checks and validate only local runtime dependencies.",
    )
    namespace = parser.parse_args(argv)
    return DoctorOptions(
        command="doctor",
        output_dir=namespace.output_dir,
        provider_name=namespace.provider,
        model_name=namespace.model_name,
        hello_smoke=namespace.hello_smoke,
        skip_model_access=namespace.skip_model_access,
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


def parse_inspect_args(argv: list[str] | None = None) -> InspectOptions:
    parser = argparse.ArgumentParser(
        prog="flowscribe inspect",
        description="Inspect a local media file or public URL before transcription.",
    )
    parser.add_argument("source", help="Local media path or public http(s) URL.")
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Write inspection result as JSON for GUI or automation use.",
    )
    parser.add_argument(
        "--timeout",
        type=positive_int,
        default=30,
        help="Network/probe timeout in seconds. Default: 30",
    )
    parser.add_argument(
        "--network-family",
        choices=["auto", "ipv4", "ipv6"],
        default="auto",
        help="Network address family for URL inspection. Default: auto",
    )
    parser.add_argument(
        "--cookies",
        type=Path,
        default=None,
        help="Explicit Netscape cookies.txt file for login-required URL inspection.",
    )
    parser.add_argument(
        "--proxy",
        default=None,
        help="Proxy URL for URL inspection, such as http://127.0.0.1:7890.",
    )
    namespace = parser.parse_args(argv)
    return InspectOptions(
        command="inspect",
        source=namespace.source,
        json_output=namespace.json_output,
        timeout_seconds=namespace.timeout,
        network_family=namespace.network_family,
        cookies=namespace.cookies,
        proxy=namespace.proxy,
    )


def parse_serve_args(argv: list[str] | None = None) -> ServeOptions:
    parser = argparse.ArgumentParser(
        prog="flowscribe serve",
        description="Start HTTP server for Bookmarklet integration.",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host address to bind. Default: 127.0.0.1",
    )
    parser.add_argument(
        "--port",
        type=positive_int,
        default=8765,
        help="Port to listen on. Default: 8765",
    )
    parser.add_argument(
        "--queue-store",
        type=Path,
        default=None,
        help="Path to batch-queue.json. Default: {AppData}/FlowScribe/batch-queue.json",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=None,
        help="Default output directory for transcripts. Default: ~/Documents/FlowScribe",
    )
    parser.add_argument(
        "--format",
        dest="output_formats",
        default="json",
        help="Default output formats (comma-separated). Default: json",
    )
    parser.add_argument(
        "-m",
        "--model",
        dest="model_name",
        default="small",
        help="Default transcription model. Default: small",
    )
    parser.add_argument(
        "-l",
        "--language",
        default=None,
        help="Default language code (e.g., zh, en). Default: auto-detect",
    )
    parser.add_argument(
        "--api-token",
        default=None,
        help="Optional bearer token required for /v1 remote task and artifact APIs.",
    )
    namespace = parser.parse_args(argv)

    # Default queue store path
    queue_store_path = namespace.queue_store
    if queue_store_path is None:
        from flowscribe.server.handlers import _get_app_data_dir
        queue_store_path = _get_app_data_dir() / "batch-queue.json"

    # Default output directory
    output_dir = namespace.output_dir
    if output_dir is None:
        output_dir = Path.home() / "Documents" / "FlowScribe"

    # Parse output formats
    output_formats = tuple(
        fmt.strip().lower()
        for fmt in namespace.output_formats.split(",")
        if fmt.strip()
    )

    return ServeOptions(
        command="serve",
        host=namespace.host,
        port=namespace.port,
        queue_store_path=queue_store_path,
        output_dir=output_dir,
        output_formats=output_formats,
        model_name=namespace.model_name,
        language=namespace.language,
        api_token=namespace.api_token,
    )


def parse_remote_args(argv: list[str] | None = None) -> RemoteCommandOptions:
    parser = argparse.ArgumentParser(
        prog="flowscribe remote",
        description="Manage FlowScribe remote server profiles for CLI execution.",
    )
    parser.add_argument("--json", action="store_true", dest="json_output", help="Write JSON output.")
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    add_parser = subparsers.add_parser("add-server", help="Add or update a remote server profile.")
    add_parser.add_argument("name", help="Stable profile name.")
    add_parser.add_argument("--url", required=True, dest="base_url", help="Base URL such as http://127.0.0.1:8765")
    add_parser.add_argument("--token", default=None, help="Optional bearer token.")
    add_parser.add_argument("--disable", action="store_false", dest="enabled", default=True, help="Store the profile as disabled.")
    add_parser.add_argument("--no-verify-tls", action="store_false", dest="verify_tls", default=True, help="Disable TLS certificate verification.")
    add_parser.add_argument("--timeout", type=positive_float, dest="timeout_seconds", default=30.0, help="Default request timeout in seconds. Default: 30")
    artifact_group = add_parser.add_mutually_exclusive_group()
    artifact_group.add_argument("--download-artifacts", action="store_true", dest="download_artifacts_by_default", default=True, help="Download remote artifacts by default.")
    artifact_group.add_argument("--no-download-artifacts", action="store_false", dest="download_artifacts_by_default", default=True, help="Do not download remote artifacts by default.")

    subparsers.add_parser("list-servers", help="List configured remote server profiles.")
    show_parser = subparsers.add_parser("show-server", help="Show one configured remote server profile.")
    show_parser.add_argument("name", help="Profile name.")
    remove_parser = subparsers.add_parser("remove-server", help="Remove a configured remote server profile.")
    remove_parser.add_argument("name", help="Profile name.")

    namespace = parser.parse_args(argv)
    return RemoteCommandOptions(
        command="remote",
        subcommand=namespace.subcommand,
        name=getattr(namespace, "name", None),
        base_url=getattr(namespace, "base_url", None),
        token=getattr(namespace, "token", None),
        enabled=getattr(namespace, "enabled", True),
        verify_tls=getattr(namespace, "verify_tls", True),
        timeout_seconds=getattr(namespace, "timeout_seconds", 30.0),
        download_artifacts_by_default=getattr(namespace, "download_artifacts_by_default", True),
        json_output=namespace.json_output,
    )


def parse_simple_command_args(command: str, argv: list[str]) -> SimpleCommandOptions:
    descriptions = {
        "version": "Show FlowScribe version information.",
        "formats": "List supported local media file extensions.",
        "models": "Show recommended local transcription models.",
        "capture": "Placeholder for future system audio capture.",
        "gui": "Launch the experimental desktop GUI.",
    }
    parser = argparse.ArgumentParser(
        prog=f"flowscribe {command}",
        description=descriptions[command],
    )
    parser.parse_args(argv)
    return SimpleCommandOptions(command=command)


def parse_model_args(argv: list[str] | None = None) -> ModelCommandOptions:
    parser = argparse.ArgumentParser(
        prog="flowscribe model",
        description="Manage installed local transcription models.",
    )
    parser.add_argument(
        "--models-dir",
        type=Path,
        default=None,
        help="Override the models directory used for download and listing.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Write structured model management output as JSON.",
    )
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    subparsers.add_parser("list-available", help="List downloadable and importable model options.")
    subparsers.add_parser("list-installed", help="List installed and imported model entries.")

    download_parser = subparsers.add_parser("download", help="Download a model into the managed models directory.")
    download_parser.add_argument("model_id", help="Model id, such as small or paraformer-zh.")

    remove_parser = subparsers.add_parser("remove", help="Remove an installed model entry.")
    remove_parser.add_argument("model_id", help="Model id to remove.")

    import_parser = subparsers.add_parser(
        "import-native",
        help="Register a local whisper.cpp ggml .bin file for native-engine use.",
    )
    import_parser.add_argument("path", type=Path, help="Path to a local whisper.cpp ggml .bin file.")

    namespace = parser.parse_args(argv)
    return ModelCommandOptions(
        command="model",
        subcommand=namespace.subcommand,
        model_id=getattr(namespace, "model_id", None),
        path=getattr(namespace, "path", None),
        models_dir=namespace.models_dir,
        json_output=namespace.json_output,
    )


def parse_install_args(argv: list[str] | None = None) -> InstallCommandOptions:
    parser = argparse.ArgumentParser(
        prog="flowscribe install",
        description="Installer-facing commands for writing packaged-install configuration.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Write structured installer command output as JSON.",
    )
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    write_config = subparsers.add_parser(
        "write-config",
        help="Write install-config.json for a packaged installation.",
    )
    write_config.add_argument(
        "--scope",
        dest="install_scope",
        choices=["user", "machine"],
        required=True,
        help="Installation scope recorded in install-config.json.",
    )
    write_config.add_argument(
        "--models-dir",
        type=Path,
        required=True,
        help="Managed models directory.",
    )
    write_config.add_argument(
        "--docs-dir",
        type=Path,
        required=True,
        help="Managed docs directory.",
    )
    write_config.add_argument(
        "--component",
        dest="component_names",
        action="append",
        default=[],
        choices=["gui", "cli", "docs"],
        help="Installed component name. Repeat for multiple components.",
    )
    write_config.add_argument(
        "--allow-implicit-model-download",
        action="store_true",
        help="Allow runtime model auto-download for this install. Defaults to disabled.",
    )

    namespace = parser.parse_args(argv)
    return InstallCommandOptions(
        command="install",
        subcommand=namespace.subcommand,
        install_scope=getattr(namespace, "install_scope", None),
        models_dir=getattr(namespace, "models_dir", None),
        docs_dir=getattr(namespace, "docs_dir", None),
        component_names=tuple(getattr(namespace, "component_names", ()) or ()),
        allow_implicit_model_download=bool(
            getattr(namespace, "allow_implicit_model_download", False)
        ),
        json_output=namespace.json_output,
    )
