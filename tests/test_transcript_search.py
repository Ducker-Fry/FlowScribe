import json
from pathlib import Path

from flowscribe.search.transcript_search import search_transcript_file


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
