import pytest

from flowscribe.core.models import TranscriptWord
from flowscribe.nlp import segmenter


def test_align_chinese_words_merges_raw_character_tokens(monkeypatch) -> None:
    me = "\u6211"
    like = "\u559c\u6b22"
    milk = "\u725b\u5976"
    milk_first = "\u725b"
    milk_second = "\u5976"
    monkeypatch.setattr(segmenter, "segment_chinese_text", lambda text: (me, like, milk))
    raw_words = (
        TranscriptWord(me, 0.0, 0.1, 0.90),
        TranscriptWord(like, 0.1, 0.4, 0.95),
        TranscriptWord(milk_first, 0.4, 0.6, 0.80),
        TranscriptWord(milk_second, 0.6, 0.8, 0.88),
    )

    words = segmenter.align_chinese_words(me + like + milk, raw_words)

    assert [word.text for word in words] == [me, like, milk]
    assert words[2].start_seconds == 0.4
    assert words[2].end_seconds == 0.8
    assert words[2].confidence == pytest.approx(0.84)


def test_align_chinese_words_falls_back_to_raw_words_on_mismatch(monkeypatch) -> None:
    machine_learning = "\u673a\u5668\u5b66\u4e60"
    raw_words = (
        TranscriptWord("\u5b8c\u5168", 0.0, 0.2, 0.90),
        TranscriptWord("\u4e0d\u540c", 0.2, 0.4, 0.90),
    )
    monkeypatch.setattr(segmenter, "segment_chinese_text", lambda text: (machine_learning,))

    assert segmenter.align_chinese_words(machine_learning, raw_words) == raw_words


def test_align_chinese_words_splits_coarse_provider_tokens(monkeypatch) -> None:
    me = "\u6211"
    like = "\u559c\u6b22"
    milk = "\u725b\u5976"
    monkeypatch.setattr(segmenter, "segment_chinese_text", lambda text: (me, like, milk))
    raw_words = (
        TranscriptWord(me + like, 0.0, 0.6, 0.90),
        TranscriptWord(milk, 0.6, 1.0, 0.80),
    )

    words = segmenter.align_chinese_words(me + like + milk, raw_words)

    assert [word.text for word in words] == [me, like, milk]
    assert words[0].start_seconds == 0.0
    assert words[0].end_seconds == pytest.approx(0.2)
    assert words[1].start_seconds == pytest.approx(0.2)
    assert words[1].end_seconds == pytest.approx(0.6)
    assert words[2].start_seconds == 0.6
    assert words[2].end_seconds == 1.0
