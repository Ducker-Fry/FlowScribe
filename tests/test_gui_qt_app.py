from pathlib import Path

from flowscribe.gui.qt_app import (
    _gui_state_payload,
    _normalize_gui_preferences_payload,
    _normalize_recent_work_entry_paths,
    _recent_work_payload,
    _normalize_gui_state_payload,
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


def test_normalize_gui_preferences_payload_filters_invalid_values() -> None:
    preferences = _normalize_gui_preferences_payload(
        {
            "output_dir": "",
            "model_name": "bad-model",
            "language": "fr",
            "preset": "bad-preset",
            "output_formats": ["txt", "bad", "json"],
            "timestamps": False,
            "word_timestamps": True,
            "overwrite": True,
            "keep_media": True,
            "network_family": "bad-network",
            "proxy": 123,
        }
    )

    assert preferences == {
        "output_dir": "outputs",
        "model_name": "small",
        "language": "auto",
        "preset": "none",
        "output_formats": ["txt", "json"],
        "timestamps": False,
        "word_timestamps": True,
        "overwrite": True,
        "keep_media": True,
        "network_family": "auto",
        "proxy": "",
    }


def test_gui_state_payload_uses_nested_preferences_and_local_sources(tmp_path: Path) -> None:
    media = tmp_path / "sample.mp4"
    media.write_bytes(b"media")
    transcript = tmp_path / "result.json"
    transcript.write_text("{}", encoding="utf-8")
    outputs = tmp_path / "outputs"
    outputs.mkdir()

    payload = _gui_state_payload(
        [media],
        [media],
        {
            "output_dir": "saved-outputs",
            "model_name": "medium",
            "language": "zh",
            "preset": "zh",
            "output_formats": ["txt", "md"],
            "timestamps": True,
            "word_timestamps": False,
            "overwrite": False,
            "keep_media": False,
            "network_family": "ipv4",
            "proxy": "http://127.0.0.1:7890",
        },
        {
            "recent_transcripts": [str(transcript)],
            "recent_output_dirs": [str(outputs)],
            "recent_jobs": [
                {
                    "label": "1 source(s) -> outputs",
                    "status": "completed",
                    "output_dir": str(outputs),
                    "transcript_path": str(transcript),
                    "media_path": str(media),
                }
            ],
            "recent_media_bindings": [
                {
                    "transcript_path": str(transcript),
                    "media_path": str(media),
                }
            ],
        },
    )

    assert payload == {
        "version": 3,
        "preferences": {
            "output_dir": "saved-outputs",
            "model_name": "medium",
            "language": "zh",
            "preset": "zh",
            "output_formats": ["txt", "md"],
            "timestamps": True,
            "word_timestamps": False,
            "overwrite": False,
            "keep_media": False,
            "network_family": "ipv4",
            "proxy": "http://127.0.0.1:7890",
        },
        "local_sources": {
            "local_paths": [str(media)],
            "checked_paths": [str(media)],
        },
        "recent_work": {
            "recent_transcripts": [str(transcript)],
            "recent_output_dirs": [str(outputs)],
            "recent_jobs": [
                {
                    "label": "1 source(s) -> outputs",
                    "status": "completed",
                    "output_dir": str(outputs),
                    "transcript_path": str(transcript),
                    "media_path": str(media),
                }
            ],
            "recent_media_bindings": [
                {
                    "transcript_path": str(transcript),
                    "media_path": str(media),
                }
            ],
        },
    }


def test_normalize_gui_state_payload_supports_nested_and_legacy_formats(tmp_path: Path) -> None:
    media = tmp_path / "sample.mp4"
    media.write_bytes(b"media")
    transcript = tmp_path / "result.json"
    transcript.write_text("{}", encoding="utf-8")
    outputs = tmp_path / "outputs"
    outputs.mkdir()

    local_paths, checked, preferences, recent_work = _normalize_gui_state_payload(
        {
            "preferences": {
                "output_dir": "custom-out",
                "model_name": "medium",
                "language": "zh",
                "preset": "zh",
                "output_formats": ["txt", "vtt"],
                "timestamps": False,
                "word_timestamps": True,
                "overwrite": True,
                "keep_media": True,
                "network_family": "ipv4",
                "proxy": "http://127.0.0.1:7890",
            },
            "local_sources": {
                "local_paths": [str(media)],
                "checked_paths": [str(media)],
            },
            "recent_work": {
                "recent_transcripts": [str(transcript)],
                "recent_output_dirs": [str(outputs)],
                "recent_jobs": [
                    {
                        "label": "nested",
                        "status": "completed",
                        "output_dir": str(outputs),
                        "transcript_path": str(transcript),
                        "media_path": str(media),
                    }
                ],
                "recent_media_bindings": [
                    {
                        "transcript_path": str(transcript),
                        "media_path": str(media),
                    }
                ],
            },
        }
    )

    assert local_paths == [media]
    assert checked == {str(media)}
    assert preferences["output_dir"] == "custom-out"
    assert preferences["model_name"] == "medium"
    assert preferences["output_formats"] == ["txt", "vtt"]
    assert recent_work["recent_transcripts"] == [str(transcript)]
    assert recent_work["recent_output_dirs"] == [str(outputs)]

    legacy_local_paths, legacy_checked, legacy_preferences, legacy_recent_work = _normalize_gui_state_payload(
        {
            "local_paths": [str(media)],
            "selected_paths": [str(media)],
            "output_dir": "legacy-out",
            "model_name": "tiny",
            "language": "en",
            "preset": "none",
            "output_formats": ["json"],
            "network_family": "ipv6",
            "proxy": "http://localhost:7890",
        }
    )

    assert legacy_local_paths == [media]
    assert legacy_checked == {str(media)}
    assert legacy_preferences["output_dir"] == "legacy-out"
    assert legacy_preferences["model_name"] == "tiny"
    assert legacy_preferences["language"] == "en"
    assert legacy_preferences["output_formats"] == ["json"]
    assert legacy_recent_work == {
        "recent_transcripts": [],
        "recent_output_dirs": [],
        "recent_jobs": [],
        "recent_media_bindings": [],
    }


def test_normalize_recent_work_entry_paths_deduplicates_and_preserves_missing_paths(tmp_path: Path) -> None:
    transcript = tmp_path / "result.json"
    transcript.write_text("{}", encoding="utf-8")
    missing = tmp_path / "missing.json"

    normalized = _normalize_recent_work_entry_paths(
        [str(transcript), str(transcript), str(missing), 123],
        max_items=8,
    )

    assert normalized == [str(transcript), str(missing)]


def test_recent_work_payload_filters_invalid_entries(tmp_path: Path) -> None:
    transcript = tmp_path / "result.json"
    transcript.write_text("{}", encoding="utf-8")
    media = tmp_path / "sample.mp4"
    media.write_bytes(b"media")
    outputs = tmp_path / "outputs"
    outputs.mkdir()

    payload = _recent_work_payload(
        {
            "recent_transcripts": [str(transcript), "", 42],
            "recent_output_dirs": [str(outputs), str(transcript)],
            "recent_jobs": [
                {
                    "label": "job",
                    "status": "completed",
                    "output_dir": str(outputs),
                    "transcript_path": str(transcript),
                    "media_path": str(media),
                },
                {"label": "", "status": "failed", "output_dir": str(outputs)},
            ],
            "recent_media_bindings": [
                {
                    "transcript_path": str(transcript),
                    "media_path": str(media),
                },
                {
                    "transcript_path": "",
                    "media_path": str(media),
                },
            ],
        }
    )

    assert payload == {
        "recent_transcripts": [str(transcript)],
        "recent_output_dirs": [str(outputs)],
        "recent_jobs": [
            {
                "label": "job",
                "status": "completed",
                "output_dir": str(outputs),
                "transcript_path": str(transcript),
                "media_path": str(media),
            }
        ],
        "recent_media_bindings": [
            {
                "transcript_path": str(transcript),
                "media_path": str(media),
            }
        ],
    }
