"""Shared CLI-oriented payload helpers for automation and remote APIs."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from flowscribe.tasks.models import ProgressEvent


def event_payload(event: ProgressEvent) -> dict:
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


def result_payload(result) -> dict:
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
            _output_payload(result, index, output)
            for index, output in enumerate(result.outputs)
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


def _output_payload(result, index: int, output) -> dict:
    source = result.job.sources[index] if index < len(result.job.sources) else None
    source_kind = output.source_kind or (source.kind if source is not None else None)
    source_locator = output.source_locator or (source.resolved_locator if source is not None else None)
    source_value = output.source_value or _source_value_from_job_source(source)
    return {
        "paths": [str(path) for path in output.paths],
        "json_path": str(output.json_path) if output.json_path is not None else None,
        "media_path": str(output.media_path) if output.media_path is not None else None,
        "media_kind": output.media_kind,
        "requested_media_kind": output.requested_media_kind,
        "source_kind": source_kind,
        "source_value": source_value,
        "source_locator": source_locator,
        "original_filename": output.original_filename or _original_filename(source_kind, source_locator or source_value),
        "transcription_strategy": output.transcription_strategy,
        "subtitle_language": output.subtitle_language,
    }


def _source_value_from_job_source(source) -> str | None:
    if source is None:
        return None
    if source.kind == "local" and source.locator:
        return source.locator
    return source.value


def _original_filename(source_kind: str | None, value: str | None) -> str | None:
    if not value:
        return None
    path = Path(value)
    if path.name:
        return path.name
    return value if source_kind == "url" else None
