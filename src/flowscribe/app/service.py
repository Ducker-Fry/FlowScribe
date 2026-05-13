"""Application service for running transcription jobs."""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

from flowscribe.app.models import (
    ErrorInfo,
    ProgressCallback,
    ProgressEvent,
    SourceSpec,
    TranscriptionJob,
    TranscriptionResult,
)
from flowscribe.config.settings import AppSettings
from flowscribe.core.errors import FlowScribeError
from flowscribe.core.models import MediaItem, OutputArtifacts
from flowscribe.core.pipeline import LocalTranscriptionPipeline
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
from flowscribe.transcription.local_whisper import LocalWhisperTranscriber


class TranscriptionService:
    """Run transcription jobs through a stable app-facing interface."""

    def run(
        self,
        job: TranscriptionJob,
        progress: ProgressCallback | None = None,
    ) -> TranscriptionResult:
        progress = progress or (lambda event: None)
        started_at = datetime.now()
        outputs: list[OutputArtifacts] = []
        errors: list[ErrorInfo] = []

        progress(
            ProgressEvent(
                stage="discover",
                message=f"Received {len(job.sources)} source(s).",
                total=len(job.sources),
            )
        )

        for index, source in enumerate(job.sources, start=1):
            source_outputs, source_errors = self._run_source(
                job,
                source,
                progress,
                index,
                len(job.sources),
            )
            outputs.extend(source_outputs)
            errors.extend(source_errors)

        progress(
            ProgressEvent(
                stage="complete",
                message=f"Done. Succeeded: {len(outputs)}. Failed: {len(errors)}.",
                total=len(job.sources),
            )
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
        current: int,
        total: int,
    ) -> tuple[tuple[OutputArtifacts, ...], tuple[ErrorInfo, ...]]:
        try:
            if source.kind == "local":
                return self._run_local_source(job, source, progress, current, total)
            if source.kind == "url":
                return (self._run_url_source(job, source, progress, current, total),), ()
            if source.kind == "capture":
                raise FlowScribeError("System audio capture source is planned but not implemented yet.")
            raise FlowScribeError(f"Unsupported source kind: {source.kind}")
        except FlowScribeError as exc:
            error = _error_from_exception(exc, source=source.value)
            progress(
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
        current: int,
        total: int,
    ) -> tuple[tuple[OutputArtifacts, ...], tuple[ErrorInfo, ...]]:
        settings = _settings_from_job(job, recursive=source.recursive)
        pipeline = _build_pipeline(job, settings)
        input_source = LocalFileSource([Path(source.value)], recursive=settings.recursive)
        items = input_source.discover()
        outputs: list[OutputArtifacts] = []
        errors: list[ErrorInfo] = []

        progress(
            ProgressEvent(
                stage="discover",
                message=f"Discovered {len(items)} media file(s).",
                source=source.value,
                current=current,
                total=total,
            )
        )
        for item_index, item in enumerate(items, start=1):
            progress(
                ProgressEvent(
                    stage="transcribe",
                    message=f"Processing {item.path}",
                    source=str(item.path),
                    current=item_index,
                    total=len(items),
                )
            )
            try:
                artifacts = pipeline.process(item)
            except FlowScribeError as exc:
                errors.append(_error_from_exception(exc, source=str(item.path)))
                progress(
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
                progress(
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
        )

        progress(
            ProgressEvent(
                stage="download",
                message="Downloading/extracting remote audio...",
                source=source.value,
                current=current,
                total=total,
            )
        )
        download = downloader.download_audio(source.value)
        try:
            progress(
                ProgressEvent(
                    stage="prepare",
                    message=f"Remote audio ready: {download.path}",
                    source=source.value,
                    path=download.path,
                )
            )
            pipeline = _build_pipeline(job, settings)
            artifacts = pipeline.process(MediaItem(path=download.path))
            for path in artifacts.paths:
                progress(
                    ProgressEvent(
                        stage="write",
                        message=f"Wrote: {path}",
                        source=source.value,
                        path=path,
                    )
                )
        finally:
            if not source.keep_media:
                shutil.rmtree(download.cleanup_dir, ignore_errors=True)
        return artifacts


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
    path_builder = OutputPathBuilder(overwrite=settings.overwrite)
    return LocalTranscriptionPipeline(
        media_preparer=FfmpegAudioExtractor(sample_rate=settings.sample_rate),
        transcriber=LocalWhisperTranscriber(
            model_name=settings.model_name,
            language=settings.language,
            task=settings.task,
            beam_size=settings.beam_size,
            vad_filter=settings.vad_filter,
            initial_prompt=settings.initial_prompt,
            preset=settings.preset,
            word_timestamps=settings.word_timestamps,
        ),
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
