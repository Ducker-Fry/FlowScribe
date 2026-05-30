"""Post-processing deduplication for progressive transcription results."""

from __future__ import annotations

from dataclasses import replace

from flowscribe.core.models import Transcript, TranscriptSegment


class TranscriptDeduplicator:
    """Remove duplicate segments from final transcript output."""

    def __init__(
        self,
        *,
        text_similarity_threshold: float = 0.9,
        time_overlap_threshold_seconds: float = 2.0,
    ) -> None:
        """
        Initialize deduplicator.

        Args:
            text_similarity_threshold: Minimum similarity ratio to consider segments duplicates
            time_overlap_threshold_seconds: Maximum time gap to consider segments as overlapping
        """
        self._text_similarity_threshold = text_similarity_threshold
        self._time_overlap_threshold = time_overlap_threshold_seconds

    def deduplicate(self, transcript: Transcript) -> Transcript:
        """
        Remove duplicate segments from transcript.

        This is designed to run after progressive transcription completes,
        removing any remaining duplicates at chunk boundaries.
        """
        if not transcript.segments:
            return transcript

        deduplicated_segments = self._deduplicate_segments(list(transcript.segments))

        return replace(
            transcript,
            segments=tuple(deduplicated_segments),
        )

    def _deduplicate_segments(
        self,
        segments: list[TranscriptSegment],
    ) -> list[TranscriptSegment]:
        """Remove duplicate segments using sliding window comparison."""
        if not segments:
            return []

        result: list[TranscriptSegment] = [segments[0]]

        for current in segments[1:]:
            # Check if current segment is duplicate of the last kept segment
            if self._is_duplicate(result[-1], current):
                # Keep the segment with better timing information
                if self._has_better_timing(current, result[-1]):
                    result[-1] = current
                continue

            result.append(current)

        return result

    def _is_duplicate(
        self,
        seg1: TranscriptSegment,
        seg2: TranscriptSegment,
    ) -> bool:
        """Check if two segments are duplicates based on text and timing."""
        # Normalize text for comparison
        text1 = self._normalize_text(seg1.text)
        text2 = self._normalize_text(seg2.text)

        if not text1 or not text2:
            return False

        # Check text similarity
        if text1 == text2:
            text_match = True
        else:
            # Check if one text is substring of another (common in chunk overlaps)
            text_match = text1 in text2 or text2 in text1
            if not text_match:
                # Check similarity ratio
                similarity = self._text_similarity(text1, text2)
                text_match = similarity >= self._text_similarity_threshold

        if not text_match:
            return False

        # If texts match, check timing overlap
        return self._has_time_overlap(seg1, seg2)

    def _has_time_overlap(
        self,
        seg1: TranscriptSegment,
        seg2: TranscriptSegment,
    ) -> bool:
        """Check if two segments overlap in time."""
        # If either segment lacks timing, consider them overlapping if text matches
        if seg1.start_seconds is None or seg2.start_seconds is None:
            return True

        # Check if segments are close in time
        time_gap = abs(seg1.start_seconds - seg2.start_seconds)
        return time_gap <= self._time_overlap_threshold

    @staticmethod
    def _normalize_text(text: str) -> str:
        """Normalize text for comparison."""
        return " ".join(text.strip().split())

    @staticmethod
    def _text_similarity(text1: str, text2: str) -> float:
        """Calculate simple text similarity ratio."""
        if not text1 or not text2:
            return 0.0

        # Use simple character-level similarity
        len1, len2 = len(text1), len(text2)
        max_len = max(len1, len2)
        if max_len == 0:
            return 1.0

        # Count matching characters at the start
        matching = 0
        for c1, c2 in zip(text1, text2):
            if c1 == c2:
                matching += 1
            else:
                break

        return matching / max_len

    @staticmethod
    def _has_better_timing(seg1: TranscriptSegment, seg2: TranscriptSegment) -> bool:
        """Check if seg1 has better timing information than seg2."""
        # Prefer segment with both start and end times
        seg1_complete = seg1.start_seconds is not None and seg1.end_seconds is not None
        seg2_complete = seg2.start_seconds is not None and seg2.end_seconds is not None

        if seg1_complete and not seg2_complete:
            return True
        if seg2_complete and not seg1_complete:
            return False

        # Prefer segment with word-level timestamps
        if len(seg1.words) > len(seg2.words):
            return True

        return False
