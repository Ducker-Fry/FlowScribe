"""Shared payload helpers for remote-direct task submission."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from flowscribe.tasks.models import DownloadOptions, SourceSpec, TranscriptionJob


def task_job_from_payload(
    payload: dict[str, Any],
    *,
    blob_resolver=None,
) -> TranscriptionJob:
    source_payload = payload.get("source")
    if not isinstance(source_payload, dict):
        raise ValueError("source must be an object")
    source_kind = str(source_payload.get("kind") or "").strip()
    source_value = str(source_payload.get("value") or "").strip()
    if source_kind not in {"local", "url", "remote_blob"}:
        raise ValueError("source.kind must be local, url, or remote_blob")
    if not source_value:
        raise ValueError("source.value is required")
    output_payload = payload.get("output", {})
    if not isinstance(output_payload, dict):
        raise ValueError("output must be an object")
    output_dir = Path(output_payload.get("output_dir") or "outputs")
    output_formats = tuple(output_payload.get("formats") or ("json",))
    if not output_formats:
        output_formats = ("json",)

    source = _source_from_payload(source_payload, blob_resolver=blob_resolver)
    return TranscriptionJob(
        sources=(source,),
        task_id=payload.get("task_id"),
        output_dir=output_dir,
        output_formats=output_formats,
        provider_name=payload.get("provider_name") or "local-whisper",
        model_name=payload.get("model_name") or "small",
        language=payload.get("language"),
        preset=payload.get("preset"),
        timestamps=bool(payload.get("timestamps", True)),
        word_timestamps=bool(payload.get("word_timestamps", False)),
        overwrite=bool(output_payload.get("overwrite", False)),
        progressive_enabled=bool(payload.get("progressive", False)),
        progressive_resume=bool(payload.get("progressive_resume", False)),
        progressive_chunk_seconds=float(payload.get("progressive_chunk_seconds", 30.0)),
        progressive_chunk_overlap_seconds=float(payload.get("progressive_chunk_overlap_seconds", 3.0)),
        progressive_max_workers=int(payload.get("progressive_max_workers", 1)),
        resume_token=payload.get("resume_token"),
        checkpoint_id=payload.get("checkpoint_id"),
        requested_capabilities=("subtitle", "transcribe") if source.kind == "url" else ("transcribe",),
    )


def job_to_payload(
    job: TranscriptionJob,
    *,
    source_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    source = job.sources[0]
    if source_payload is None:
        source_payload = {
            "kind": source.kind,
            "value": source.value,
        }
        if source.locator:
            source_payload["locator"] = source.locator
        if source.metadata:
            source_payload["metadata"] = dict(source.metadata)
    return {
        "task_id": job.task_id,
        "source": source_payload,
        "output": {
            "output_dir": str(job.output_dir),
            "formats": list(job.output_formats),
            "overwrite": job.overwrite,
        },
        "provider_name": job.provider_name,
        "model_name": job.model_name,
        "language": job.language,
        "preset": job.preset,
        "timestamps": job.timestamps,
        "word_timestamps": job.word_timestamps,
        "progressive": job.progressive_enabled,
        "progressive_resume": job.progressive_resume,
        "progressive_chunk_seconds": job.progressive_chunk_seconds,
        "progressive_chunk_overlap_seconds": job.progressive_chunk_overlap_seconds,
        "progressive_max_workers": job.progressive_max_workers,
        "resume_token": job.resume_token,
        "checkpoint_id": job.checkpoint_id,
    }


def _source_from_payload(source_payload: dict[str, Any], *, blob_resolver=None) -> SourceSpec:
    source_kind = str(source_payload.get("kind") or "").strip()
    source_value = str(source_payload.get("value") or "").strip()
    locator = source_payload.get("locator")
    metadata = source_payload.get("metadata")
    metadata = metadata if isinstance(metadata, dict) else {}
    if source_kind == "remote_blob":
        if blob_resolver is None:
            raise ValueError("remote_blob source requires a blob resolver")
        resolved = blob_resolver(source_value)
        if resolved is None:
            raise ValueError(f"remote blob not found: {source_value}")
        return SourceSpec(
            kind="local",
            value=str(resolved),
            locator=str(locator or source_value),
            metadata={"remote_blob_id": source_value, **metadata},
        )
    if source_kind == "url":
        download_payload = source_payload.get("download_options")
        download_options = None
        if isinstance(download_payload, dict):
            download_options = DownloadOptions(
                quality=str(download_payload.get("quality") or "best"),
                prefer_format=download_payload.get("prefer_format"),
            )
        return SourceSpec(
            kind="url",
            value=source_value,
            locator=str(locator) if isinstance(locator, str) and locator else None,
            keep_media=bool(source_payload.get("keep_media", False)),
            url_media_kind=str(source_payload.get("url_media_kind") or "audio"),
            download_options=download_options,
            metadata=metadata,
        )
    return SourceSpec(
        kind="local",
        value=source_value,
        locator=str(locator) if isinstance(locator, str) and locator else None,
        recursive=bool(source_payload.get("recursive", False)),
        metadata=metadata,
    )
