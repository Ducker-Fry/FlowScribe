from pathlib import Path

from flowscribe.input.file_filter import is_supported_media


def test_supported_media_extension_is_detected(tmp_path: Path) -> None:
    media = tmp_path / "sample.mp4"
    media.write_text("placeholder", encoding="utf-8")

    assert is_supported_media(media)


def test_unsupported_media_extension_is_rejected(tmp_path: Path) -> None:
    document = tmp_path / "notes.txt"
    document.write_text("placeholder", encoding="utf-8")

    assert not is_supported_media(document)
