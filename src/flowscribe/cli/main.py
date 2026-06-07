"""Command-line entry point for FlowScribe."""

from __future__ import annotations

import json
import logging
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from flowscribe.tasks.models import ProgressEvent, SourceSpec, TranscriptionJob
from flowscribe.app.service import TranscriptionService
from flowscribe.cli.args import parse_args
from flowscribe.cli.doctor import run_doctor
from flowscribe import __version__
from flowscribe.core.errors import (
    CancellationError,
    DownloadError,
    FlowScribeError,
    InputError,
    MediaPreparationError,
    OutputError,
    TranscriptionError,
)
from flowscribe.input.file_filter import SUPPORTED_MEDIA_EXTENSIONS
from flowscribe.input.url_inspector import UrlInspector
from flowscribe.input.url_tool_bridge import select_url_inspector_cls
from flowscribe.media.inspector import LocalMediaInspector
from flowscribe.output.time_format import format_timestamp
from flowscribe.search.transcript_search import search_transcript_file
from flowscribe.model_manager import (
    download_model,
    import_native_model,
    list_available_models,
    list_installed_models,
    managed_models_present,
    remove_model,
    write_install_config,
)
from flowscribe.providers.transcribe.native_engine import resolve_engine_exe
from flowscribe.providers.transcribe.paraformer import PARAFORMER_MODEL_NAME
from flowscribe.utils.runtime_logging import configure_runtime_logging

LOGGER = logging.getLogger(__name__)

CLI_PROGRESSIVE_AUTO_THRESHOLD_SECONDS = 20 * 60
EXIT_OK = 0
EXIT_PARTIAL_SUCCESS = 10
EXIT_INPUT_ERROR = 20
EXIT_SOURCE_ERROR = 30
EXIT_ENVIRONMENT_ERROR = 40
EXIT_RUNTIME_ERROR = 50
EXIT_RESUMABLE_INTERRUPT = 60
EXIT_CANCELED = 70


def main(argv: list[str] | None = None) -> int:
    log_path = configure_runtime_logging("FlowScribeCLI")
    if log_path is not None:
        LOGGER.debug("CLI log file: %s", log_path)
    options = parse_args(argv)
    if options.command == "doctor":
        return run_doctor(
            output_dir=options.output_dir,
            provider_name=options.provider_name,
            model_name=options.model_name,
            hello_smoke=options.hello_smoke,
            skip_model_access=options.skip_model_access,
        )
    if options.command == "search":
        return run_search(options)
    if options.command == "inspect":
        return run_inspect(options)
    if options.command == "url":
        return run_url(options)
    if options.command == "serve":
        return run_serve(options)
    if options.command == "model":
        return run_model_command(options)
    if options.command == "install":
        return run_install_command(options)
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
        print("Native engine models:")
        print("- native-engine requires a local whisper.cpp ggml .bin model path")
        print("")
        print("Chinese-first models:")
        print("- paraformer: local FunASR Paraformer provider; model alias paraformer-zh")
        sample_model = Path("models") / "ggml-base.en.bin"
        if sample_model.exists():
            print(f"- example local ggml path: {sample_model.resolve()}")
        try:
            engine_exe = resolve_engine_exe()
            print(f"- engine executable: {engine_exe}")
        except FlowScribeError as exc:
            print(f"- engine executable: not found ({exc})")
        print("")
        print("Examples:")
        print("  flowscribe transcribe video.mp4 --model small --preset speed")
        print("  flowscribe transcribe video.mp4 --model small --preset zh")
        print("  flowscribe transcribe video.mp4 --preset zh")
        print("  flowscribe transcribe video.mp4 --provider paraformer --model paraformer-zh")
        print("  flowscribe transcribe video.mp4 --model medium --language en")
        print("  flowscribe transcribe audio.wav --provider native-engine --model models\\ggml-base.en.bin")
        print("  flowscribe url https://example.com/video --provider native-engine --model D:\\models\\ggml-base.en.bin")
        return 0
    if options.command == "capture":
        print("System audio capture is planned but not implemented yet.")
        print("Future example: flowscribe capture --duration 10m -o outputs")
        return 2
    if options.command == "gui":
        from flowscribe.gui.qt_app import run_gui

        return run_gui()

    return run_transcribe(options)


