"""Standalone URL inspection and download CLI."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from flowscribe import __version__
from flowscribe.core.errors import FlowScribeError
from flowscribe.input.url_downloader import DownloadOptions, UrlAudioDownloader
from flowscribe.input.url_inspector import UrlInspector

EXIT_OK = 0
EXIT_INPUT_ERROR = 20
EXIT_SOURCE_ERROR = 30
EXIT_RUNTIME_ERROR = 50


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="flowscribe-url",
        description="Inspect or download URL media without running transcription.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser(
        "inspect",
        help="Inspect a public URL and show the planned acquisition strategy.",
    )
    inspect_parser.add_argument("url", help="Public http(s) audio/video URL or supported media page URL.")
    inspect_parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Write inspection result as JSON.",
    )
    inspect_parser.add_argument(
        "--timeout",
        type=_positive_int,
        default=30,
        help="Network timeout in seconds. Default: 30",
    )
    inspect_parser.add_argument(
        "--network-family",
        choices=["auto", "ipv4", "ipv6"],
        default="auto",
        help="Network address family for URL inspection. Default: auto",
    )
    inspect_parser.add_argument(
        "--cookies",
        type=Path,
        default=None,
        help="Explicit Netscape cookies.txt file for login-required URL inspection.",
    )
    inspect_parser.add_argument(
        "--proxy",
        default=None,
        help="Proxy URL for URL inspection, such as http://127.0.0.1:7890.",
    )

    download_parser = subparsers.add_parser(
        "download",
        help="Download or extract URL media to a local folder.",
    )
    download_parser.add_argument("url", help="Public http(s) audio/video URL or supported media page URL.")
    download_parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=Path("outputs") / "url-downloads",
        help="Directory for saved media. Default: outputs/url-downloads",
    )
    download_parser.add_argument(
        "--work-dir",
        type=Path,
        default=None,
        help="Temporary working directory. Default: <output-dir>/.flowscribe-url-work",
    )
    download_parser.add_argument(
        "--media-kind",
        choices=["audio", "video"],
        default="audio",
        help="Preferred saved media kind. Default: audio",
    )
    download_parser.add_argument(
        "--quality",
        choices=["best", "high", "medium", "low"],
        default="best",
        help="Download quality preference. Default: best",
    )
    download_parser.add_argument(
        "--format",
        dest="prefer_format",
        default=None,
        help="Preferred download format such as mp4, webm, mp3, m4a, or opus.",
    )
    download_parser.add_argument(
        "--max-download-mb",
        type=_positive_int,
        default=2048,
        help="Maximum downloaded media size in MB. Default: 2048",
    )
    download_parser.add_argument(
        "--max-duration",
        type=_positive_float,
        default=4 * 60 * 60,
        help="Maximum remote media duration in seconds. Default: 14400",
    )
    download_parser.add_argument(
        "--timeout",
        type=_positive_int,
        default=30,
        help="Download/network timeout in seconds. Default: 30",
    )
    download_parser.add_argument(
        "--network-family",
        choices=["auto", "ipv4", "ipv6"],
        default="auto",
        help="Network address family for URL download. Default: auto",
    )
    download_parser.add_argument(
        "--cookies",
        type=Path,
        default=None,
        help="Explicit Netscape cookies.txt file for login-required URL download.",
    )
    download_parser.add_argument(
        "--proxy",
        default=None,
        help="Proxy URL for URL download, such as http://127.0.0.1:7890.",
    )
    download_parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Write download result as JSON.",
    )
    download_parser.add_argument(
        "--jsonl-progress",
        action="store_true",
        dest="jsonl_progress",
        help=argparse.SUPPRESS,
    )

    version_parser = subparsers.add_parser("version", help="Show FlowScribe URL tool version.")
    version_parser.add_argument("--json", action="store_true", dest="json_output", help=argparse.SUPPRESS)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    options = parser.parse_args(argv)
    try:
        if options.command == "inspect":
            return run_inspect(options)
        if options.command == "download":
            return run_download(options)
        if options.command == "version":
            payload = {"tool": "FlowScribeURL", "version": __version__}
            if options.json_output:
                print(json.dumps(payload, ensure_ascii=False, indent=2))
            else:
                print(f"FlowScribeURL {__version__}")
            return EXIT_OK
    except FlowScribeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return _exit_code_for_error(exc)
    except Exception as exc:  # pragma: no cover - safety net for packaged builds
        print(f"Unexpected error: {exc}", file=sys.stderr)
        return EXIT_RUNTIME_ERROR
    parser.error(f"Unsupported command: {options.command}")
    return 2


def run_inspect(options) -> int:
    inspection = UrlInspector(
        timeout_seconds=options.timeout,
        network_family=options.network_family,
        cookies_path=options.cookies,
        proxy=options.proxy,
    ).inspect(options.url)
    payload = {"type": "url", **asdict(inspection)}
    if options.json_output:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        _print_inspection(payload)
    return EXIT_OK


def run_download(options) -> int:
    output_dir = options.output_dir.expanduser().resolve()
    work_dir = options.work_dir.expanduser().resolve() if options.work_dir else output_dir / ".flowscribe-url-work"
    work_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    downloader = UrlAudioDownloader(
        download_dir=work_dir,
        max_bytes=options.max_download_mb * 1024 * 1024,
        max_duration_seconds=options.max_duration,
        timeout_seconds=options.timeout,
        network_family=options.network_family,
        cookies_path=options.cookies,
        proxy=options.proxy,
        progress_callback=(lambda message: _emit_progress_payload(message)) if options.jsonl_progress else None,
    )
    result = downloader.download_audio(
        options.url,
        saved_media_kind=options.media_kind,
        download_options=DownloadOptions(
            media_kind=options.media_kind,
            quality=options.quality,
            prefer_format=options.prefer_format,
        ),
    )
    saved_path = _preserve_download(result, output_dir=output_dir)
    bindable_path = None
    if result.saved_media_path is not None and result.saved_media_path.exists():
        bindable_path = saved_path if result.saved_media_path == result.path else _preserve_saved_media(
            result,
            output_dir=output_dir,
            preferred_path=saved_path,
        )

    payload = {
        "ok": True,
        "source": options.url,
        "output_dir": str(output_dir),
        "downloaded_audio_path": str(saved_path),
        "saved_media_path": str(bindable_path) if bindable_path is not None else None,
        "saved_media_kind": result.saved_media_kind,
        "cleanup_dir": str(saved_path.parent),
    }
    if options.json_output:
        print(
            json.dumps(payload, ensure_ascii=False, indent=None if options.jsonl_progress else 2),
            flush=options.jsonl_progress,
        )
    else:
        print(f"Saved audio: {saved_path}")
        if bindable_path is not None and bindable_path != saved_path:
            print(f"Saved media: {bindable_path}")
        print(f"Media kind: {result.saved_media_kind}")
    return EXIT_OK


def _emit_progress_payload(message: str) -> None:
    print(
        json.dumps(
            {
                "type": "progress",
                "message": message,
            },
            ensure_ascii=False,
        ),
        flush=True,
    )


def _preserve_download(result, *, output_dir: Path) -> Path:
    source = result.path
    target_dir = output_dir / result.cleanup_dir.name
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = _available_target_path(target_dir / source.name)
    source.replace(target_path)
    return target_path


def _preserve_saved_media(result, *, output_dir: Path, preferred_path: Path) -> Path:
    source = result.saved_media_path
    if source is None:
        return preferred_path
    if not source.exists():
        return preferred_path
    if source == result.path:
        return preferred_path
    target_dir = output_dir / result.cleanup_dir.name
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = _available_target_path(target_dir / source.name)
    source.replace(target_path)
    return target_path


def _print_inspection(payload: dict) -> None:
    print("FlowScribeURL inspect")
    print("====================")
    print(f"Source: {payload['source']}")
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


def _exit_code_for_error(exc: FlowScribeError) -> int:
    from flowscribe.core.errors import DownloadError, InputError

    if isinstance(exc, InputError):
        return EXIT_INPUT_ERROR
    if isinstance(exc, DownloadError):
        return EXIT_SOURCE_ERROR
    return EXIT_RUNTIME_ERROR


def _available_target_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    counter = 2
    while True:
        candidate = path.with_name(f"{stem}-{counter}{suffix}")
        if not candidate.exists():
            return candidate
        counter += 1


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be greater than 0")
    return parsed


def _positive_float(value: str) -> float:
    parsed = float(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be greater than 0")
    return parsed


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"


def _format_optional_duration(value: float | None) -> str:
    if value is None:
        return "unknown"
    hours = int(value) // 3600
    minutes = (int(value) % 3600) // 60
    seconds = int(value) % 60
    if hours:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


def _format_size(value: int | None) -> str:
    if value is None:
        return "unknown"
    if value < 1024:
        return f"{value} B"
    if value < 1024 * 1024:
        return f"{value / 1024:.1f} KiB"
    return f"{value / (1024 * 1024):.1f} MiB"
