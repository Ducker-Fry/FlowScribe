"""Progressive transcription merging - chunk merge policies and consistency checking."""

from __future__ import annotations

from dataclasses import replace
from typing import Protocol

from flowscribe.core.errors import TranscriptionError
from flowscribe.core.models import (
    Transcript,
    TranscriptSegment,
    TranscriptWord,
    TranscriptionChunk,
)


class ChunkMergePolicy(Protocol):
    def merge(
        self,
        *,
        existing_segments: list[TranscriptSegment],
        chunk_segments: tuple[TranscriptSegment, ...],
        chunk: TranscriptionChunk,
        transcript: Transcript,
    ) -> list[TranscriptSegment]:
        """Return segments to append from one chunk."""


class ConservativeChunkMergePolicy:
    """Keep chunk merges conservative, especially around Chinese boundaries."""

    def __init__(self, *, duplicate_tolerance_seconds: float = 0.35) -> None:
        self._duplicate_tolerance_seconds = duplicate_tolerance_seconds

    def merge(
        self,
        *,
        existing_segments: list[TranscriptSegment],
        chunk_segments: tuple[TranscriptSegment, ...],
        chunk: TranscriptionChunk,
        transcript: Transcript,
    ) -> list[TranscriptSegment]:
        prepared = self._prepare_segments(chunk_segments, chunk=chunk)
        if not prepared:
            return []

        appended: list[TranscriptSegment] = []
        protect_chinese = _is_chinese_transcript(transcript)
        prior = existing_segments[-1] if existing_segments else None
        for segment in prepared:
            if prior is not None and self._should_drop_duplicate(
                prior,
                segment,
                protect_chinese=protect_chinese,
            ):
                continue
            appended.append(segment)
            prior = segment
        return appended

    def _prepare_segments(
        self,
        segments: tuple[TranscriptSegment, ...],
        *,
        chunk: TranscriptionChunk,
    ) -> list[TranscriptSegment]:
        if chunk.index <= 1:
            return list(segments)

        prepared: list[TranscriptSegment] = []
        content_start_seconds = chunk.content_start_seconds
        for segment in segments:
            segment_end_seconds = segment.end_seconds
            if segment_end_seconds is not None and segment_end_seconds <= content_start_seconds:
                continue
            if (
                segment.start_seconds is not None
                and segment.start_seconds < content_start_seconds
                and (segment_end_seconds is None or segment_end_seconds > content_start_seconds)
            ):
                prepared.append(
                    self._clip_segment_start(segment, content_start_seconds)
                )
                continue
            prepared.append(segment)
        return prepared

    def _clip_segment_start(self, segment: TranscriptSegment, content_start_seconds: float) -> TranscriptSegment:
        return replace(
            segment,
            start_seconds=content_start_seconds,
            raw_words=self._clip_words(segment.raw_words, content_start_seconds),
            words=self._clip_words(segment.words, content_start_seconds),
        )

    @staticmethod
    def _clip_words(
        words: tuple[TranscriptWord, ...],
        content_start_seconds: float,
    ) -> tuple[TranscriptWord, ...]:
        clipped: list[TranscriptWord] = []
        for word in words:
            word_end = word.end_seconds
            if word_end is not None and word_end <= content_start_seconds:
                continue
            if word.start_seconds is not None and word.start_seconds < content_start_seconds:
                clipped.append(replace(word, start_seconds=content_start_seconds))
            else:
                clipped.append(word)
        return tuple(clipped)

    def _should_drop_duplicate(
        self,
        previous: TranscriptSegment,
        current: TranscriptSegment,
        *,
        protect_chinese: bool,
    ) -> bool:
        if _normalized_segment_text(previous) != _normalized_segment_text(current):
            return False
        if protect_chinese:
            return _matching_segment_span(
                previous,
                current,
                tolerance_seconds=self._duplicate_tolerance_seconds,
            )
        return _segments_overlap(previous, current, tolerance_seconds=self._duplicate_tolerance_seconds)


