from pathlib import Path

from flowscribe.gui.qt_app import (
    _local_source_state_payload,
    _normalize_local_source_state_payload,
)


def test_local_source_state_payload_uses_checked_paths(tmp_path: Path) -> None:
    media = tmp_path / "sample.mp4"
    media.write_bytes(b"media")
    folder = tmp_path / "folder"
    folder.mkdir()

    payload = _local_source_state_payload([media, folder], [folder])

    assert payload == {
        "local_paths": [str(media), str(folder)],
        "checked_paths": [str(folder)],
    }


def test_normalize_local_source_state_payload_supports_legacy_selected_paths(tmp_path: Path) -> None:
    media = tmp_path / "sample.mp4"
    media.write_bytes(b"media")
    folder = tmp_path / "folder"
    folder.mkdir()

    local_paths, checked = _normalize_local_source_state_payload(
        {
            "local_paths": [str(media), str(folder)],
            "selected_paths": [str(media)],
        }
    )

    assert local_paths == [media, folder]
    assert checked == {str(media)}


def test_normalize_local_source_state_payload_filters_unsupported_entries(tmp_path: Path) -> None:
    media = tmp_path / "sample.mp4"
    media.write_bytes(b"media")
    text = tmp_path / "notes.txt"
    text.write_text("notes", encoding="utf-8")

    local_paths, checked = _normalize_local_source_state_payload(
        {
            "local_paths": [str(media), str(text)],
            "checked_paths": [str(media), str(text)],
        }
    )

    assert local_paths == [media]
    assert checked == {str(media), str(text)}
