"""Application service for running transcription jobs."""

from __future__ import annotations

import shutil
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from shutil import move

from flowscribe.app.models import (
    ErrorInfo,
    ProgressCallback,
    ProgressEvent,
    SourceSpec,
    TranscriptionJob,
    TranscriptionResult,
)
from flowscribe.config.settings import AppSettings
from flowscribe.core.errors import CancellationError, FlowScribeError
from flowscribe.core.models import (
    MediaDurationInfo,
    MediaItem,
    OutputArtifacts,
    ProgressiveTranscriptionUpdate,
    TranscriptionChunkPlan,
)
from flowscribe.core.pipeline import LocalTranscriptionPipeline
from flowscribe.core.progressive import tuned_chunk_overlap_seconds
from flowscribe.input.local_source import LocalFileSource
from flowscribe.input.url_downloader import UrlAudioDownloader
from flowscribe.media.audio_extractor import FfmpegAudioExtractor
from flowscribe.nlp.script_converter import simplify_chinese_transcript
from flowscribe.output.artifact_writer import TranscriptArtifactWriter
from flowscribe.output.json_writer import JsonTranscriptWriter
from flowscribe.output.md_writer import MarkdownTranscriptWriter
from flowscribe.output.paths import OutputPathBuilder
from flowscribe.output.srt_writer import SrtTranscriptWriter
from flowscribe.output.txt_writer import TxtTranscriptWriter
from flowscribe.output.vtt_writer import VttTranscriptWriter
from flowscribe.transcription.providers import (
    ProviderTranscriptionSettings,
    resolve_transcription_provider,
)


class TranscriptionService:
    """Run transcription jobs through a stable app-facing interface."""

    def run(
        self,
        job: TranscriptionJob,
        progress: ProgressCallback | None = None,
        should_cancel: Callable[[], bool] | None = None,
    ) -> TranscriptionResult:
        progress = progress or (lambda event: None)
        should_cancel = should_cancel or (lambda: False)
        started_at = datetime.now()
        outputs: list[OutputArtifacts] = []
        errors: list[ErrorInfo] = []

        self._emit_progress(
            progress,
            should_cancel,
            ProgressEvent(
                stage="discover",
                message=f"Received {len(job.sources)} source(s).",
                total=len(job.sources),
            )
        )

        try:
            for index, source in enumerate(job.sources, start=1):
                self._ensure_not_canceled(should_cancel)
                source_outputs, source_errors = self._run_source(
                    job,
                    source,
                    progress,
                    should_cancel,
                    index,
                    len(job.sources),
                )
                outputs.extend(source_outputs)
                errors.extend(source_errors)
        except CancellationError:
            progress(
                ProgressEvent(
                    stage="canceled",
                    message="Transcription canceled.",
                    total=len(job.sources),
                ),
            )
            return TranscriptionResult(
                job=job,
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
            ),
        )
        return TranscriptionResult(
            job=job,
            outputs=tuple(outputs),
            errors=tuple(errors),
            started_at=started_at,
            finished_at=datetime.now(),
        )

    def _run_source(
        self,
        job: TranscriptionJob,
        source: SourceSpec,
        progress: ProgressCallback,
        should_cancel: Callable[[], bool],
        current: int,
        total: int,
    ) -> tuple[tuple[OutputArtifacts, ...], tuple[ErrorInfo, ...]]:
        try:
            if source.kind == "local":
                return self._run_local_source(job, source, progress, should_cancel, current, total)
            if source.kind == "url":
                return (self._run_url_source(job, source, progress, should_cancel, current, total),), ()
            if source.kind == "capture":
                raise FlowScribeError("System audio capture source is planned but not implemented yet.")
            raise FlowScribeError(f"Unsupported source kind: {source.kind}")
        except CancellationError:
            raise
        except FlowScribeError as exc:
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
                )
            )
            return (), (error,)

    def _run_local_source(
        self,
        job: TranscriptionJob,
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
                )
            )
            try:
                if job.progressive_enabled and hasattr(pipeline, "process_progressive"):
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
                    artifacts = pipeline.process(item, should_cancel=should_cancel)
            except FlowScribeError as exc:
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
                    )
                )
        return tuple(outputs), tuple(errors)

    def _run_url_source(
        self,
        job: TranscriptionJob,
        source: SourceSpec,
        progress: ProgressCallback,
        should_cancel: Callable[[], bool],
        current: int,
        total: int,
    ) -> OutputArtifacts:
        settings = _settings_from_job(job, recursive=False)
        downloader = UrlAudioDownloader(
            download_dir=settings.work_dir / ".url-media",
            max_bytes=job.max_download_mb * 1024 * 1024,
            max_duration_seconds=job.max_duration_seconds,
            timeout_seconds=job.download_timeout_seconds,
            network_family=job.network_family,
            cookies_path=job.cookies_path,
            proxy=job.proxy,
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
            )
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
                )
            )
            pipeline = _build_pipeline(job, settings)
            self._ensure_not_canceled(should_cancel)
            item = MediaItem(path=download.path)
            if job.progressive_enabled and hasattr(pipeline, "process_progressive"):
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
                artifacts = pipeline.process(item, should_cancel=should_cancel)
            preserved_media_path = self._preserve_url_media(
                download,
                source=source,
                job=job,
            )
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
            )

            # Update JSON files with media binding info
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
                    )
                )
        finally:
            shutil.rmtree(download.cleanup_dir, ignore_errors=True)
        return artifacts

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

    @staticmethod
    def _ensure_not_canceled(should_cancel: Callable[[], bool]) -> None:
        if should_cancel():
            raise CancellationError("Transcription canceled.")

    def _emit_progress(
        self,
        progress: ProgressCallback,
        should_cancel: Callable[[], bool],
        event: ProgressEvent,
    ) -> None:
        self._ensure_not_canceled(should_cancel)
        progress(event)
        if event.stage != "canceled":
            self._ensure_not_canceled(should_cancel)

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
            ),
        )

    def _update_json_media_binding(
        self,
        artifacts: OutputArtifacts,
        media_path: Path,
        media_kind: str,
    ) -> None:
        """Update JSON transcript files with media binding information."""
        import json

        for path in artifacts.paths:
            if path.suffix.lower() == ".json":
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)

                    data["media_binding"] = {
                        "path": str(media_path),
                        "kind": media_kind,
                    }

                    with open(path, "w", encoding="utf-8") as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
                        f.write("\n")
                except (OSError, json.JSONDecodeError) as e:
                    # Log error but don't fail the transcription
                    import warnings
                    warnings.warn(f"Failed to update media binding in {path}: {e}", UserWarning)