class ProgressiveTranscriptConsistencyChecker:
    """Validate merged chunk output before it is written or resumed."""

    def __init__(
        self,
        *,
        max_allowed_overlap_seconds: float = 3.0,
        auto_fix_timestamps: bool = True,
    ) -> None:
        self._max_allowed_overlap_seconds = max_allowed_overlap_seconds
        self._auto_fix_timestamps = auto_fix_timestamps

    def validate(self, transcript: Transcript) -> Transcript:
        if not self._auto_fix_timestamps:
            return self._validate_strict(transcript)
        return self._validate_and_fix(transcript)

    def _validate_strict(self, transcript: Transcript) -> Transcript:
        """Strict validation without auto-fixing."""
        previous: TranscriptSegment | None = None
        for index, segment in enumerate(transcript.segments, start=1):
            self._validate_segment(segment, index=index)
            if previous is not None:
                self._validate_segment_order(previous, segment, index=index)
            previous = segment
        return transcript

    def _validate_and_fix(self, transcript: Transcript) -> Transcript:
        """Validate and auto-fix timestamp issues."""
        if not transcript.segments:
            return transcript

        fixed_segments: list[TranscriptSegment] = []
        previous: TranscriptSegment | None = None

        for index, segment in enumerate(transcript.segments, start=1):
            # Validate segment internal consistency
            if (
                segment.start_seconds is not None
                and segment.end_seconds is not None
                and segment.end_seconds < segment.start_seconds
            ):
                raise TranscriptionError(
                    f"Progressive transcript segment {index} ends before it starts."
                )

            # Fix timestamp order issues
            if previous is not None:
                segment = self._fix_segment_order(previous, segment, index=index)

            fixed_segments.append(segment)
            previous = segment

        return Transcript(
            source=transcript.source,
            segments=tuple(fixed_segments),
            language=transcript.language,
            model_name=transcript.model_name,
            options=transcript.options,
            created_at=transcript.created_at,
        )

    def _fix_segment_order(
        self,
        previous: TranscriptSegment,
        current: TranscriptSegment,
        *,
        index: int,
    ) -> TranscriptSegment:
        """Fix timestamp order issues by adjusting current segment."""
        if current.start_seconds is None or previous.start_seconds is None:
            return current

        # Fix: current starts before previous
        if current.start_seconds < previous.start_seconds:
            # Use previous segment's start as minimum
            fixed_start = previous.start_seconds
            return replace(current, start_seconds=fixed_start)

        # Fix: excessive overlap
        if (
            previous.end_seconds is not None
            and current.start_seconds < previous.end_seconds - self._max_allowed_overlap_seconds
        ):
            # Adjust to maximum allowed overlap
            fixed_start = previous.end_seconds - self._max_allowed_overlap_seconds
            return replace(current, start_seconds=fixed_start)

        return current

    def _validate_segment(self, segment: TranscriptSegment, *, index: int) -> None:
        """Validate segment internal consistency."""
        if (
            segment.start_seconds is not None
            and segment.end_seconds is not None
            and segment.end_seconds < segment.start_seconds
        ):
            raise TranscriptionError(
                f"Progressive transcript segment {index} ends before it starts."
            )

    def _validate_segment_order(
        self,
        previous: TranscriptSegment,
        current: TranscriptSegment,
        *,
        index: int,
    ) -> None:
        """Validate segment order (strict mode)."""
        if (
            previous.start_seconds is not None
            and current.start_seconds is not None
            and current.start_seconds < previous.start_seconds
        ):
            raise TranscriptionError(
                f"Progressive transcript segment {index} starts before the previous segment."
            )
        if (
            previous.end_seconds is not None
            and current.start_seconds is not None
            and current.start_seconds < previous.end_seconds - self._max_allowed_overlap_seconds
        ):
            raise TranscriptionError(
                f"Progressive transcript segment {index} overlaps the previous segment too much."
            )


def _is_chinese_transcript(transcript: Transcript) -> bool:
    language = (transcript.language or "").strip().lower()
    preset = (transcript.options.preset if transcript.options is not None else "") or ""
    options_language = (transcript.options.language if transcript.options is not None else "") or ""
    return language == "zh" or preset.strip().lower() == "zh" or options_language.strip().lower() == "zh"


def _normalized_segment_text(segment: TranscriptSegment) -> str:
    return " ".join(segment.text.strip().split())


def _matching_segment_span(
    left: TranscriptSegment,
    right: TranscriptSegment,
    *,
    tolerance_seconds: float,
) -> bool:
    if left.start_seconds is None or left.end_seconds is None:
        return False
    if right.start_seconds is None or right.end_seconds is None:
        return False
    return (
        abs(left.start_seconds - right.start_seconds) <= tolerance_seconds
        and abs(left.end_seconds - right.end_seconds) <= tolerance_seconds
    )


def _segments_overlap(
    left: TranscriptSegment,
    right: TranscriptSegment,
    *,
    tolerance_seconds: float,
) -> bool:
    if left.end_seconds is None or right.start_seconds is None:
        return False
    return right.start_seconds < left.end_seconds + tolerance_seconds
