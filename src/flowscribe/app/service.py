"""Application service for running transcription jobs."""

from __future__ import annotations

import json
import time
import logging
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from flowscribe.tasks.models import (
    CancelAck,
    CancelRequest,
    CapabilityResult,
    ErrorInfo,
    ProgressCallback,
    ProgressEvent,
    SourceSpec,
    TaskSpec,
    TranscriptionJob,
    TranscriptionResult,
)
from flowscribe.core.errors import CancellationError, FlowScribeError
from flowscribe.core.models import (
    MediaDurationInfo,
    MediaItem,
    OutputArtifacts,
    ProgressiveTranscriptionUpdate,
    TranscriptionChunkPlan,
)
from flowscribe.pipeline.progressive import tuned_chunk_overlap_seconds
from flowscribe.pipeline.runtime_factory import (
    build_transcription_pipeline,
    process_with_optional_progress,
    settings_from_job,
)
from flowscribe.pipeline.url_transcription import UrlTranscriptionPipeline
from flowscribe.input.local_source import LocalFileSource
from flowscribe.input.url_downloader import UrlAudioDownloader
from flowscribe.providers.transcribe.registry import (
    is_native_engine_provider_name,
    supports_python_progressive_provider_name,
)

LOGGER = logging.getLogger(__name__)

# Compatibility aliases for existing tests and external integrations.
_build_pipeline = build_transcription_pipeline
_process_with_optional_progress = process_with_optional_progress
_settings_from_job = settings_from_job


