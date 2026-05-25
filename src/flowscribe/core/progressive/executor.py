"""Progressive transcription execution - chunk processing, caching, and state management."""

from __future__ import annotations

import json
import os
import shutil
import time
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Callable

from flowscribe.core.errors import TranscriptionError
from flowscribe.core.models import (
    ChunkTranscriptionResult,
    MediaItem,
    PreparedAudio,
    ProgressiveTranscriptionState,
    ProgressiveTranscriptionUpdate,
    Transcript,
    TranscriptSegment,
    TranscriptWord,
    TranscriptionChunk,
    TranscriptionChunkPlan,
    TranscriptionOptions,
)
from flowscribe.core.progressive.merger import (
    ChunkMergePolicy,
    ConservativeChunkMergePolicy,
    ProgressiveTranscriptConsistencyChecker,
)
from flowscribe.core.progressive.planner import ClipTranscriber


class ProgressiveTranscriptionExecutor:
    """Run serial chunk transcription and merge the results conservatively."""

    def __init__(
        self,
        *,
        transcriber: ClipTranscriber,
        merge_policy: ChunkMergePolicy | None = None,
        consistency_checker: ProgressiveTranscriptConsistencyChecker | None = None,
    ) -> None:
        self._transcriber = transcriber
        self._merge_policy = merge_policy or ConservativeChunkMergePolicy()
        self._consistency_checker = consistency_checker or ProgressiveTranscriptConsistencyChecker()

    def execute(
        self,
        audio: PreparedAudio,
        chunk_plan: TranscriptionChunkPlan,
        *,
        cache_store: ProgressiveChunkCache | None = None,
        resume: bool = False,
        max_workers: int = 1,
        max_failed_chunks: int = 0,
        update_callback: Callable[[ProgressiveTranscriptionUpdate], None] | None = None,
        should_cancel: Callable[[], bool] | None = None,
    ) -> ProgressiveTranscriptionState:
        if cache_store is not None:
            cache_store.prepare(chunk_plan, resume=resume)
        cached_results_by_index = (
            cache_store.load_completed_results(chunk_plan) if cache_store is not None and resume else {}
        )
        chunk_results: list[ChunkTranscriptionResult] = []
        merged_segments: list[TranscriptSegment] = []
        processed_duration_seconds = 0.0
        failed_count = 0
        first_transcript: Transcript | None = None
        chunk_lookup = {chunk.index: chunk for chunk in chunk_plan.chunks}
        pending_chunks = [
            chunk
            for chunk in chunk_plan.chunks
            if chunk.index not in cached_results_by_index
        ]
        completed_results_by_index: dict[int, ChunkTranscriptionResult] = dict(cached_results_by_index)
        for update in self._yield_updates(
            audio=audio,
            chunk_plan=chunk_plan,
            pending_chunks=pending_chunks,
            completed_results_by_index=completed_results_by_index,
            cached_results_by_index=cached_results_by_index,
            max_workers=max_workers,
            should_cancel=should_cancel,
        ):
            if should_cancel is not None and should_cancel():
                from flowscribe.core.errors import CancellationError
                raise CancellationError("Progressive transcription canceled.")

            chunk = chunk_lookup[update.chunk_result.chunk.index]
            result = update.chunk_result
            if result.status == "failed":
                retried = self._retry_one_chunk(audio, chunk, result, should_cancel=should_cancel)
                if retried.status == "done":
                    update = ProgressiveTranscriptionUpdate(
                        state=update.state,
                        chunk_result=retried,
                        appended_segments=(),
                        resumed=False,
                    )
                    result = retried
                else:
                    failed_count += 1
                    chunk_results.append(result)
                    if cache_store is not None:
                        cache_store.save_chunk_result(result)
                    if failed_count > max_failed_chunks:
                        if cache_store is not None:
                            cache_store.save_state(
                                chunk_plan=chunk_plan,
                                transcript=self._build_partial_transcript(
                                    audio=audio,
                                    first_transcript=first_transcript,
                                    merged_segments=merged_segments,
                                ),
                                chunk_results=tuple(chunk_results),
                                processed_duration_seconds=processed_duration_seconds,
                                status="failed",
                                error_message=result.error_message,
                            )
                        raise TranscriptionError(
                            f"Progressive transcription failed for {audio.path} "
                            f"chunk {chunk.index} ({failed_count} total failures): "
                            f"{result.error_message}"
                        )
                    continue

            chunk_results.append(result)
            first_transcript = first_transcript or result.transcript
            appended_segments = self._merge_policy.merge(
                existing_segments=merged_segments,
                chunk_segments=result.transcript.segments,
                chunk=chunk,
                transcript=result.transcript,
            )
            merged_segments.extend(appended_segments)
            processed_duration_seconds += chunk.content_duration_seconds
            partial_transcript = self._build_partial_transcript(
                audio=audio,
                first_transcript=first_transcript,
                merged_segments=merged_segments,
            )
            partial_transcript = self._consistency_checker.validate(partial_transcript)
            partial_state = ProgressiveTranscriptionState(
                source=audio.source,
                duration_info=chunk_plan.duration_info,
                chunk_plan=chunk_plan,
                chunk_results=tuple(chunk_results),
                transcript=partial_transcript,
                processed_duration_seconds=min(
                    processed_duration_seconds,
                    chunk_plan.duration_info.duration_seconds or processed_duration_seconds,
                ),
                cache_dir=None if cache_store is None else cache_store.cache_dir,
            )
            if cache_store is not None:
                cache_store.save_chunk_result(result)
                cache_store.save_state(
                    chunk_plan=chunk_plan,
                    transcript=partial_transcript,
                    chunk_results=partial_state.chunk_results,
                    processed_duration_seconds=partial_state.processed_duration_seconds,
                    status="running",
                )
            if update_callback is not None:
                update_callback(
                    ProgressiveTranscriptionUpdate(
                        state=partial_state,
                        chunk_result=result,
                        appended_segments=tuple(appended_segments),
                        resumed=update.resumed,
                    )
                )
        if first_transcript is None:
            raise TranscriptionError(f"Progressive transcription produced no transcript for {audio.path}.")

        final_transcript = self._build_partial_transcript(
            audio=audio,
            first_transcript=first_transcript,
            merged_segments=merged_segments,
        )
        final_transcript = self._consistency_checker.validate(final_transcript)
        state = ProgressiveTranscriptionState(
            source=audio.source,
            duration_info=chunk_plan.duration_info,
            chunk_plan=chunk_plan,
            chunk_results=tuple(chunk_results),
            transcript=final_transcript,
            processed_duration_seconds=min(
                processed_duration_seconds,
                chunk_plan.duration_info.duration_seconds or processed_duration_seconds,
            ),
            cache_dir=None if cache_store is None else cache_store.cache_dir,
        )
        if cache_store is not None:
            cache_store.save_state(
                chunk_plan=chunk_plan,
                transcript=final_transcript,
                chunk_results=state.chunk_results,
                processed_duration_seconds=state.processed_duration_seconds,
                status="completed",
            )
        return state

    def _yield_updates(
        self,
        *,
        audio: PreparedAudio,
        chunk_plan: TranscriptionChunkPlan,
        pending_chunks: list[TranscriptionChunk],
        completed_results_by_index: dict[int, ChunkTranscriptionResult],
        cached_results_by_index: dict[int, ChunkTranscriptionResult],
        max_workers: int,
        should_cancel: Callable[[], bool] | None = None,
    ):
        next_expected_index = 1
        while next_expected_index in completed_results_by_index:
            result = completed_results_by_index.pop(next_expected_index)
            yield ProgressiveTranscriptionUpdate(
                state=self._empty_state(audio, chunk_plan),
                chunk_result=result,
                appended_segments=(),
                resumed=next_expected_index in cached_results_by_index,
            )
            next_expected_index += 1

        if not pending_chunks:
            return

        effective_workers = self._resolve_max_workers(max_workers=max_workers)
        if effective_workers <= 1 or len(pending_chunks) <= 1:
            for chunk in pending_chunks:
                if should_cancel is not None and should_cancel():
                    from flowscribe.core.errors import CancellationError
                    raise CancellationError("Progressive transcription canceled.")
                result = self._transcribe_one_chunk(audio, chunk, transcriber=self._transcriber, should_cancel=should_cancel)
                completed_results_by_index[chunk.index] = result
                while next_expected_index in completed_results_by_index:
                    ready_result = completed_results_by_index.pop(next_expected_index)
                    yield ProgressiveTranscriptionUpdate(
                        state=self._empty_state(audio, chunk_plan),
                        chunk_result=ready_result,
                        appended_segments=(),
                        resumed=False,
                    )
                    next_expected_index += 1
            return

        worker_transcribers = [self._transcriber]
        for _ in range(effective_workers - 1):
            worker_transcribers.append(self._fork_transcriber())

        with ThreadPoolExecutor(max_workers=effective_workers) as pool:
            futures: dict[Future, TranscriptionChunk] = {}
            for index, chunk in enumerate(pending_chunks):
                transcriber = worker_transcribers[index % len(worker_transcribers)]
                future = pool.submit(self._transcribe_one_chunk, audio, chunk, transcriber)
                futures[future] = chunk

            while futures:
                done, _ = wait(tuple(futures), return_when=FIRST_COMPLETED)
                for future in done:
                    chunk = futures.pop(future)
                    result = future.result()
                    completed_results_by_index[chunk.index] = result
                    while next_expected_index in completed_results_by_index:
                        ready_result = completed_results_by_index.pop(next_expected_index)
                        yield ProgressiveTranscriptionUpdate(
                            state=self._empty_state(audio, chunk_plan),
                            chunk_result=ready_result,
                            appended_segments=(),
                            resumed=False,
                        )
                        next_expected_index += 1

    @staticmethod
    def _empty_state(audio: PreparedAudio, chunk_plan: TranscriptionChunkPlan) -> ProgressiveTranscriptionState:
        return ProgressiveTranscriptionState(
            source=audio.source,
            duration_info=chunk_plan.duration_info,
            chunk_plan=chunk_plan,
            chunk_results=(),
            transcript=Transcript(source=audio.source, segments=()),
            processed_duration_seconds=0.0,
        )

    def _resolve_max_workers(self, *, max_workers: int) -> int:
        """Resolve max workers based on CPU count and available memory.

        Each worker loads a model copy (~500MB-2GB depending on model size).
        We dynamically calculate safe worker count based on available memory.
        """
        requested = max(1, int(max_workers))
        cpu_count = max(1, os.cpu_count() or 1)

        # Check if transcriber supports forking
        if not hasattr(self._transcriber, "fork_for_worker"):
            return 1

        # Calculate memory-based limit
        memory_limit = self._calculate_memory_based_worker_limit()

        # Use minimum of requested, CPU count, and memory-based limit
        capped = min(requested, cpu_count, memory_limit)
        return max(1, capped)

    def _calculate_memory_based_worker_limit(self) -> int:
        """Calculate safe worker count based on available memory.

        Estimates model memory usage and ensures we don't exceed 80% of available memory.
        Returns conservative limit if memory info unavailable.
        """
        try:
            import psutil

            # Get available memory in GB
            available_gb = psutil.virtual_memory().available / (1024 ** 3)

            # Estimate model memory usage based on model name
            model_name = getattr(self._transcriber, "_model_name", "small")
            model_memory_gb = self._estimate_model_memory(model_name)

            # Reserve 20% of available memory for system and other processes
            usable_memory_gb = available_gb * 0.8

            # Calculate how many workers can fit
            max_workers = int(usable_memory_gb / model_memory_gb)

            # Return at least 1, at most 8 (reasonable upper bound)
            return max(1, min(max_workers, 8))
        except ImportError:
            # psutil not available, use conservative default
            return 2
        except Exception:
            # Any error, use conservative default
            return 2

    def _estimate_model_memory(self, model_name: str) -> float:
        """Estimate model memory usage in GB.

        Based on typical faster-whisper model sizes with int8 quantization.
        """
        memory_map = {
            "tiny": 0.5,
            "base": 0.7,
            "small": 1.0,
            "medium": 1.5,
            "large-v3-turbo": 1.8,
            "large-v3": 2.5,
        }
        # Default to medium estimate if model not recognized
        return memory_map.get(model_name, 1.5)

    def _fork_transcriber(self):
        fork = getattr(self._transcriber, "fork_for_worker", None)
        if callable(fork):
            return fork()
        return self._transcriber

    def _transcribe_one_chunk(
        self,
        audio: PreparedAudio,
        chunk: TranscriptionChunk,
        transcriber,
        *,
        should_cancel: Callable[[], bool] | None = None,
    ) -> ChunkTranscriptionResult:
        if should_cancel is not None and should_cancel():
            from flowscribe.core.errors import CancellationError
            raise CancellationError("Progressive transcription canceled.")

        started_at = time.perf_counter()
        try:
            transcript = transcriber.transcribe_clip(
                audio,
                start_seconds=chunk.start_seconds,
                end_seconds=chunk.end_seconds,
                should_cancel=should_cancel,
            )
        except Exception as exc:
            elapsed_seconds = time.perf_counter() - started_at
            return ChunkTranscriptionResult(
                chunk=chunk,
                status="failed",
                elapsed_seconds=elapsed_seconds,
                error_message=str(exc),
            )

        elapsed_seconds = time.perf_counter() - started_at
        normalized_transcript = self._normalize_chunk_transcript(transcript, chunk=chunk)

        # Validate first chunk segments start near beginning
        if chunk.index == 1:
            normalized_transcript = self._validate_first_chunk_segments(
                normalized_transcript, chunk=chunk, audio=audio
            )

        trimmed_segments = self._merge_policy.merge(
            existing_segments=[],
            chunk_segments=normalized_transcript.segments,
            chunk=chunk,
            transcript=normalized_transcript,
        )
        return ChunkTranscriptionResult(
            chunk=chunk,
            status="done",
            transcript=normalized_transcript,
            elapsed_seconds=elapsed_seconds,
            merged_segment_count=len(trimmed_segments),
        )

    @staticmethod
    def _validate_first_chunk_segments(
        transcript: Transcript,
        *,
        chunk: TranscriptionChunk,
        audio: PreparedAudio,
    ) -> Transcript:
        """
        Validate that first chunk segments start near the beginning.

        Bug fix: Sometimes Whisper skips the first N seconds of audio,
        resulting in segments starting at e.g. 28s instead of 0s.
        This validation detects the issue and logs a warning.
        """
        if not transcript.segments:
            return transcript

        first_segment = transcript.segments[0]
        if first_segment.start_seconds is None:
            return transcript

        # Check if first segment starts suspiciously late (> 5 seconds)
        # This threshold allows for initial silence but catches real content loss
        LATE_START_THRESHOLD_SECONDS = 5.0

        if first_segment.start_seconds > LATE_START_THRESHOLD_SECONDS:
            # Log warning about potential content loss
            import warnings
            warnings.warn(
                f"First chunk of {audio.source.path.name} has segments starting at "
                f"{first_segment.start_seconds:.1f}s instead of near 0s. "
                f"This may indicate missing content at the beginning. "
                f"Possible causes: VAD filter, initial silence, or Whisper model issue. "
                f"Consider re-transcribing without VAD filter or checking the audio file.",
                UserWarning,
                stacklevel=2,
            )

        return transcript

    @staticmethod
    def _build_partial_transcript(
        *,
        audio: PreparedAudio,
        first_transcript: Transcript | None,
        merged_segments: list[TranscriptSegment],
    ) -> Transcript:
        if first_transcript is None:
            return Transcript(source=audio.source, segments=())
        return Transcript(
            source=audio.source,
            segments=tuple(merged_segments),
            language=first_transcript.language,
            model_name=first_transcript.model_name,
            options=first_transcript.options,
            created_at=first_transcript.created_at,
        )

    def _retry_one_chunk(
        self,
        audio: PreparedAudio,
        chunk: TranscriptionChunk,
        previous_result: ChunkTranscriptionResult,
        *,
        should_cancel: Callable[[], bool] | None = None,
    ) -> ChunkTranscriptionResult:
        """Retry a failed chunk once and return the result."""
        try:
            return self._transcribe_one_chunk(audio, chunk, transcriber=self._transcriber, should_cancel=should_cancel)
        except Exception as exc:
            return ChunkTranscriptionResult(
                chunk=chunk,
                status="failed",
                elapsed_seconds=previous_result.elapsed_seconds,
                error_message=str(exc),
            )

    @staticmethod
    def _normalize_chunk_transcript(transcript: Transcript, *, chunk: TranscriptionChunk) -> Transcript:
        chunk_duration_seconds = chunk.duration_seconds
        starts = [
            segment.start_seconds
            for segment in transcript.segments
            if segment.start_seconds is not None
        ]
        ends = [
            segment.end_seconds
            for segment in transcript.segments
            if segment.end_seconds is not None
        ]
        if starts and ends:
            max_end_seconds = max(ends)
            min_start_seconds = min(starts)
            if min_start_seconds >= 0.0 and max_end_seconds <= chunk_duration_seconds + 0.25:
                offset_seconds = chunk.start_seconds
                return Transcript(
                    source=transcript.source,
                    segments=tuple(
                        ProgressiveTranscriptionExecutor._offset_segment(segment, offset_seconds)
                        for segment in transcript.segments
                    ),
                    language=transcript.language,
                    model_name=transcript.model_name,
                    options=transcript.options,
                    created_at=transcript.created_at,
                )
        return transcript

    @staticmethod
    def _offset_segment(segment: TranscriptSegment, offset_seconds: float) -> TranscriptSegment:
        return replace(
            segment,
            start_seconds=(
                None if segment.start_seconds is None else segment.start_seconds + offset_seconds
            ),
            end_seconds=None if segment.end_seconds is None else segment.end_seconds + offset_seconds,
            raw_words=tuple(
                replace(
                    word,
                    start_seconds=(
                        None if word.start_seconds is None else word.start_seconds + offset_seconds
                    ),
                    end_seconds=(
                        None if word.end_seconds is None else word.end_seconds + offset_seconds
                    ),
                )
                for word in segment.raw_words
            ),
            words=tuple(
                replace(
                    word,
                    start_seconds=(
                        None if word.start_seconds is None else word.start_seconds + offset_seconds
                    ),
                    end_seconds=(
                        None if word.end_seconds is None else word.end_seconds + offset_seconds
                    ),
                )
                for word in segment.words
            ),
        )


