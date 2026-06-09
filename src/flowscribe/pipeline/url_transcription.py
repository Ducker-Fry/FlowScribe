"""URL orchestration pipeline for subtitle-first and audio fallback runs."""

from __future__ import annotations

import shutil
import time
from collections.abc import Callable
from pathlib import Path
from shutil import move

from flowscribe.capabilities import SubtitleCapability
from flowscribe.core.errors import FlowScribeError
from flowscribe.core.models import MediaItem, OutputArtifacts
from flowscribe.input.url_downloader import UrlAudioDownloader
from flowscribe.pipeline.progressive import tuned_chunk_overlap_seconds
from flowscribe.pipeline.runtime_factory import (
    build_transcription_pipeline,
    process_with_optional_progress,
    settings_from_job,
)
from flowscribe.providers.transcribe.registry import (
    is_native_engine_provider_name,
    supports_python_progressive_provider_name,
)
from flowscribe.tasks.models import ProgressEvent, SourceSpec, TaskSpec, TranscriptionJob


class UrlTranscriptionPipeline:
    """Handle URL subtitle-first execution and audio-transcription fallback."""

    def __init__(
        self,
        *,
        emit_progress: Callable[[Callable[[ProgressEvent], None], Callable[[], bool], ProgressEvent], None],
        emit_progressive_plan: Callable[..., None],
        emit_progressive_update: Callable[..., None],
        ensure_not_canceled: Callable[[Callable[[], bool]], None],
        source_progress_wrapper: Callable[[ProgressEvent, str, int, int], ProgressEvent],
        update_json_media_binding: Callable[[OutputArtifacts, Path, str], None],
        provider_runtime_validator: Callable[[TranscriptionJob, object], None] | None = None,
        downloader_cls=UrlAudioDownloader,
        pipeline_builder=build_transcription_pipeline,
        subtitle_runner: Callable[..., object] | None = None,
    ) -> None:
        self._emit_progress = emit_progress
        self._emit_progressive_plan = emit_progressive_plan
        self._emit_progressive_update = emit_progressive_update
        self._ensure_not_canceled = ensure_not_canceled
        self._source_progress_wrapper = source_progress_wrapper
        self._update_json_media_binding = update_json_media_binding
        self._provider_runtime_validator = provider_runtime_validator
        self._downloader_cls = downloader_cls
        self._pipeline_builder = pipeline_builder
        self._subtitle_runner = subtitle_runner

    def run(
        self,
        *,
        job: TranscriptionJob,
        task_spec: TaskSpec,
        source: SourceSpec,
        progress: Callable[[ProgressEvent], None],
        should_cancel: Callable[[], bool],
        current: int,
        total: int,
    ) -> OutputArtifacts:
        settings = settings_from_job(job, recursive=False)
        subtitle_result = self._run_subtitle_capability(
            task_spec,
            progress,
            should_cancel,
            current=current,
            total=total,
        )
        if subtitle_result.supported and subtitle_result.status == "success" and subtitle_result.artifacts:
            return subtitle_result.artifacts[0]
        if subtitle_result.supported and subtitle_result.status == "failed":
            message = (
                subtitle_result.error.user_message
                if subtitle_result.error is not None
                else "Native subtitle extraction failed."
            )
            raise FlowScribeError(message)
        if subtitle_result.status == "unsupported":
            self._emit_progress(
                progress,
                should_cancel,
                ProgressEvent(
                    stage="prepare",
                    message="No usable native subtitles found. Falling back to audio transcription.",
                    source=source.value,
                    current=current,
                    total=total,
                    task_id=task_spec.task_id,
                    capability="subtitle",
                    raw_metadata={"fallback": "audio-transcription"},
                ),
            )

        if self._provider_runtime_validator is not None:
            self._emit_progress(
                progress,
                should_cancel,
                ProgressEvent(
                    stage="validate",
                    message="Preparing transcription engine (loading models)...",
                    source=source.value,
                    current=current,
                    total=total,
                    task_id=task_spec.task_id,
                    capability="transcribe",
                ),
            )
            self._provider_runtime_validator(job, settings)

        downloader = self._downloader_cls(
            download_dir=settings.work_dir / ".url-media",
            max_bytes=job.max_download_mb * 1024 * 1024,
            max_duration_seconds=job.max_duration_seconds,
            timeout_seconds=job.download_timeout_seconds,
            network_family=job.network_family,
            cookies_path=job.cookies_path,
            proxy=job.proxy,
            progress_callback=lambda message: self._emit_progress(
                progress,
                should_cancel,
                ProgressEvent(
                    stage="download",
                    message=message,
                    source=source.value,
                    current=current,
                    total=total,
                    task_id=task_spec.task_id,
                    capability="transcribe",
                ),
            ),
            should_cancel=should_cancel,
        )

        self._emit_progress(
            progress,
            should_cancel,
            ProgressEvent(
                stage="download",
                message="Downloading/extracting remote audio...",
                source=source.value,
                current=current,
                total=total,
                task_id=task_spec.task_id,
                capability="transcribe",
            ),
        )
        self._ensure_not_canceled(should_cancel)

        from flowscribe.input.url_downloader import DownloadOptions as UrlDownloadOptions

        url_download_opts = None
        if source.download_options:
            url_download_opts = UrlDownloadOptions(
                media_kind=source.url_media_kind if source.keep_media else "audio",
                quality=source.download_options.quality,
                prefer_format=source.download_options.prefer_format,
            )

        download = downloader.download_audio(
            source.value,
            saved_media_kind=source.url_media_kind if source.keep_media else "audio",
            download_options=url_download_opts,
        )
        try:
            self._emit_progress(
                progress,
                should_cancel,
                ProgressEvent(
                    stage="prepare",
                    message=f"Remote audio ready: {download.path}",
                    source=source.value,
                    path=download.path,
                    task_id=task_spec.task_id,
                    capability="transcribe",
                ),
            )
            pipeline = self._pipeline_builder(job, settings)
            self._ensure_not_canceled(should_cancel)
            item = MediaItem(path=download.path)
            if (
                job.progressive_enabled
                and supports_python_progressive_provider_name(job.provider_name)
                and hasattr(pipeline, "process_progressive")
            ):
                run_started_at = time.perf_counter()
                artifacts, _ = pipeline.process_progressive(
                    item,
                    chunk_duration_seconds=job.progressive_chunk_seconds,
                    chunk_overlap_seconds=tuned_chunk_overlap_seconds(
                        requested_overlap_seconds=job.progressive_chunk_overlap_seconds,
                        language=job.language,
                        preset=job.preset,
                    ),
                    resume=job.progressive_resume,
                    keep_progressive_cache=True,
                    max_workers=job.progressive_max_workers,
                    max_failed_chunks=10,
                    plan_callback=lambda duration_info, chunk_plan: self._emit_progressive_plan(
                        progress,
                        should_cancel,
                        item=item,
                        duration_info=duration_info,
                        chunk_plan=chunk_plan,
                    ),
                    update_callback=lambda update: self._emit_progressive_update(
                        progress,
                        should_cancel,
                        item=item,
                        update=update,
                        run_started_at=run_started_at,
                    ),
                    should_cancel=should_cancel,
                )
            else:
                artifacts = process_with_optional_progress(
                    pipeline,
                    item,
                    should_cancel=should_cancel,
                    progress=(
                        lambda event: self._emit_progress(
                            progress,
                            should_cancel,
                            self._source_progress_wrapper(event, str(download.path), current, total),
                        )
                    )
                    if is_native_engine_provider_name(job.provider_name)
                    else None,
                )
            preserved_media_path = self._preserve_url_media(download, source=source, job=job)
            artifacts = OutputArtifacts(
                paths=artifacts.paths,
                media_path=preserved_media_path,
                media_kind=download.saved_media_kind if preserved_media_path is not None else None,
                requested_media_kind=source.url_media_kind if source.keep_media else None,
                media_fallback=(
                    preserved_media_path is not None
                    and source.keep_media
                    and download.saved_media_kind != source.url_media_kind
                ),
                source_kind=source.kind,
                source_value=source.value,
                auto_bind_media=source.auto_bind_media,
                transcription_strategy="audio-transcription",
            )

            if preserved_media_path is not None and source.auto_bind_media:
                self._update_json_media_binding(artifacts, preserved_media_path, download.saved_media_kind)

            for path in artifacts.paths:
                self._emit_progress(
                    progress,
                    should_cancel,
                    ProgressEvent(
                        stage="write",
                        message=f"Wrote: {path}",
                        source=source.value,
                        path=path,
                        task_id=task_spec.task_id,
                        capability="transcribe",
                    ),
                )
        finally:
            shutil.rmtree(download.cleanup_dir, ignore_errors=True)
        return artifacts

    def _run_subtitle_capability(
        self,
        task_spec: TaskSpec,
        progress: Callable[[ProgressEvent], None],
        should_cancel: Callable[[], bool],
        *,
        current: int,
        total: int,
    ):
        if self._subtitle_runner is not None:
            return self._subtitle_runner(
                task_spec,
                progress,
                should_cancel,
                current=current,
                total=total,
            )
        if "subtitle" not in task_spec.requested_capabilities or task_spec.source.kind != "url":
            from flowscribe.tasks.models import CapabilityResult

            return CapabilityResult(
                task_id=task_spec.task_id,
                capability="subtitle",
                supported=False,
                status="unsupported",
            )
        return SubtitleCapability().run(
            task_spec,
            progress_cb=lambda event: self._emit_progress(
                progress,
                should_cancel,
                self._source_progress_wrapper(event, task_spec.source.value, current, total),
            ),
            cancel_token=should_cancel,
        )

    def _preserve_url_media(
        self,
        download,
        *,
        source: SourceSpec,
        job: TranscriptionJob,
    ) -> Path | None:
        if not source.keep_media:
            return None

        candidate = download.saved_media_path or download.path
        if not candidate.exists():
            return None

        target_root = (
            source.media_output_dir
            if source.media_output_dir is not None
            else job.output_dir / "url-media"
        )
        target_root = target_root.expanduser().resolve()
        target_dir = target_root / download.cleanup_dir.name
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = self._available_target_path(target_dir / candidate.name)
        move(str(candidate), str(target_path))
        return target_path

    @staticmethod
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
