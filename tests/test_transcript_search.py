import json
from pathlib import Path

from flowscribe.search.transcript_search import search_transcript_file

FIXTURES = Path(__file__).parent / "fixtures" / "transcripts"


def test_search_transcript_uses_word_timestamps(tmp_path: Path) -> None:
    machine_learning = "\u673a\u5668\u5b66\u4e60"
    path = tmp_path / "lesson.json"
    path.write_text(
        json.dumps(
            {
                "segments": [
                    {
                        "text": f"\u8fd9\u91cc\u8bb2\u5230{machine_learning}\u7684\u57fa\u672c\u6982\u5ff5",
                        "start_seconds": 1.0,
                        "end_seconds": 8.0,
                        "words": [
                            {"text": "\u8fd9\u91cc", "start_seconds": 1.0, "end_seconds": 1.3},
                            {"text": "\u8bb2\u5230", "start_seconds": 1.3, "end_seconds": 1.8},
                            {"text": machine_learning, "start_seconds": 2.1, "end_seconds": 3.0},
                            {
                                "text": "\u7684\u57fa\u672c\u6982\u5ff5",
                                "start_seconds": 3.0,
                                "end_seconds": 4.2,
                            },
                        ],
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    hits = search_transcript_file(path, machine_learning)

    assert len(hits) == 1
    assert hits[0].matched_text == machine_learning
    assert hits[0].start_seconds == 2.1
    assert hits[0].end_seconds == 3.0
    assert machine_learning in hits[0].context


def test_search_transcript_falls_back_to_segment_timestamps(tmp_path: Path) -> None:
    query = "keyword"
    path = tmp_path / "lesson.json"
    path.write_text(
        json.dumps(
            {
                "segments": [
                    {
                        "text": f"This segment contains a {query} for testing.",
                        "start_seconds": 10.0,
                        "end_seconds": 20.0,
                        "words": [],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    hits = search_transcript_file(path, query, context_chars=8)

    assert len(hits) == 1
    assert hits[0].start_seconds == 10.0
    assert hits[0].end_seconds == 20.0
    assert hits[0].context.startswith("...")
    assert hits[0].context.endswith("...")
    assert "keyword" in hits[0].context


def test_search_transcript_applies_limit_and_time_filters(tmp_path: Path) -> None:
    query = "keyword"
    path = tmp_path / "lesson.json"
    path.write_text(
        json.dumps(
            {
                "segments": [
                    _segment("early keyword", 10.0, 11.0),
                    _segment("middle keyword", 20.0, 21.0),
                    _segment("late keyword", 30.0, 31.0),
                ]
            }
        ),
        encoding="utf-8",
    )

    hits = search_transcript_file(
        path,
        query,
        limit=1,
        after_seconds=15.0,
        before_seconds=25.0,
    )

    assert len(hits) == 1
    assert hits[0].context == "middle keyword"
    assert hits[0].start_seconds == 20.0


def test_search_transcript_context_tracks_repeated_word_hits(tmp_path: Path) -> None:
    query = "keyword"
    path = tmp_path / "lesson.json"
    path.write_text(
        json.dumps(
            {
                "segments": [
                    {
                        "text": f"first {query}. second {query}.",
                        "start_seconds": 0.0,
                        "end_seconds": 3.0,
                        "words": [
                            {"text": "first", "start_seconds": 0.0, "end_seconds": 0.3},
                            {"text": query, "start_seconds": 0.3, "end_seconds": 0.8},
                            {"text": "second", "start_seconds": 1.5, "end_seconds": 1.9},
                            {"text": query, "start_seconds": 2.0, "end_seconds": 2.5},
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    hits = search_transcript_file(path, query, context_chars=4)

    assert len(hits) == 2
    assert hits[0].start_seconds == 0.3
    assert "rst keyword." in hits[0].context
    assert hits[1].start_seconds == 2.0
    assert "ond keyword." in hits[1].context


def _segment(text: str, start: float, end: float) -> dict:
    return {
        "text": text,
        "start_seconds": start,
        "end_seconds": end,
        "words": [],
    }


def test_fixture_chinese_repeated_keyword_returns_all_matches() -> None:
    query = "\u673a\u5668\u5b66\u4e60"

    hits = search_transcript_file(FIXTURES / "chinese_repeated_keyword.json", query)

    assert len(hits) == 3
    assert [hit.start_seconds for hit in hits] == [11.4, 121.0, 301.0]
    assert all(query in hit.context for hit in hits)


def test_fixture_mixed_language_keyword_spans_english_and_chinese_words() -> None:
    hits = search_transcript_file(FIXTURES / "mixed_language_keyword.json", "AI\u6a21\u578b")

    assert len(hits) == 1
    assert hits[0].start_seconds == 41.6
    assert hits[0].end_seconds == 42.8


def test_fixture_legacy_no_words_uses_segment_time_range() -> None:
    hits = search_transcript_file(FIXTURES / "legacy_no_words.json", "keyword")

    assert len(hits) == 1
    assert hits[0].start_seconds == 50.0
    assert hits[0].end_seconds == 60.0


def test_fixture_raw_and_aligned_words_uses_natural_word_timing() -> None:
    hits = search_transcript_file(FIXTURES / "raw_and_words.json", "\u725b\u5976")

    assert len(hits) == 1
    assert hits[0].start_seconds == 0.5
    assert hits[0].end_seconds == 0.9


def test_fixture_long_transcript_limit_keeps_first_results() -> None:
    hits = search_transcript_file(FIXTURES / "long_transcript.json", "keyword", limit=5)

    assert len(hits) == 5
    assert [hit.start_seconds for hit in hits] == [60.0, 120.0, 180.0, 240.0, 300.0]


def test_fixture_multi_segment_time_window_filters_matches() -> None:
    hits = search_transcript_file(
        FIXTURES / "multi_segment_time_window.json",
        "keyword",
        after_seconds=600.0,
        before_seconds=1800.0,
    )

    assert len(hits) == 2
    assert [hit.start_seconds for hit in hits] == [610.0, 900.0]


def test_fixture_cross_word_keyword_uses_span_start_and_end_times() -> None:
    hits = search_transcript_file(FIXTURES / "cross_word_keyword.json", "\u6df1\u5ea6\u5b66\u4e60")

    assert len(hits) == 1
    assert hits[0].start_seconds == 201.0
    assert hits[0].end_seconds == 202.4


def test_search_accepts_stable_json_start_end_and_word_alias(tmp_path: Path) -> None:
    path = tmp_path / "stable.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "1.1",
                "segments": [
                    {
                        "text": "alpha keyword",
                        "start": 5.0,
                        "end": 8.0,
                        "words": [
                            {"word": "alpha", "start": 5.0, "end": 5.5},
                            {"word": "keyword", "start": 5.5, "end": 6.2},
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    hits = search_transcript_file(path, "keyword")

    assert len(hits) == 1
    assert hits[0].start_seconds == 5.5
    assert hits[0].end_seconds == 6.2