def run_install_command(options) -> int:
    if options.subcommand != "write-config":
        print(f"Unsupported install subcommand: {options.subcommand}", file=sys.stderr)
        return 2

    try:
        config_path = write_install_config(
            install_scope=options.install_scope or "user",
            models_dir=options.models_dir,
            docs_dir=options.docs_dir,
            component_names=options.component_names,
            allow_implicit_model_download_value=options.allow_implicit_model_download,
        )
    except FlowScribeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    payload = {
        "ok": True,
        "config_path": str(config_path),
        "install_scope": options.install_scope or "user",
        "models_dir": str(options.models_dir) if options.models_dir is not None else None,
        "docs_dir": str(options.docs_dir) if options.docs_dir is not None else None,
        "installed_components": list(options.component_names),
        "allow_implicit_model_download": options.allow_implicit_model_download,
        "managed_models_present": managed_models_present(),
    }
    if options.json_output:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"Wrote install config: {config_path}")
    return 0


def run_model_command(options) -> int:
    if options.subcommand == "list-available":
        entries = list_available_models()
        if options.json_output:
            print(
                json.dumps(
                    [
                        {
                            "model_id": entry.model_id,
                            "provider_name": entry.provider_name,
                            "display_name": entry.display_name,
                            "description": entry.description,
                            "recommended": entry.recommended,
                            "approx_size_mb": entry.approx_size_mb,
                        }
                        for entry in entries
                    ],
                    ensure_ascii=False,
                    indent=2,
                )
            )
        else:
            print("Available models:")
            for entry in entries:
                badge = " [recommended]" if entry.recommended else ""
                size = f" ({entry.approx_size_mb} MB)" if entry.approx_size_mb is not None else ""
                print(f"- {entry.model_id}{badge}{size}: {entry.description}")
        return 0

    if options.subcommand == "list-installed":
        entries = list_installed_models()
        if options.json_output:
            print(
                json.dumps(
                    [
                        {
                            "model_id": entry.model_id,
                            "provider_name": entry.provider_name,
                            "display_name": entry.display_name,
                            "status": entry.status,
                            "path": str(entry.path) if entry.path is not None else None,
                            "imported": entry.imported,
                            "recommended": entry.recommended,
                            "description": entry.description,
                            "approx_size_mb": entry.approx_size_mb,
                        }
                        for entry in entries
                    ],
                    ensure_ascii=False,
                    indent=2,
                )
            )
        else:
            if not entries:
                print("No models are currently installed.")
            else:
                print("Installed models:")
                for entry in entries:
                    suffix = " (imported)" if entry.imported else ""
                    print(f"- {entry.model_id}{suffix}: {entry.path or 'managed path unavailable'}")
        return 0

    if options.subcommand == "download":
        messages: list[str] = []
        try:
            entry = download_model(
                options.model_id,
                models_dir=options.models_dir,
                progress=messages.append,
            )
        except FlowScribeError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2
        if options.json_output:
            print(
                json.dumps(
                    {
                        "ok": True,
                        "messages": messages,
                        "model": {
                            "model_id": entry.model_id,
                            "provider_name": entry.provider_name,
                            "display_name": entry.display_name,
                            "status": entry.status,
                            "path": str(entry.path) if entry.path is not None else None,
                        },
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
        else:
            for message in messages:
                print(message)
            print(f"Installed model: {entry.model_id}")
        return 0

    if options.subcommand == "remove":
        removed = remove_model(options.model_id)
        if options.json_output:
            print(json.dumps({"ok": removed, "model_id": options.model_id}, ensure_ascii=False, indent=2))
        else:
            if removed:
                print(f"Removed model: {options.model_id}")
            else:
                print(f"Model not found: {options.model_id}", file=sys.stderr)
        return 0 if removed else 1

    if options.subcommand == "import-native":
        try:
            entry = import_native_model(options.path)
        except FlowScribeError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2
        if options.json_output:
            print(
                json.dumps(
                    {
                        "ok": True,
                        "model": {
                            "model_id": entry.model_id,
                            "provider_name": entry.provider_name,
                            "display_name": entry.display_name,
                            "status": entry.status,
                            "path": str(entry.path) if entry.path is not None else None,
                            "imported": entry.imported,
                        },
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
        else:
            print(f"Imported native model: {entry.path}")
        return 0

    print(f"Unsupported model subcommand: {options.subcommand}", file=sys.stderr)
    return 2


def run_transcribe(options) -> int:
    job = _job_from_transcribe_options(options)
    result = TranscriptionService().run(job, progress=_build_cli_progress_handler(options))

    if options.json_output:
        print(json.dumps(_result_payload(result), ensure_ascii=False, indent=2))
    elif not options.non_interactive:
        elapsed = result.elapsed_seconds
        elapsed_str = f" Time: {_format_duration(elapsed)}." if elapsed is not None else ""
        print(f"Done. Succeeded: {result.succeeded}. Failed: {result.failed}.{elapsed_str}")
        if result.errors:
            print("Failures:")
            for error in result.errors:
                print(f"- {error.source}: {error.message}")
    return _exit_code_for_result(result)


def run_url(options) -> int:
    job = _job_from_url_options(options)
    result = TranscriptionService().run(job, progress=_build_cli_progress_handler(options))
    if options.json_output:
        print(json.dumps(_result_payload(result), ensure_ascii=False, indent=2))
    elif not options.non_interactive:
        if result.errors:
            for error in result.errors:
                print(f"Error: {error.message}", file=sys.stderr)
        _print_url_strategy_summary(result)
        elapsed = result.elapsed_seconds
        elapsed_str = f" Time: {_format_duration(elapsed)}." if elapsed is not None else ""
        print(f"Done. Succeeded: {result.succeeded}. Failed: {result.failed}.{elapsed_str}")
    return _exit_code_for_result(result)


def run_serve(options) -> int:
    """Start HTTP server for Bookmarklet integration."""
    from flowscribe.server import BookmarkletServer
    from flowscribe.server.agent_api import agent_task_store_path_for

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(message)s",
        datefmt="%H:%M:%S",
    )
    task_store_path = agent_task_store_path_for(options.queue_store_path)

    print("=" * 70)
    print("FlowScribe Server")
    print("=" * 70)
    print(f"Listening on: http://{options.host}:{options.port}")
    print(f"Queue store:  {options.queue_store_path}")
    print(f"Task store:   {task_store_path}")
    print("")
    print("Default Settings:")
    print(f"  Output dir:  {options.output_dir}")
    print(f"  Formats:     {', '.join(options.output_formats)}")
    print(f"  Model:       {options.model_name}")
    print(f"  Language:    {options.language or 'auto-detect'}")
    print("")
    print("Bookmarklet Endpoints:")
    print(f"  POST http://{options.host}:{options.port}/add-url     - Add single URL to queue")
    print(f"  POST http://{options.host}:{options.port}/add-urls    - Add multiple URLs to queue")
    print(f"  GET  http://{options.host}:{options.port}/status      - Get queue status")
    print(f"  GET  http://{options.host}:{options.port}/bookmarklet.js - Get bookmarklet script")
    print("")
    print("Agent Task API:")
    print(f"  POST http://{options.host}:{options.port}/v1/tasks                  - Submit single task")
    print(f"  GET  http://{options.host}:{options.port}/v1/tasks/{{task_id}}      - Get task status")
    print(f"  GET  http://{options.host}:{options.port}/v1/tasks/{{task_id}}/events - Stream task events")
    print(f"  GET  http://{options.host}:{options.port}/v1/tasks/{{task_id}}/result - Get final result")
    print("")
    print("Task Persistence:")
    print("  Agent task history is stored in agent-tasks.json next to the queue store.")
    print("  Completed, failed, and canceled tasks remain queryable after server restart.")
    print("  Accepted or running tasks interrupted by restart are recovered as failed.")
    print("")
    print("Status reports will be shown every 30 seconds")
    print("Press Ctrl+C to stop")
    print("=" * 70)
    print("")

    try:
        server = BookmarkletServer(
            queue_store_path=options.queue_store_path,
            host=options.host,
            port=options.port,
            status_interval=30,
            default_output_dir=options.output_dir,
            default_output_formats=options.output_formats,
            default_model_name=options.model_name,
            default_language=options.language,
        )
        server.start()
        return 0
    except KeyboardInterrupt:
        print("\n✓ Server stopped")
        return 0
    except OSError as e:
        if _is_address_in_use_error(e):
            print(f"\n❌ Error: Port {options.port} is already in use", file=sys.stderr)
            print(f"   Try a different port: flowscribe serve --port {options.port + 1}", file=sys.stderr)
        else:
            print(f"\n❌ Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}", file=sys.stderr)
        return 2


def run_inspect(options) -> int:
    try:
        if _is_http_url(options.source):
            inspection = select_url_inspector_cls(UrlInspector)(
                timeout_seconds=options.timeout_seconds,
                network_family=options.network_family,
                cookies_path=options.cookies,
                proxy=options.proxy,
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
    progressive_enabled, progressive_note = _resolve_cli_progressive_mode_for_transcribe(options)
    if progressive_note and not options.non_interactive and not options.json_output:
        print(progressive_note)
    provider_name, model_name = _resolve_cli_provider_and_model(options)
    return TranscriptionJob(
        sources=tuple(
            SourceSpec(kind="local", value=str(input_path), recursive=options.recursive)
            for input_path in options.inputs
        ),
        task_id=options.task_id,
        output_dir=options.output_dir,
        work_dir=options.work_dir,
        provider_name=provider_name,
        model_name=model_name,
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
        progressive_enabled=progressive_enabled,
        progressive_resume=options.progressive_resume,
        progressive_chunk_seconds=options.progressive_chunk_seconds,
        progressive_chunk_overlap_seconds=options.progressive_chunk_overlap_seconds,
        progressive_max_workers=options.progressive_max_workers,
        resume_token=options.resume_token,
        checkpoint_id=options.checkpoint_id,
    )


def _job_from_url_options(options) -> TranscriptionJob:
    from flowscribe.tasks.models import DownloadOptions

    progressive_enabled, progressive_note = _resolve_cli_progressive_mode_for_url(options)
    if progressive_note and not options.non_interactive and not options.json_output:
        print(progressive_note)

    download_opts = DownloadOptions(
        quality=options.download_quality,
        prefer_format=options.download_format,
    )
    provider_name, model_name = _resolve_cli_provider_and_model(options)

    source = SourceSpec(
        kind="url",
        value=options.url,
        keep_media=options.keep_media,
        url_media_kind="video" if options.keep_media else "audio",
        download_options=download_opts,
    )

    return TranscriptionJob(
        sources=(source,),
        task_id=options.task_id,
        output_dir=options.output_dir,
        work_dir=options.work_dir,
        provider_name=provider_name,
        model_name=model_name,
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
        proxy=options.proxy,
        progressive_enabled=progressive_enabled,
        progressive_resume=options.progressive_resume,
        progressive_chunk_seconds=options.progressive_chunk_seconds,
        progressive_chunk_overlap_seconds=options.progressive_chunk_overlap_seconds,
        progressive_max_workers=options.progressive_max_workers,
        requested_capabilities=("subtitle", "transcribe"),
        resume_token=options.resume_token,
        checkpoint_id=options.checkpoint_id,
    )


def _resolve_cli_provider_and_model(options) -> tuple[str, str]:
    provider_name = options.provider_name
    model_name = options.model_name
    if provider_name is None:
        provider_name = "paraformer" if options.preset == "zh" else "local-whisper"
    if provider_name == "paraformer" and model_name == "small":
        model_name = PARAFORMER_MODEL_NAME
    return provider_name, model_name


def _print_cli_progress(event: ProgressEvent) -> None:
    if event.stage == "complete":
        return
    if event.stage == "error":
        return
    if event.stage == "discover" and event.source is None:
        return
    line = _cli_progress_line(event)
    if line:
        print(line)


def _build_cli_progress_handler(options):
    def handle(event: ProgressEvent) -> None:
        if options.event_stream == "jsonl":
            print(json.dumps(_event_payload(event), ensure_ascii=False), flush=True)
            return
        if not options.non_interactive and not options.json_output:
            _print_cli_progress(event)

    return handle


def _cli_progress_line(event: ProgressEvent) -> str:
    if event.capability == "subtitle" and event.message:
        return event.message
    if event.processed_duration_seconds is not None:
        parts = [event.message]
        if event.total_duration_seconds is not None:
            parts.append(
                f"Progress {format_timestamp(event.processed_duration_seconds)} / "
                f"{format_timestamp(event.total_duration_seconds)}"
            )
        if event.chunk_index is not None and event.chunk_count is not None:
            parts.append(f"Chunk {event.chunk_index}/{event.chunk_count}")
        if event.realtime_factor is not None:
            parts.append(f"Speed {event.realtime_factor:.1f}x")
        if event.eta_seconds is not None:
            parts.append(f"ETA {format_timestamp(event.eta_seconds)}")
        if event.resumed:
            parts.append("resumed")
        return " | ".join(parts)
    return event.message


def _event_payload(event: ProgressEvent) -> dict:
    return {
        "event_type": event.event_type or "progress",
        "timestamp": event.timestamp or datetime.utcnow().isoformat(timespec="milliseconds") + "Z",
        "sequence": event.sequence,
        "task_id": event.task_id,
        "stage": event.stage,
        "message": event.message,
        "source": event.source,
        "current": event.current,
        "total": event.total,
        "path": str(event.path) if event.path is not None else None,
        "processed_duration_seconds": event.processed_duration_seconds,
        "total_duration_seconds": event.total_duration_seconds,
        "eta_seconds": event.eta_seconds,
        "realtime_factor": event.realtime_factor,
        "chunk_index": event.chunk_index,
        "chunk_count": event.chunk_count,
        "completed_chunks": event.completed_chunks,
        "failed_chunks": event.failed_chunks,
        "resumed": event.resumed,
        "capability": event.capability,
        "percent": event.percent,
        "raw_metadata": dict(event.raw_metadata),
    }


def _result_payload(result) -> dict:
    return {
        "ok": result.ok,
        "canceled": result.canceled,
        "succeeded": result.succeeded,
        "failed": result.failed,
        "elapsed_seconds": result.elapsed_seconds,
        "tasks": [
            {
                "task_id": spec.task_id,
                "resume_token": spec.resume_token,
                "checkpoint_id": spec.checkpoint_id,
                "cache_key": spec.cache_key,
                "source": {
                    "kind": spec.source.kind,
                    "value": spec.source.value,
                    "locator": spec.source.resolved_locator,
                },
            }
            for spec in result.task_specs
        ],
        "outputs": [
            {
                "paths": [str(path) for path in output.paths],
                "json_path": str(output.json_path) if output.json_path is not None else None,
                "media_path": str(output.media_path) if output.media_path is not None else None,
                "media_kind": output.media_kind,
                "requested_media_kind": output.requested_media_kind,
                "source_kind": output.source_kind,
                "source_value": output.source_value,
                "transcription_strategy": output.transcription_strategy,
                "subtitle_language": output.subtitle_language,
            }
            for output in result.outputs
        ],
        "errors": [
            {
                "code": error.code,
                "message": error.message,
                "source": error.source,
                "recoverable": error.recoverable,
            }
            for error in result.errors
        ],
    }


def _exit_code_for_result(result) -> int:
    if result.canceled:
        return EXIT_CANCELED
    if result.errors and result.outputs:
        return EXIT_PARTIAL_SUCCESS
    if result.errors:
        return _exit_code_for_error(result.errors[0].code)
    return EXIT_OK


def _exit_code_for_error(code: str | None) -> int:
    mapping = {
        InputError.__name__: EXIT_INPUT_ERROR,
        DownloadError.__name__: EXIT_SOURCE_ERROR,
        MediaPreparationError.__name__: EXIT_SOURCE_ERROR,
        OutputError.__name__: EXIT_ENVIRONMENT_ERROR,
        TranscriptionError.__name__: EXIT_RUNTIME_ERROR,
        CancellationError.__name__: EXIT_CANCELED,
    }
    if code is None:
        return EXIT_RUNTIME_ERROR
    return mapping.get(code, EXIT_RUNTIME_ERROR)


def _print_url_strategy_summary(result) -> None:
    if not result.outputs:
        return
    for output in result.outputs:
        if output.source_kind != "url":
            continue
        strategy = output.transcription_strategy
        if strategy == "native-subtitles":
            language = output.subtitle_language or "unknown"
            print(f"Strategy: used native YouTube subtitles ({language}).")
        elif strategy == "automatic-subtitles":
            language = output.subtitle_language or "unknown"
            print(f"Strategy: used automatic YouTube captions ({language}).")
        elif strategy == "audio-transcription":
            print("Strategy: fell back to audio transcription.")


def _resolve_cli_progressive_mode_for_transcribe(options) -> tuple[bool, str | None]:
    if options.progressive_mode == "enabled":
        return True, "Progressive transcription enabled by CLI flag."
    if options.progressive_mode == "disabled":
        return False, "Using classic one-shot transcription by CLI flag."
    if options.recursive or len(options.inputs) != 1:
        return False, "Using classic one-shot transcription for batch/local multi-source CLI runs."

    input_path = options.inputs[0]
    if not input_path.is_file():
        return False, None
    try:
        inspection = LocalMediaInspector(timeout_seconds=10).inspect(input_path)
    except FlowScribeError:
        return False, None
    if inspection.duration_seconds is not None and inspection.duration_seconds >= CLI_PROGRESSIVE_AUTO_THRESHOLD_SECONDS:
        return True, (
            "Auto-enabled progressive transcription for long local media "
            f"({format_timestamp(inspection.duration_seconds)} >= "
            f"{format_timestamp(CLI_PROGRESSIVE_AUTO_THRESHOLD_SECONDS)})."
        )
    return False, None


def _resolve_cli_progressive_mode_for_url(options) -> tuple[bool, str | None]:
    if options.progressive_mode == "enabled":
        return True, "Progressive transcription enabled by CLI flag."
    if options.progressive_mode == "disabled":
        return False, "Using classic one-shot transcription by CLI flag."
    try:
        inspection = select_url_inspector_cls(UrlInspector)(
            timeout_seconds=min(15, options.download_timeout_seconds),
            network_family=options.network_family,
            cookies_path=options.cookies,
            proxy=options.proxy,
        ).inspect(options.url)
    except FlowScribeError:
        return False, None
    if (
        inspection.duration_seconds is not None
        and inspection.duration_seconds >= CLI_PROGRESSIVE_AUTO_THRESHOLD_SECONDS
    ):
        return True, (
            "Auto-enabled progressive transcription for long URL media "
            f"({format_timestamp(inspection.duration_seconds)} >= "
            f"{format_timestamp(CLI_PROGRESSIVE_AUTO_THRESHOLD_SECONDS)})."
        )
    return False, None


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


def _format_duration(seconds: float | None) -> str:
    """Format elapsed time in human-readable form (e.g., '2m 34s', '1h 5m 23s')."""
    if seconds is None:
        return "unknown"
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s"
    minutes = seconds // 60
    secs = seconds % 60
    if minutes < 60:
        return f"{minutes}m {secs}s"
    hours = minutes // 60
    mins = minutes % 60
    return f"{hours}h {mins}m {secs}s"


def _is_address_in_use_error(exc: OSError) -> bool:
    if exc.errno in {98, 10048}:
        return True
    if getattr(exc, "winerror", None) == 10048:
        return True
    return "address already in use" in str(exc).lower()

if __name__ == "__main__":
    raise SystemExit(main())
