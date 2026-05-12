"""Chinese script normalization utilities."""

from __future__ import annotations

from dataclasses import replace

from flowscribe.core.errors import FlowScribeError
from flowscribe.core.models import Transcript, TranscriptSegment, TranscriptWord


class ChineseScriptConversionError(FlowScribeError):
    """Raised when Chinese script conversion is unavailable."""


def simplify_chinese_transcript(transcript: Transcript) -> Transcript:
    """Convert transcript text and timing words to Simplified Chinese."""

    converter = _simplified_converter()
    segments = tuple(_simplify_segment(segment, converter) for segment in transcript.segments)
    return replace(transcript, segments=segments)


def _simplify_segment(segment: TranscriptSegment, converter) -> TranscriptSegment:
    return replace(
        segment,
        text=converter.convert(segment.text),
        raw_words=tuple(_simplify_word(word, converter) for word in segment.raw_words),
        words=tuple(_simplify_word(word, converter) for word in segment.words),
    )


def _simplify_word(word: TranscriptWord, converter) -> TranscriptWord:
    return replace(word, text=converter.convert(word.text))


def _simplified_converter():
    try:
        from opencc import OpenCC
    except ImportError as exc:
        raise ChineseScriptConversionError(
            "Chinese simplification requires opencc-python-reimplemented. "
            "Run `python -m pip install -e .` to install project dependencies."
        ) from exc
    return OpenCC("t2s")
