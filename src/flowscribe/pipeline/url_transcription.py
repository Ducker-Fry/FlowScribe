"""URL orchestration pipeline for subtitle-first and audio fallback runs."""

from __future__ import annotations

import shutil
import time
from collections.abc import Callable
from pathlib import Path
from shutil import move

from flowscribe.app.progressive_policy import (
    ProgressiveExecutionPolicy,
    job_with_progressive_policy,
    progressive_failure_note,
)
from flowscribe.capabilities import SubtitleCapability
from flowscribe.core.errors import FlowScribeError
from flowscribe.core.models import MediaItem, OutputArtifacts
from flowscribe.input.url_downloader import UrlAudioDownloader
from flowscribe.pipeline.runtime_factory import (
    build_transcription_pipeline,
    process_with_optional_progress,
    settings_from_job,
)
from flowscribe.tasks.models import ProgressEvent, SourceSpec, TaskSpec, TranscriptionJob


class UrlTranscriptionPipeline:
    """Handle URL subtitle-first execution and audio-transcription fallback."""

    def __init__(
        self,
        *,
        emit_progress: Callable[[Callable[[ProgressEvent], None], Callable[[], bool], ProgressEvent], None],
        emit_policy_notes: Callable[..., None],
        emit_progressive_plan: Callable[..., None],
        emit_progressive_update: Callable[..., None],
        emit_progressive_summary: Callable[..., None],
        capture_progressive_native_event: Callable[..., ProgressEvent],
        ensure_not_canceled: Callable[[Callable[[], bool]], None],
        source_progress_wrapper: Callable[[ProgressEvent, str, int, int], ProgressEvent],
        update_json_media_binding: Callable[[OutputArtifacts, Path, str], None],
        provider_runtime_validator: Callable[[TranscriptionJob, object], None] | None = None,
        downloader_cls=UrlAudioDownloader,
        pipeline_builder=build_transcription_pipeline,
        subtitle_runner: Callable[..., object] | None = None,
    ) -> None:
        self._emit_progress = emit_progress
        self._emit_policy_notes = emit_policy_notes
        self._emit_progressive_plan = emit_progressive_plan
        self._emit_progressive_update = emit_progressive_update
        self._emit_progressive_summary = emit_progressive_summary
        self._capture_progressive_native_event = capture_progressive_native_event
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
        policy: ProgressiveExecutionPolicy,
        task_spec: TaskSpec,
        source: SourceSpec,
        progress: Callable[[ProgressEvent], None],
        should_cancel: Callable[[], bool],
        current: int,
        total: int,
    ) -> OutputArtifacts:
        execution_job = job_with_progressive_policy(job, policy)
        settings = settings_from_job(execution_job, recursive=False)
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
        self._emit_policy_notes(
            progress,
            should_cancel,
            policy=policy,
            source=source.value,
            current=current,
            total=total,
            task_id=task_spec.task_id,
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
            self._provider_runtime_validator(execution_job, settings)

        downloader = self._downloader_cls(
            download_dir=settings.work_dir / ".url-media",
            max_bytes=execution_job.max_download_mb * 1024 * 1024,
            max_duration_seconds=execution_job.max_duration_seconds,
            timeout_seconds=execution_job.download_timeout_seconds,
            network_family=execution_job.network_family,
            cookies_path=execution_job.cookies_path,
            proxy=execution_job.proxy,
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
            pipeline = self._pipeline_builder(execution_job, settings)
            self._ensure_not_canceled(should_cancel)
            item = MediaItem(path=download.path)
            if policy.mode == "python-progressive" and hasattr(pipeline, "process_progressive"):
                run_state = {"resume_used": False}
                run_started_at = time.perf_counter()
                artifacts, state = pipeline.process_progressive(
                    item,
                    chunk_duration_seconds=policy.chunk_seconds,
                    chunk_overlap_seconds=policy.overlap_seconds,
                    resume=policy.resume_effective,
                    keep_progressive_cache=True,
                    max_workers=policy.max_workers,
                    max_failed_chunks=10,
                    plan_callback=lambda duration_info, chunk_plan: self._emit_progressive_plan(
                        progress,
                        should_cancel,
                        policy=policy,
                        item=item,
                        duration_info=duration_info,
                        chunk_plan=chunk_plan,
                        task_id=task_spec.task_id,
                        current=current,
                        total=total,
                    ),
                    update_callback=lambda update: self._emit_progressive_update(
                        progress,
                        should_cancel,
                        policy=policy,
                        item=item,
                        update=update,
                        run_started_at=run_started_at,
                        task_id=task_spec.task_id,
                        current=current,
                        total=total,
                        run_state=run_state,
                    ),
                    should_cancel=should_cancel,
                )
                self._emit_progressive_summary(
                    progress,
                    should_cancel,
                    policy=policy,
                    source=str(download.path),
                    task_id=task_spec.task_id,
                    current=current,
                    total=total,
                    chunk_count=len(state.chunk_plan.chunks),
                    completed_chunks=state.completed_chunks,
                    failed_chunks=state.failed_chunks,
                    effective_parallel_chunks=state.effective_parallel_chunks,
                    total_duration_seconds=state.duration_info.duration_seconds,
                    processed_duration_seconds=state.processed_duration_seconds,
                    cache_dir_present=state.cache_dir is not None,
                    resume_used=run_state["resume_used"],
                )
            elif policy.mode == "native-engine-progressive":
                run_state = {
                    "resume_used": False,
                    "chunk_count": None,
                    "completed_chunks": None,
                    "failed_chunks": None,
                    "effective_parallel_chunks": None,
                    "processed_duration_seconds": None,
                    "total_duration_seconds": None,
                }
                artifacts = process_with_optional_progress(
                    pipeline,
                    item,
                    should_cancel=should_cancel,
                    progress=lambda event: self._emit_progress(
                        progress,
                        should_cancel,
                        self._capture_progressive_native_event(
                            self._source_progress_wrapper(event, str(download.path), current, total),
                            run_state=run_state,
                        ),
                    ),
                )
                self._emit_progressive_summary(
                    progress,
                    should_cancel,
                    policy=policy,
                    source=str(download.path),
                    task_id=task_spec.task_id,
                    current=current,
                    total=total,
                    chunk_count=run_state["chunk_count"],
                    completed_chunks=run_state["completed_chunks"],
                    failed_chunks=run_state["failed_chunks"],
                    effective_parallel_chunks=run_state["effective_parallel_chunks"],
                    total_duration_seconds=run_state["total_duration_seconds"],
                    processed_duration_seconds=run_state["processed_duration_seconds"],
                    cache_dir_present=False,
                    resume_used=False,
                )
            else:
                artifacts = process_with_optional_progress(
                    pipeline,
                    item,
                    should_cancel=should_cancel,
                    progress=None,
                )
            preserved_media_path = self._preserve_url_media(download, source=source, job=execution_job)
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
                source_locator=source.resolved_locator,
                original_filename=Path(source.value).name if Path(source.value).name else None,
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
        except FlowScribeError:
            if policy.mode != "classic":
                self._emit_progress(
                    progress,
                    should_cancel,
                    ProgressEvent(
                        stage="prepare",
                        message=progressive_failure_note(policy),
                        source=source.value,
                        current=current,
                        total=total,
                        task_id=task_spec.task_id,
                        capability="transcribe",
                    ),
                )
            raise
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
