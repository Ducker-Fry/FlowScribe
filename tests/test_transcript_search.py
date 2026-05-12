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
