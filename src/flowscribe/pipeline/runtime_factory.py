"""Shared factories for task-to-pipeline runtime construction."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from dataclasses import replace

from flowscribe.config.settings import AppSettings
from flowscribe.core.models import MediaItem, OutputArtifacts
from flowscribe.media.audio_extractor import FfmpegAudioExtractor
from flowscribe.nlp.script_converter import simplify_chinese_transcript
from flowscribe.output.artifact_writer import TranscriptArtifactWriter
from flowscribe.output.json_writer import JsonTranscriptWriter
from flowscribe.output.md_writer import MarkdownTranscriptWriter
from flowscribe.output.paths import OutputPathBuilder
from flowscribe.output.srt_writer import SrtTranscriptWriter
from flowscribe.output.txt_writer import TxtTranscriptWriter
from flowscribe.output.vtt_writer import VttTranscriptWriter
from flowscribe.pipeline.transcription import LocalTranscriptionPipeline
from flowscribe.providers.transcribe.registry import (
    ProviderTranscriptionSettings,
    TranscriptionProvider,
    resolve_transcription_provider,
)
from flowscribe.tasks.models import ProgressEvent, TranscriptionJob


def settings_from_job(job: TranscriptionJob, *, recursive: bool) -> AppSettings:
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


def build_transcription_pipeline(job: TranscriptionJob, settings: AppSettings) -> LocalTranscriptionPipeline:
    provider = resolve_transcription_provider(job.provider_name)
    provider_settings = ProviderTranscriptionSettings(
        model_name=settings.model_name,
        language=settings.language,
        task=settings.task,
        beam_size=settings.beam_size,
        vad_filter=settings.vad_filter,
        initial_prompt=settings.initial_prompt,
        preset=settings.preset,
        word_timestamps=settings.word_timestamps,
        progressive_enabled=job.progressive_enabled,
        progressive_resume_requested=job.progressive_resume,
        progressive_chunk_seconds=job.progressive_chunk_seconds,
        progressive_chunk_overlap_seconds=job.progressive_chunk_overlap_seconds,
        progressive_max_workers=job.progressive_max_workers,
        native_threads=job.native_threads,
    )
    return build_pipeline_from_provider(
        job,
        settings,
        provider=provider,
        provider_settings=provider_settings,
    )


def build_pipeline_from_provider(
    job: TranscriptionJob,
    settings: AppSettings,
    *,
    provider: TranscriptionProvider,
    provider_settings: ProviderTranscriptionSettings,
) -> LocalTranscriptionPipeline:
    path_builder = OutputPathBuilder(
        overwrite=settings.overwrite,
        base_name=job.output_name_base,
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
        transcript_enricher=lambda transcript, item: replace(
            transcript,
            task_id=job.task_id,
            resume_token=job.resume_token,
            checkpoint_id=job.checkpoint_id,
        ),
    )


def process_with_optional_progress(
    pipeline,
    item: MediaItem,
    *,
    should_cancel: Callable[[], bool],
    progress: Callable[[ProgressEvent], None] | None,
) -> OutputArtifacts:
    if progress is None or not callable_accepts_keyword(pipeline.process, "progress"):
        return pipeline.process(item, should_cancel=should_cancel)
    return pipeline.process(item, should_cancel=should_cancel, progress=progress)


def callable_accepts_keyword(func, name: str) -> bool:
    try:
        signature = inspect.signature(func)
    except (TypeError, ValueError):
        return False
    return name in signature.parameters
