"""Chinese natural-word alignment for timed transcript tokens."""

from __future__ import annotations

import logging

from flowscribe.core.models import TranscriptWord


def align_chinese_words(
    text: str,
    raw_words: tuple[TranscriptWord, ...],
) -> tuple[TranscriptWord, ...]:
    """Merge provider timing tokens into Chinese natural words.

    The speech provider may return Chinese timing units as individual characters or short
    tokens. This function keeps those units available as raw_words while producing natural
    words for navigation and search.
    """

    if not raw_words:
        return ()

    target_words = tuple(word for word in segment_chinese_text(text) if _compact(word))
    if not target_words:
        return raw_words

    timing_units = _expand_to_character_units(raw_words)
    aligned: list[TranscriptWord] = []
    raw_index = 0
    for target in target_words:
        target_compact = _compact(target)
        consumed: list[TranscriptWord] = []
        consumed_text = ""

        while raw_index < len(timing_units) and len(consumed_text) < len(target_compact):
            raw_word = timing_units[raw_index]
            raw_index += 1
            raw_compact = _compact(raw_word.text)
            if not raw_compact:
                continue
            consumed.append(raw_word)
            consumed_text += raw_compact

        if not consumed:
            continue

        if consumed_text != target_compact and not consumed_text.startswith(target_compact):
            return raw_words

        aligned.append(_merge_words(target, consumed))

    if raw_index < len(timing_units):
        aligned.extend(timing_units[raw_index:])

    return tuple(aligned) or raw_words


def segment_chinese_text(text: str) -> tuple[str, ...]:
    """Segment Chinese text with jieba, falling back to raw characters if unavailable."""

    try:
        import jieba
    except ImportError:
        return tuple(char for char in text if not char.isspace())

    jieba.setLogLevel(logging.ERROR)
    return tuple(part.strip() for part in jieba.lcut(text, HMM=True) if part.strip())


def _merge_words(text: str, words: list[TranscriptWord]) -> TranscriptWord:
    confidences = [word.confidence for word in words if word.confidence is not None]
    confidence = sum(confidences) / len(confidences) if confidences else None
    return TranscriptWord(
        text=text,
        start_seconds=words[0].start_seconds,
        end_seconds=words[-1].end_seconds,
        confidence=confidence,
    )


def _expand_to_character_units(words: tuple[TranscriptWord, ...]) -> tuple[TranscriptWord, ...]:
    units: list[TranscriptWord] = []
    for word in words:
        compact = _compact(word.text)
        if len(compact) <= 1:
            units.append(word)
            continue

        duration = (
            word.end_seconds - word.start_seconds
            if word.start_seconds is not None and word.end_seconds is not None
            else None
        )
        for index, char in enumerate(compact):
            start = None
            end = None
            if duration is not None:
                step = duration / len(compact)
                start = word.start_seconds + step * index
                end = word.start_seconds + step * (index + 1)
            units.append(
                TranscriptWord(
                    text=char,
                    start_seconds=start,
                    end_seconds=end,
                    confidence=word.confidence,
                )
            )
    return tuple(units)


def _compact(text: str) -> str:
    return "".join(text.split())