class ProgressiveChunkCache:
    """Persist progressive chunk state for resume and recovery."""

    def __init__(self, cache_dir: Path) -> None:
        self.cache_dir = cache_dir
        self._chunk_results_dir = self.cache_dir / "chunk-results"
        self._plan_path = self.cache_dir / "chunk-plan.json"
        self._state_path = self.cache_dir / "state.json"
        self._partial_transcript_path = self.cache_dir / "partial-transcript.json"

    def prepare(self, chunk_plan: TranscriptionChunkPlan, *, resume: bool) -> None:
        if resume and self._plan_matches(chunk_plan):
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            self._chunk_results_dir.mkdir(parents=True, exist_ok=True)
            return
        self.clear()
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._chunk_results_dir.mkdir(parents=True, exist_ok=True)
        self._write_json(self._plan_path, self._serialize_chunk_plan(chunk_plan))

    def clear(self) -> None:
        shutil.rmtree(self.cache_dir, ignore_errors=True)

    def load_completed_results(
        self,
        chunk_plan: TranscriptionChunkPlan,
    ) -> dict[int, ChunkTranscriptionResult]:
        if not self._plan_matches(chunk_plan):
            return {}
        results: dict[int, ChunkTranscriptionResult] = {}
        for chunk in chunk_plan.chunks:
            path = self._chunk_result_path(chunk.index)
            if not path.exists():
                continue
            payload = self._read_json(path)
            result = self._deserialize_chunk_result(payload, source=chunk_plan.duration_info.source)
            if result.status == "done" and result.transcript is not None:
                results[chunk.index] = result
        return results

    def save_chunk_result(self, result: ChunkTranscriptionResult) -> None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._chunk_results_dir.mkdir(parents=True, exist_ok=True)
        self._write_json(
            self._chunk_result_path(result.chunk.index),
            self._serialize_chunk_result(result),
        )

    def save_state(
        self,
        *,
        chunk_plan: TranscriptionChunkPlan,
        transcript: Transcript,
        chunk_results: tuple[ChunkTranscriptionResult, ...],
        processed_duration_seconds: float,
        status: str,
        error_message: str | None = None,
    ) -> None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._write_json(self._partial_transcript_path, self._serialize_transcript(transcript))
        self._write_json(
            self._state_path,
            {
                "status": status,
                "error_message": error_message,
                "processed_duration_seconds": processed_duration_seconds,
                "completed_chunks": sum(1 for result in chunk_results if result.status == "done"),
                "chunk_count": len(chunk_plan.chunks),
                "source": str(chunk_plan.duration_info.source.path),
                "updated_at": datetime.now().isoformat(timespec="seconds"),
            },
        )

    def _plan_matches(self, chunk_plan: TranscriptionChunkPlan) -> bool:
        if not self._plan_path.exists():
            return False
        existing = self._read_json(self._plan_path)
        return existing == self._serialize_chunk_plan(chunk_plan)

    def _chunk_result_path(self, chunk_index: int) -> Path:
        return self._chunk_results_dir / f"chunk-{chunk_index:04d}.json"

    @staticmethod
    def _write_json(path: Path, payload: dict) -> None:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    @staticmethod
    def _read_json(path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _serialize_chunk_plan(chunk_plan: TranscriptionChunkPlan) -> dict:
        duration_info = chunk_plan.duration_info
        return {
            "source": str(duration_info.source.path),
            "prepared_audio_path": str(duration_info.prepared_audio_path),
            "sample_rate": duration_info.sample_rate,
            "duration_seconds": duration_info.duration_seconds,
            "chunk_duration_seconds": chunk_plan.chunk_duration_seconds,
            "chunk_overlap_seconds": chunk_plan.chunk_overlap_seconds,
            "chunks": [
                {
                    "index": chunk.index,
                    "start_seconds": chunk.start_seconds,
                    "end_seconds": chunk.end_seconds,
                    "overlap_seconds": chunk.overlap_seconds,
                }
                for chunk in chunk_plan.chunks
            ],
        }

    @staticmethod
    def _serialize_chunk_result(result: ChunkTranscriptionResult) -> dict:
        return {
            "chunk": {
                "index": result.chunk.index,
                "start_seconds": result.chunk.start_seconds,
                "end_seconds": result.chunk.end_seconds,
                "overlap_seconds": result.chunk.overlap_seconds,
            },
            "status": result.status,
            "elapsed_seconds": result.elapsed_seconds,
            "error_message": result.error_message,
            "merged_segment_count": result.merged_segment_count,
            "transcript": None
            if result.transcript is None
            else ProgressiveChunkCache._serialize_transcript(result.transcript),
        }

    @staticmethod
    def _deserialize_chunk_result(payload: dict, *, source: MediaItem) -> ChunkTranscriptionResult:
        chunk_payload = payload["chunk"]
        transcript_payload = payload.get("transcript")
        return ChunkTranscriptionResult(
            chunk=TranscriptionChunk(
                index=int(chunk_payload["index"]),
                start_seconds=float(chunk_payload["start_seconds"]),
                end_seconds=float(chunk_payload["end_seconds"]),
                overlap_seconds=float(chunk_payload.get("overlap_seconds", 0.0)),
            ),
            status=payload["status"],
            transcript=(
                None
                if transcript_payload is None
                else ProgressiveChunkCache._deserialize_transcript(transcript_payload, source=source)
            ),
            elapsed_seconds=payload.get("elapsed_seconds"),
            error_message=payload.get("error_message"),
            merged_segment_count=int(payload.get("merged_segment_count", 0)),
        )

    @staticmethod
    def _serialize_transcript(transcript: Transcript) -> dict:
        options = transcript.options
        return {
            "source": str(transcript.source.path),
            "language": transcript.language,
            "model_name": transcript.model_name,
            "created_at": transcript.created_at.isoformat(timespec="seconds"),
            "options": None
            if options is None
            else {
                "model_name": options.model_name,
                "language": options.language,
                "task": options.task,
                "beam_size": options.beam_size,
                "vad_filter": options.vad_filter,
                "initial_prompt": options.initial_prompt,
                "preset": options.preset,
                "word_timestamps": options.word_timestamps,
                "provider_name": options.provider_name,
            },
            "segments": [
                {
                    "text": segment.text,
                    "start_seconds": segment.start_seconds,
                    "end_seconds": segment.end_seconds,
                    "raw_words": [
                        ProgressiveChunkCache._serialize_word(word) for word in segment.raw_words
                    ],
                    "words": [ProgressiveChunkCache._serialize_word(word) for word in segment.words],
                }
                for segment in transcript.segments
            ],
        }

    @staticmethod
    def _deserialize_transcript(payload: dict, *, source: MediaItem) -> Transcript:
        options_payload = payload.get("options")
        options = (
            None
            if options_payload is None
            else TranscriptionOptions(
                model_name=options_payload["model_name"],
                language=options_payload.get("language"),
                task=options_payload["task"],
                beam_size=int(options_payload["beam_size"]),
                vad_filter=bool(options_payload["vad_filter"]),
                initial_prompt=options_payload.get("initial_prompt"),
                preset=options_payload.get("preset"),
                word_timestamps=bool(options_payload.get("word_timestamps", False)),
                provider_name=options_payload.get("provider_name", "local-whisper"),
            )
        )
        return Transcript(
            source=source,
            segments=tuple(
                TranscriptSegment(
                    text=segment_payload["text"],
                    start_seconds=segment_payload.get("start_seconds"),
                    end_seconds=segment_payload.get("end_seconds"),
                    raw_words=tuple(
                        ProgressiveChunkCache._deserialize_word(word_payload)
                        for word_payload in segment_payload.get("raw_words", [])
                    ),
                    words=tuple(
                        ProgressiveChunkCache._deserialize_word(word_payload)
                        for word_payload in segment_payload.get("words", [])
                    ),
                )
                for segment_payload in payload.get("segments", [])
            ),
            language=payload.get("language"),
            model_name=payload.get("model_name"),
            options=options,
            created_at=datetime.fromisoformat(payload["created_at"]),
        )

    @staticmethod
    def _serialize_word(word: TranscriptWord) -> dict:
        return {
            "text": word.text,
            "start_seconds": word.start_seconds,
            "end_seconds": word.end_seconds,
            "confidence": word.confidence,
        }

    @staticmethod
    def _deserialize_word(payload: dict) -> TranscriptWord:
        return TranscriptWord(
            text=payload["text"],
            start_seconds=payload.get("start_seconds"),
            end_seconds=payload.get("end_seconds"),
            confidence=payload.get("confidence"),
        )
