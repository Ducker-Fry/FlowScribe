"""Pipeline orchestration for local media transcription."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from pathlib import Path
from typing import Any

from flowscribe.core.models import (
    MediaDurationInfo,
    MediaItem,
    OutputArtifacts,
    PreparedAudio,
    ProgressiveTranscriptionState,
    ProgressiveTranscriptionUpdate,
    Transcript,
    TranscriptionChunkPlan,
)
from flowscribe.core.deduplication import TranscriptDeduplicator
from flowscribe.core.progressive import (
    FixedDurationChunkPlanner,
    ProgressiveChunkCache,
    ProgressiveTranscriptConsistencyChecker,
    PreparedAudioDurationProbe,
    ProgressiveTranscriptionExecutor,
)
from flowscribe.core.ports import ArtifactWriter, MediaPreparer, Transcriber
from flowscribe.media.audio_extractor import PreparedAudioCache


class LocalTranscriptionPipeline:
    def __init__(
        self,
        *,
        media_preparer: MediaPreparer,
        transcriber: Transcriber,
        artifact_writer: ArtifactWriter,
        work_dir: Path,
        output_dir: Path,
        keep_audio: bool = False,
        prepared_audio_cache_dir: Path | None = None,
        transcript_normalizer: Callable[[Transcript], Transcript] | None = None,
        enable_deduplication: bool = True,
    ) -> None:
        self._media_preparer = media_preparer
        self._transcriber = transcriber
        self._artifact_writer = artifact_writer
        self._work_dir = work_dir
        self._output_dir = output_dir
        self._keep_audio = keep_audio
        self._transcript_normalizer = transcript_normalizer
        self._enable_deduplication = enable_deduplication
        self._deduplicator = TranscriptDeduplicator() if enable_deduplication else None
        self._audio_cache = (
            PreparedAudioCache(prepared_audio_cache_dir)
            if prepared_audio_cache_dir is not None
            else None
        )

    def _prepare_or_cache(self, item: MediaItem, work_dir: Path) -> PreparedAudio:
        if self._audio_cache is not None:
            cached = self._audio_cache.get(item)
            if cached is not None:
                return cached
        prepared = self._media_preparer.prepare(item, work_dir)
        if self._audio_cache is not None:
            self._audio_cache.put(prepared)
        return prepared

    def process(
        self,
        item: MediaItem,
        *,
        should_cancel: Callable[[], bool] | None = None,
        progress: Callable[[Any], None] | None = None,
    ) -> OutputArtifacts:
        transcript = self.build_transcript(
            item,
            should_cancel=should_cancel,
            progress=progress,
        )
        return self._artifact_writer.write_all(transcript, self._output_dir)

    def build_transcript(
        self,
        item: MediaItem,
        *,
        should_cancel: Callable[[], bool] | None = None,
        progress: Callable[[Any], None] | None = None,
    ) -> Transcript:
        item_work_dir = self._work_dir / item.path.stem
        prepared_audio = self._prepare_or_cache(item, item_work_dir)
        try:
            kwargs = {"should_cancel": should_cancel}
            if progress is not None and _transcriber_accepts_progress(self._transcriber):
                kwargs["progress"] = progress
            transcript = self._transcriber.transcribe(prepared_audio, **kwargs)
            if self._transcript_normalizer is not None:
                transcript = self._transcript_normalizer(transcript)
            if self._deduplicator is not None:
                transcript = self._deduplicator.deduplicate(transcript)
            return transcript
        finally:
            if not self._keep_audio:
                prepared_audio.path.unlink(missing_ok=True)

    def build_progressive_transcript(
        self,
        item: MediaItem,
        *,
        chunk_duration_seconds: float = 30.0,
        chunk_overlap_seconds: float = 3.0,
        resume: bool = False,
        keep_progressive_cache: bool = True,
        max_workers: int = 1,
        max_failed_chunks: int = 3,
        plan_callback: Callable[[MediaDurationInfo, TranscriptionChunkPlan], None] | None = None,
        update_callback: Callable[[ProgressiveTranscriptionUpdate], None] | None = None,
        should_cancel: Callable[[], bool] | None = None,
    ) -> ProgressiveTranscriptionState:
        item_work_dir = self._work_dir / item.path.stem
        cache_store = ProgressiveChunkCache(item_work_dir / ".progressive")
        prepared_audio = self._prepare_or_cache(item, item_work_dir)
        try:
            duration_info = PreparedAudioDurationProbe().probe(prepared_audio)
            chunk_plan = FixedDurationChunkPlanner(
                chunk_duration_seconds=chunk_duration_seconds,
                chunk_overlap_seconds=chunk_overlap_seconds,
            ).plan(duration_info)
            if plan_callback is not None:
                plan_callback(duration_info, chunk_plan)
            executor = ProgressiveTranscriptionExecutor(transcriber=self._transcriber)
            state = executor.execute(
                prepared_audio,
                chunk_plan,
                cache_store=cache_store,
                resume=resume,
                max_workers=max_workers,
                max_failed_chunks=max_failed_chunks,
                update_callback=update_callback,
                should_cancel=should_cancel,
            )
            transcript = state.transcript
            if self._transcript_normalizer is not None:
                transcript = self._transcript_normalizer(transcript)
                transcript = ProgressiveTranscriptConsistencyChecker().validate(transcript)
            if self._deduplicator is not None:
                transcript = self._deduplicator.deduplicate(transcript)
            if self._transcript_normalizer is not None or self._deduplicator is not None:
                state = ProgressiveTranscriptionState(
                    source=state.source,
                    duration_info=state.duration_info,
                    chunk_plan=state.chunk_plan,
                    chunk_results=state.chunk_results,
                    transcript=transcript,
                    processed_duration_seconds=state.processed_duration_seconds,
                    cache_dir=state.cache_dir,
                )
            if not keep_progressive_cache:
                cache_store.clear()
                state = ProgressiveTranscriptionState(
                    source=state.source,
                    duration_info=state.duration_info,
                    chunk_plan=state.chunk_plan,
                    chunk_results=state.chunk_results,
                    transcript=state.transcript,
                    processed_duration_seconds=state.processed_duration_seconds,
                    cache_dir=None,
                )
            return state
        finally:
            if not self._keep_audio:
                prepared_audio.path.unlink(missing_ok=True)

    def process_progressive(
        self,
        item: MediaItem,
        *,
        chunk_duration_seconds: float = 30.0,
        chunk_overlap_seconds: float = 3.0,
        resume: bool = False,
        keep_progressive_cache: bool = True,
        max_workers: int = 1,
        max_failed_chunks: int = 3,
        plan_callback: Callable[[MediaDurationInfo, TranscriptionChunkPlan], None] | None = None,
        update_callback: Callable[[ProgressiveTranscriptionUpdate], None] | None = None,
        should_cancel: Callable[[], bool] | None = None,
    ) -> tuple[OutputArtifacts, ProgressiveTranscriptionState]:
        state = self.build_progressive_transcript(
            item,
            chunk_duration_seconds=chunk_duration_seconds,
            chunk_overlap_seconds=chunk_overlap_seconds,
            resume=resume,
            keep_progressive_cache=keep_progressive_cache,
            max_workers=max_workers,
            max_failed_chunks=max_failed_chunks,
            plan_callback=plan_callback,
            update_callback=update_callback,
            should_cancel=should_cancel,
        )
        return self._artifact_writer.write_all(state.transcript, self._output_dir), state

    def clear_progressive_cache(self, item: MediaItem) -> None:
        ProgressiveChunkCache((self._work_dir / item.path.stem) / ".progressive").clear()


def _transcriber_accepts_progress(transcriber: Transcriber) -> bool:
    try:
        signature = inspect.signature(transcriber.transcribe)
    except (TypeError, ValueError):
        return False
    return "progress" in signature.parameters