def _settings_from_job(job: TranscriptionJob, *, recursive: bool) -> AppSettings:
    return AppSettings.from_options(
        output_dir=job.output_dir,
        work_dir=job.work_dir,
        model_name=job.model_name,
        language=job.language,
        preset=job.preset,
        task=job.task,
        beam_size=job.beam_size,
        vad_filter=job.vad_filter,
        no_vad_filter=job.no_vad_filter,
        initial_prompt=job.initial_prompt,
        word_timestamps=job.word_timestamps,
        recursive=recursive,
        overwrite=job.overwrite,
        keep_audio=job.keep_audio,
    )


def _error_from_exception(exc: FlowScribeError, *, source: str) -> ErrorInfo:
    return ErrorInfo(
        code=exc.__class__.__name__,
        message=str(exc),
        source=source,
        recoverable=True,
    )


def _build_pipeline(job: TranscriptionJob, settings: AppSettings) -> LocalTranscriptionPipeline:
    path_builder = OutputPathBuilder(
        overwrite=settings.overwrite,
        base_name=job.output_name_base,
    )
    provider = resolve_transcription_provider()
    provider_settings = ProviderTranscriptionSettings(
        model_name=settings.model_name,
        language=settings.language,
        task=settings.task,
        beam_size=settings.beam_size,
        vad_filter=settings.vad_filter,
        initial_prompt=settings.initial_prompt,
        preset=settings.preset,
        word_timestamps=settings.word_timestamps,
    )
    return LocalTranscriptionPipeline(
        media_preparer=FfmpegAudioExtractor(sample_rate=settings.sample_rate),
        transcriber=provider.build_transcriber(provider_settings),
        artifact_writer=TranscriptArtifactWriter(
            formats=job.output_formats,
            txt_writer=TxtTranscriptWriter(path_builder),
            md_writer=MarkdownTranscriptWriter(
                path_builder,
                include_timestamps=job.timestamps,
            ),
            json_writer=JsonTranscriptWriter(path_builder),
            srt_writer=SrtTranscriptWriter(path_builder),
            vtt_writer=VttTranscriptWriter(path_builder),
        ),
        work_dir=settings.work_dir,
        output_dir=settings.output_dir,
        keep_audio=settings.keep_audio,
        transcript_normalizer=(
            simplify_chinese_transcript
            if settings.language == "zh" or settings.preset == "zh"
            else None
        ),
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