class TranscriptionService:
    """Run transcription jobs through a stable app-facing interface."""

    def __init__(self) -> None:
        self._event_sequence = 0

    def run(
        self,
        job: TranscriptionJob,
        progress: ProgressCallback | None = None,
        should_cancel: Callable[[], bool] | None = None,
    ) -> TranscriptionResult:
        progress = progress or (lambda event: None)
        should_cancel = should_cancel or (lambda: False)
        task_specs = job.to_task_specs()
        started_at = datetime.now()
        outputs: list[OutputArtifacts] = []
        errors: list[ErrorInfo] = []
        LOGGER.info(
            "Starting transcription job: sources=%s provider=%s model=%s output_dir=%s progressive=%s",
            len(job.sources),
            job.provider_name,
            job.model_name,
            job.output_dir,
            job.progressive_enabled,
        )

        try:
            self._emit_progress(
                progress,
                should_cancel,
                ProgressEvent(
                    stage="discover",
                    message=f"Received {len(job.sources)} source(s).",
                    total=len(job.sources),
                    task_id=task_specs[0].task_id if task_specs else None,
                )
            )

            for index, (source, task_spec) in enumerate(zip(job.sources, task_specs, strict=False), start=1):
                self._ensure_not_canceled(should_cancel)
                source_outputs, source_errors = self._run_source(
                    job,
                    task_spec,
                    source,
                    progress,
                    should_cancel,
                    index,
                    len(job.sources),
                )
                outputs.extend(source_outputs)
                errors.extend(source_errors)
        except CancellationError:
            LOGGER.info("Transcription job canceled.")
            progress(
                ProgressEvent(
                    stage="canceled",
                    message="Transcription canceled.",
                    total=len(job.sources),
                    task_id=task_specs[0].task_id if task_specs else None,
                ),
            )
            return TranscriptionResult(
                job=job,
                task_specs=task_specs,
                outputs=tuple(outputs),
                errors=tuple(errors),
                canceled=True,
                started_at=started_at,
                finished_at=datetime.now(),
            )
        self._emit_progress(
            progress,
            should_cancel,
            ProgressEvent(
                stage="complete",
                message=f"Done. Succeeded: {len(outputs)}. Failed: {len(errors)}.",
                total=len(job.sources),
                task_id=task_specs[0].task_id if task_specs else None,
            ),
        )
        if errors:
            for error in errors:
                LOGGER.error(
                    "Transcription job source failed: source=%s code=%s message=%s",
                    error.source,
                    error.code,
                    error.message,
                )
        else:
            LOGGER.info("Transcription job completed successfully with %s output(s).", len(outputs))
        return TranscriptionResult(
            job=job,
            task_specs=task_specs,
            outputs=tuple(outputs),
            errors=tuple(errors),
            started_at=started_at,
            finished_at=datetime.now(),
        )

    def _run_source(
        self,
        job: TranscriptionJob,
        task_spec: TaskSpec,
        source: SourceSpec,
        progress: ProgressCallback,
        should_cancel: Callable[[], bool],
        current: int,
        total: int,
    ) -> tuple[tuple[OutputArtifacts, ...], tuple[ErrorInfo, ...]]:
        try:
            if source.kind == "local":
                return self._run_local_source(job, task_spec, source, progress, should_cancel, current, total)
            if source.kind == "url":
                return (self._run_url_source(job, task_spec, source, progress, should_cancel, current, total),), ()
            if source.kind == "capture":
                raise FlowScribeError("System audio capture source is planned but not implemented yet.")
            raise FlowScribeError(f"Unsupported source kind: {source.kind}")
        except CancellationError:
            raise
        except FlowScribeError as exc:
            LOGGER.exception("Source failed: source=%s kind=%s", source.value, source.kind)
            error = _error_from_exception(exc, source=source.value)
            self._emit_progress(
                progress,
                should_cancel,
                ProgressEvent(
                    stage="error",
                    message=str(exc),
                    source=source.value,
                    current=current,
                    total=total,
                    task_id=task_spec.task_id,
                    capability="transcribe",
                )
            )
            return (), (error,)

    def _run_local_source(
        self,
        job: TranscriptionJob,
        task_spec: TaskSpec,
        source: SourceSpec,
        progress: ProgressCallback,
        should_cancel: Callable[[], bool],
        current: int,
        total: int,
    ) -> tuple[tuple[OutputArtifacts, ...], tuple[ErrorInfo, ...]]:
        settings = _settings_from_job(job, recursive=source.recursive)
        pipeline = _build_pipeline(job, settings)
        input_source = LocalFileSource([Path(source.value)], recursive=settings.recursive)
        items = input_source.discover()
        outputs: list[OutputArtifacts] = []
        errors: list[ErrorInfo] = []

        self._emit_progress(
            progress,
            should_cancel,
            ProgressEvent(
                stage="discover",
                message=f"Discovered {len(items)} media file(s).",
                source=source.value,
                current=current,
                total=total,
                task_id=task_spec.task_id,
                capability="transcribe",
            )
        )
        for item_index, item in enumerate(items, start=1):
            self._ensure_not_canceled(should_cancel)
            self._emit_progress(
                progress,
                should_cancel,
                ProgressEvent(
                    stage="transcribe",
                    message=f"Processing {item.path}",
                    source=str(item.path),
                    current=item_index,
                    total=len(items),
                    task_id=task_spec.task_id,
                    capability="transcribe",
                )
            )
            try:
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
                    artifacts = _process_with_optional_progress(
                        pipeline,
                        item,
                        should_cancel=should_cancel,
                        progress=(
                            lambda event: self._emit_progress(
                                progress,
                                should_cancel,
                                _with_source_and_totals(
                                    event,
                                    source=str(item.path),
                                    current=item_index,
                                    total=len(items),
                                ),
                            )
                        )
                        if is_native_engine_provider_name(job.provider_name)
                        else None,
                    )
                self._update_json_artifacts(
                    artifacts=artifacts,
                    task_spec=task_spec,
                    source=source,
                )
            except FlowScribeError as exc:
                LOGGER.exception("Local media item failed: %s", item.path)
                errors.append(_error_from_exception(exc, source=str(item.path)))
                self._emit_progress(
                    progress,
                    should_cancel,
                    ProgressEvent(
                        stage="error",
                        message=f"Failed: {item.path} - {exc}",
                        source=str(item.path),
                        current=item_index,
                        total=len(items),
                        task_id=task_spec.task_id,
                        capability="transcribe",
                    )
                )
                continue
            outputs.append(artifacts)
            for path in artifacts.paths:
                self._emit_progress(
                    progress,
                    should_cancel,
                    ProgressEvent(
                        stage="write",
                        message=f"Wrote: {path}",
                        source=str(item.path),
                        path=path,
                        task_id=task_spec.task_id,
                        capability="transcribe",
                    )
                )
        return tuple(outputs), tuple(errors)

    def _run_url_source(
        self,
        job: TranscriptionJob,
        task_spec: TaskSpec,
        source: SourceSpec,
        progress: ProgressCallback,
        should_cancel: Callable[[], bool],
        current: int,
        total: int,
    ) -> OutputArtifacts:
        return UrlTranscriptionPipeline(
            emit_progress=self._emit_progress,
            emit_progressive_plan=self._emit_progressive_plan,
            emit_progressive_update=self._emit_progressive_update,
            ensure_not_canceled=self._ensure_not_canceled,
            source_progress_wrapper=_with_source_and_totals_for_pipeline,
            update_json_media_binding=self._update_json_media_binding,
            downloader_cls=UrlAudioDownloader,
            pipeline_builder=_build_pipeline,
            subtitle_runner=self._run_subtitle_capability,
        ).run(
            job=job,
            task_spec=task_spec,
            source=source,
            progress=progress,
            should_cancel=should_cancel,
            current=current,
            total=total,
        )

    def _run_subtitle_capability(
        self,
        task_spec: TaskSpec,
        progress: ProgressCallback,
        should_cancel: Callable[[], bool],
        *,
        current: int,
        total: int,
    ) -> CapabilityResult:
        """Compatibility hook retained for tests and external monkeypatching."""

        from flowscribe.capabilities import SubtitleCapability

        if "subtitle" not in task_spec.requested_capabilities or task_spec.source.kind != "url":
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
                _with_source_and_totals(
                    event,
                    source=task_spec.source.value,
                    current=current,
                    total=total,
                ),
            ),
            cancel_token=should_cancel,
        )

    @staticmethod
    def _ensure_not_canceled(should_cancel: Callable[[], bool]) -> None:
        if should_cancel():
            raise CancellationError("Transcription canceled.")

    def build_cancel_request(self, task_spec: TaskSpec, *, force: bool = False) -> CancelRequest:
        return CancelRequest(task_id=task_spec.task_id, force=force)

    def acknowledge_cancel(
        self,
        request: CancelRequest,
        *,
        checkpoint: str | None = None,
        failed: bool = False,
    ) -> CancelAck:
        return CancelAck(
            task_id=request.task_id,
            status="failed" if failed else "cancelled",
            checkpoint=checkpoint,
        )

    def _emit_progress(
        self,
        progress: ProgressCallback,
        should_cancel: Callable[[], bool],
        event: ProgressEvent,
    ) -> None:
        self._ensure_not_canceled(should_cancel)
        progress(self._envelope_event(event))
        if event.stage != "canceled":
            self._ensure_not_canceled(should_cancel)

    def _envelope_event(self, event: ProgressEvent) -> ProgressEvent:
        self._event_sequence += 1
        return replace(
            event,
            event_type=event.event_type or self._event_type_for_event(event),
            timestamp=event.timestamp or datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            sequence=event.sequence if event.sequence is not None else self._event_sequence,
        )

    @staticmethod
    def _event_type_for_event(event: ProgressEvent) -> str:
        if event.stage == "discover" and event.source is None:
            return "task.accepted"
        if event.stage == "discover":
            return "task.started"
        if event.stage == "write":
            return "artifact.written"
        if event.stage == "complete":
            return "task.completed"
        if event.stage == "error":
            return "task.failed"
        if event.stage == "canceled":
            return "task.canceled"
        return "progress"

    def _emit_progressive_plan(
        self,
        progress: ProgressCallback,
        should_cancel: Callable[[], bool],
        *,
        item: MediaItem,
        duration_info: MediaDurationInfo,
        chunk_plan: TranscriptionChunkPlan,
    ) -> None:
        duration_seconds = duration_info.duration_seconds
        if duration_seconds is None:
            message = f"Progressive transcription prepared for {item.path.name}."
        else:
            message = (
                f"Progressive transcription ready for {item.path.name}: "
                f"{_format_duration_label(duration_seconds)} across {len(chunk_plan.chunks)} chunk(s)."
            )
        self._emit_progress(
            progress,
            should_cancel,
            ProgressEvent(
                stage="prepare",
                message=message,
                source=str(item.path),
                total_duration_seconds=duration_seconds,
                chunk_count=len(chunk_plan.chunks),
                capability="transcribe",
            ),
        )

    def _emit_progressive_update(
        self,
        progress: ProgressCallback,
        should_cancel: Callable[[], bool],
        *,
        item: MediaItem,
        update: ProgressiveTranscriptionUpdate,
        run_started_at: float,
    ) -> None:
        processed_seconds = update.state.processed_duration_seconds
        total_seconds = update.state.duration_info.duration_seconds
        elapsed_wall_seconds = max(0.001, time.perf_counter() - run_started_at)
        realtime_factor = None
        eta_seconds = None
        if processed_seconds > 0:
            realtime_factor = processed_seconds / elapsed_wall_seconds
            if total_seconds is not None and realtime_factor > 0:
                remaining_seconds = max(0.0, total_seconds - processed_seconds)
                eta_seconds = remaining_seconds / realtime_factor
        self._emit_progress(
            progress,
            should_cancel,
            ProgressEvent(
                stage="resume" if update.resumed else "transcribe",
                message=_progressive_status_message(
                    source_name=item.path.name,
                    processed_seconds=processed_seconds,
                    total_seconds=total_seconds,
                    chunk_index=update.chunk_result.chunk.index,
                    chunk_count=len(update.state.chunk_plan.chunks),
                    failed_chunks=update.state.failed_chunks,
                    realtime_factor=realtime_factor,
                    eta_seconds=eta_seconds,
                    resumed=update.resumed,
                ),
                source=str(item.path),
                processed_duration_seconds=processed_seconds,
                total_duration_seconds=total_seconds,
                eta_seconds=eta_seconds,
                realtime_factor=realtime_factor,
                chunk_index=update.chunk_result.chunk.index,
                chunk_count=len(update.state.chunk_plan.chunks),
                completed_chunks=update.state.completed_chunks,
                failed_chunks=update.state.failed_chunks,
                segments=update.appended_segments,
                resumed=update.resumed,
                capability="transcribe",
            ),
        )

    def _update_json_media_binding(
        self,
        artifacts: OutputArtifacts,
        media_path: Path,
        media_kind: str,
    ) -> None:
        """Update JSON transcript files with media binding information."""
        for path in artifacts.paths:
            if path.suffix.lower() == ".json":
                try:
                    data = self._load_json_payload(path)
                    data["media_binding"] = {
                        "path": str(media_path),
                        "kind": media_kind,
                    }
                    self._write_json_payload(path, data)
                except (OSError, json.JSONDecodeError) as e:
                    # Log error but don't fail the transcription
                    import warnings
                    warnings.warn(f"Failed to update media binding in {path}: {e}", UserWarning)

    def _update_json_artifacts(
        self,
        *,
        artifacts: OutputArtifacts,
        task_spec: TaskSpec,
        source: SourceSpec,
    ) -> None:
        for path in artifacts.paths:
            if path.suffix.lower() != ".json":
                continue
            try:
                data = self._load_json_payload(path)
                data["task_id"] = task_spec.task_id
                data["resume"] = {
                    "resume_token": task_spec.resume_token,
                    "checkpoint_id": task_spec.checkpoint_id,
                    "cache_key": task_spec.cache_key,
                }
                data["artifacts"] = [
                    {
                        "format": artifact_path.suffix.lstrip(".").lower(),
                        "path": str(artifact_path),
                    }
                    for artifact_path in artifacts.paths
                ]
                metadata = data.get("metadata")
                if not isinstance(metadata, dict):
                    metadata = {}
                    data["metadata"] = metadata
                metadata.setdefault("source_kind", source.kind)
                metadata.setdefault("source_locator", source.resolved_locator)
                self._write_json_payload(path, data)
            except (OSError, json.JSONDecodeError):
                LOGGER.warning("Failed to update JSON artifact metadata: %s", path, exc_info=True)

    @staticmethod
    def _load_json_payload(path: Path) -> dict:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def _write_json_payload(path: Path, data: dict) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")


