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
    cookies_path = _cookies_path_from_payload(payload, blob_resolver=blob_resolver)
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
        max_download_mb=int(payload.get("max_download_mb", 2048)),
        max_duration_seconds=float(payload.get("max_duration_seconds", 4 * 60 * 60)),
        download_timeout_seconds=int(payload.get("download_timeout_seconds", 30)),
        network_family=str(payload.get("network_family") or "auto"),
        cookies_path=cookies_path,
        proxy=payload.get("proxy"),
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
    cookies_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    source = job.sources[0]
    if source_payload is None:
        source_payload = _source_to_payload(source)
    payload = {
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
        "max_download_mb": job.max_download_mb,
        "max_duration_seconds": job.max_duration_seconds,
        "download_timeout_seconds": job.download_timeout_seconds,
        "network_family": job.network_family,
        "proxy": job.proxy,
        "progressive": job.progressive_enabled,
        "progressive_resume": job.progressive_resume,
        "progressive_chunk_seconds": job.progressive_chunk_seconds,
        "progressive_chunk_overlap_seconds": job.progressive_chunk_overlap_seconds,
        "progressive_max_workers": job.progressive_max_workers,
        "resume_token": job.resume_token,
        "checkpoint_id": job.checkpoint_id,
    }
    cookies = cookies_payload or _cookies_to_payload(job.cookies_path)
    if cookies is not None:
        payload["cookies"] = cookies
    return payload


def _source_to_payload(source: SourceSpec) -> dict[str, Any]:
    payload = {
        "kind": source.kind,
        "value": source.value,
    }
    if source.kind == "url":
        payload["keep_media"] = source.keep_media
        payload["url_media_kind"] = source.url_media_kind
        if source.download_options is not None:
            payload["download_options"] = {
                "quality": source.download_options.quality,
                "prefer_format": source.download_options.prefer_format,
            }
    else:
        payload["recursive"] = source.recursive
    if source.locator:
        payload["locator"] = source.locator
    if source.metadata:
        payload["metadata"] = dict(source.metadata)
    return payload


def _cookies_to_payload(cookies_path: Path | None) -> dict[str, Any] | None:
    if cookies_path is None:
        return None
    return {
        "kind": "path",
        "value": str(cookies_path),
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


def _cookies_path_from_payload(
    payload: dict[str, Any],
    *,
    blob_resolver=None,
) -> Path | None:
    cookies_payload = payload.get("cookies")
    if isinstance(cookies_payload, dict):
        cookies_kind = str(cookies_payload.get("kind") or "").strip()
        cookies_value = str(cookies_payload.get("value") or "").strip()
        if cookies_kind == "remote_blob":
            if not cookies_value:
                return None
            if blob_resolver is None:
                raise ValueError("remote cookie blob requires a blob resolver")
            resolved = blob_resolver(cookies_value)
            if resolved is None:
                raise ValueError(f"remote cookie blob not found: {cookies_value}")
            return resolved
        if cookies_kind == "path" and cookies_value:
            return Path(cookies_value)

    legacy_path = payload.get("cookies_path")
    if isinstance(legacy_path, str) and legacy_path.strip():
        return Path(legacy_path)
    return None
