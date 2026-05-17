"""Tests for flowscribe.queue.importers."""


import pytest

from flowscribe.app.models import SourceSpec
from flowscribe.queue.importers import (
    deduplicate_sources,
    import_urls_from_csv,
    import_urls_from_file,
    import_urls_from_txt,
    parse_urls_from_text,
)
from flowscribe.queue.models import QueueItem, QueueItemSettings


def test_parse_urls_from_text_basic():
    text = "https://example.com/a.mp4\nhttps://example.com/b.mp4\n"
    urls = parse_urls_from_text(text)
    assert urls == ["https://example.com/a.mp4", "https://example.com/b.mp4"]


def test_parse_urls_from_text_skips_comments_and_blanks():
    text = "# comment\n\nhttps://example.com/a.mp4\n  \n# another\nhttps://example.com/b.mp4"
    urls = parse_urls_from_text(text)
    assert urls == ["https://example.com/a.mp4", "https://example.com/b.mp4"]


def test_parse_urls_from_text_skips_non_urls():
    text = "not a url\nftp://example.com/file\nhttps://valid.com/ok"
    urls = parse_urls_from_text(text)
    assert urls == ["https://valid.com/ok"]


def test_parse_urls_from_text_strips_whitespace():
    text = "  https://example.com/a.mp4  \n"
    urls = parse_urls_from_text(text)
    assert urls == ["https://example.com/a.mp4"]


def test_import_urls_from_txt(tmp_path):
    txt_file = tmp_path / "urls.txt"
    txt_file.write_text("https://a.com/1\nhttps://b.com/2\n", encoding="utf-8")
    urls = import_urls_from_txt(txt_file)
    assert urls == ["https://a.com/1", "https://b.com/2"]


def test_import_urls_from_csv(tmp_path):
    csv_file = tmp_path / "urls.csv"
    csv_file.write_text("url,title\nhttps://a.com/1,Video 1\nhttps://b.com/2,Video 2\n", encoding="utf-8")
    urls = import_urls_from_csv(csv_file)
    assert urls == ["https://a.com/1", "https://b.com/2"]


def test_import_urls_from_csv_skips_header(tmp_path):
    csv_file = tmp_path / "urls.csv"
    csv_file.write_text("url\nhttps://a.com/1\n", encoding="utf-8")
    urls = import_urls_from_csv(csv_file)
    assert urls == ["https://a.com/1"]


def test_import_urls_from_file_txt(tmp_path):
    txt_file = tmp_path / "urls.txt"
    txt_file.write_text("https://a.com/1\n", encoding="utf-8")
    urls = import_urls_from_file(txt_file)
    assert urls == ["https://a.com/1"]


def test_import_urls_from_file_unsupported(tmp_path):
    bad_file = tmp_path / "urls.doc"
    bad_file.write_text("content", encoding="utf-8")
    with pytest.raises(ValueError, match="Unsupported"):
        import_urls_from_file(bad_file)


def test_deduplicate_sources():
    existing = [
        QueueItem(
            item_id="id1",
            source=SourceSpec(kind="url", value="https://a.com/1"),
            settings=QueueItemSettings(),
            status="pending",
        ),
        QueueItem(
            item_id="id2",
            source=SourceSpec(kind="url", value="https://a.com/2"),
            settings=QueueItemSettings(),
            status="completed",
        ),
    ]
    new_sources = [
        SourceSpec(kind="url", value="https://a.com/1"),
        SourceSpec(kind="url", value="https://a.com/2"),
        SourceSpec(kind="url", value="https://a.com/3"),
    ]
    result = deduplicate_sources(new_sources, existing)
    assert len(result) == 2
    assert result[0].value == "https://a.com/2"
    assert result[1].value == "https://a.com/3"