def _error_from_exception(exc: FlowScribeError, *, source: str) -> ErrorInfo:
    return ErrorInfo(
        code=exc.__class__.__name__,
        message=str(exc),
        source=source,
        recoverable=True,
    )


def _with_source_and_totals(
    event: ProgressEvent,
    *,
    source: str,
    current: int,
    total: int,
) -> ProgressEvent:
    return ProgressEvent(
        stage=event.stage,
        message=event.message,
        source=event.source or source,
        current=event.current if event.current is not None else current,
        total=event.total if event.total is not None else total,
        path=event.path,
        processed_duration_seconds=event.processed_duration_seconds,
        total_duration_seconds=event.total_duration_seconds,
        eta_seconds=event.eta_seconds,
        realtime_factor=event.realtime_factor,
        chunk_index=event.chunk_index,
        chunk_count=event.chunk_count,
        completed_chunks=event.completed_chunks,
        failed_chunks=event.failed_chunks,
        segments=event.segments,
        resumed=event.resumed,
        task_id=event.task_id,
        capability=event.capability,
        percent=event.percent,
        raw_metadata=event.raw_metadata,
    )


def _with_source_and_totals_for_pipeline(
    event: ProgressEvent,
    source: str,
    current: int,
    total: int,
) -> ProgressEvent:
    return _with_source_and_totals(
        event,
        source=source,
        current=current,
        total=total,
    )


def _format_duration_label(value: float) -> str:
    total_seconds = max(0, int(round(value)))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


def _progressive_status_message(
    *,
    source_name: str,
    processed_seconds: float,
    total_seconds: float | None,
    chunk_index: int,
    chunk_count: int,
    failed_chunks: int = 0,
    realtime_factor: float | None = None,
    eta_seconds: float | None = None,
    resumed: bool = False,
) -> str:
    prefix = "Resumed" if resumed else "Processed"
    if total_seconds is None:
        base = f"{prefix} chunk {chunk_index}/{chunk_count} for {source_name}."
    else:
        base = (
            f"{prefix} chunk {chunk_index}/{chunk_count} for {source_name}: "
            f"{_format_duration_label(processed_seconds)} / {_format_duration_label(total_seconds)}."
        )
    extras: list[str] = []
    if failed_chunks > 0:
        extras.append(f"{failed_chunks} failed")
    if realtime_factor is not None:
        extras.append(f"{realtime_factor:.1f}x realtime")
    if eta_seconds is not None:
        extras.append(f"ETA {_format_duration_label(eta_seconds)}")
    if extras:
        return base + " " + " | ".join(extras)
    return base
