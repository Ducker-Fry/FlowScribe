from datetime import datetime
from pathlib import Path

from flowscribe.app.models import SourceSpec, TranscriptionJob, TranscriptionResult
from flowscribe.core.models import OutputArtifacts
from flowscribe.gui.export_profiles import ExportProfile
from flowscribe.gui.qt_app import (
    _build_library_entry,
    _discover_transcript_output_paths,
    _format_library_datetime,
    _gui_state_payload,
    _infer_library_source_kind_from_result,
    _infer_library_source_media_path_from_result,
    _library_entry_list_label,
    _library_entry_missing_summary,
    _normalize_gui_preferences_payload,
    _normalize_recent_work_entry_paths,
    _recent_work_payload,
    _sort_library_entries,
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
            "output_name_base": 123,
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
        "output_name_base": "",
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
            "output_name_base": "custom-name",
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
        (
            ExportProfile(
                name="Review",
                output_formats=("txt", "md"),
                timestamps=True,
                word_timestamps=False,
            ),
        ),
    )

    assert payload == {
        "version": 4,
        "preferences": {
            "output_dir": "saved-outputs",
            "output_name_base": "custom-name",
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
        "export_profiles": [
            {
                "name": "Review",
                "output_formats": ["txt", "md"],
                "timestamps": True,
                "word_timestamps": False,
            }
        ],
    }


def test_normalize_gui_state_payload_supports_nested_and_legacy_formats(tmp_path: Path) -> None:
    media = tmp_path / "sample.mp4"
    media.write_bytes(b"media")
    transcript = tmp_path / "result.json"
    transcript.write_text("{}", encoding="utf-8")
    outputs = tmp_path / "outputs"
    outputs.mkdir()

    local_paths, checked, preferences, recent_work, export_profiles = _normalize_gui_state_payload(
        {
            "preferences": {
                "output_dir": "custom-out",
                "output_name_base": "phase4-note",
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
            "export_profiles": [
                {
                    "name": "Review",
                    "output_formats": ["txt", "md"],
                    "timestamps": True,
                    "word_timestamps": False,
                }
            ],
        }
    )

    assert local_paths == [media]
    assert checked == {str(media)}
    assert preferences["output_dir"] == "custom-out"
    assert preferences["output_name_base"] == "phase4-note"
    assert preferences["model_name"] == "medium"
    assert preferences["output_formats"] == ["txt", "vtt"]
    assert recent_work["recent_transcripts"] == [str(transcript)]
    assert recent_work["recent_output_dirs"] == [str(outputs)]
    assert export_profiles[0].name == "Review"
    assert export_profiles[0].output_formats == ("txt", "md")

    legacy_local_paths, legacy_checked, legacy_preferences, legacy_recent_work, legacy_profiles = _normalize_gui_state_payload(
        {
            "local_paths": [str(media)],
            "selected_paths": [str(media)],
            "output_dir": "legacy-out",
            "output_name_base": "legacy-name",
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
    assert legacy_preferences["output_name_base"] == "legacy-name"
    assert legacy_preferences["model_name"] == "tiny"
    assert legacy_preferences["language"] == "en"
    assert legacy_preferences["output_formats"] == ["json"]
    assert legacy_recent_work == {
        "recent_transcripts": [],
        "recent_output_dirs": [],
        "recent_jobs": [],
        "recent_media_bindings": [],
    }
    assert legacy_profiles == ()


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


def test_discover_transcript_output_paths_collects_known_sibling_formats(tmp_path: Path) -> None:
    transcript = tmp_path / "lesson.json"
    transcript.write_text("{}", encoding="utf-8")
    txt_output = tmp_path / "lesson.txt"
    txt_output.write_text("hello", encoding="utf-8")
    srt_output = tmp_path / "lesson.srt"
    srt_output.write_text("1", encoding="utf-8")
    ignored = tmp_path / "lesson.docx"
    ignored.write_text("ignore", encoding="utf-8")

    discovered = _discover_transcript_output_paths(transcript)

    assert discovered == (transcript.resolve(), txt_output.resolve(), srt_output.resolve())


def test_build_library_entry_merges_existing_outputs_and_updates_binding(tmp_path: Path) -> None:
    transcript = tmp_path / "lesson.json"
    transcript.write_text('{"source": "lesson.mp4", "segments": []}', encoding="utf-8")
    media = tmp_path / "lesson.mp4"
    media.write_bytes(b"media")
    txt_output = tmp_path / "lesson.txt"
    txt_output.write_text("hello", encoding="utf-8")
    md_output = tmp_path / "lesson.md"
    md_output.write_text("# hello", encoding="utf-8")

    existing = _build_library_entry(
        transcript,
        output_paths=(transcript, txt_output),
    )
    updated = _build_library_entry(
        transcript,
        existing=existing,
        media_path=media,
        output_paths=(transcript, md_output),
    )

    assert sorted(output.kind for output in updated.outputs) == ["json", "md", "txt"]
    assert updated.media_binding is not None
    assert updated.media_binding.media_path == media.resolve()
    assert updated.source_media_path == media.resolve()


def test_result_inference_helpers_detect_local_source_and_media(tmp_path: Path) -> None:
    media = tmp_path / "sample.mp4"
    media.write_bytes(b"media")
    transcript = tmp_path / "sample.json"
    transcript.write_text('{"source": "sample.mp4", "segments": []}', encoding="utf-8")
    txt_output = tmp_path / "sample.txt"
    txt_output.write_text("hello", encoding="utf-8")

    result = TranscriptionResult(
        job=TranscriptionJob(
            sources=(SourceSpec(kind="local", value=str(media)),),
            output_dir=tmp_path,
        ),
        outputs=(OutputArtifacts(paths=(transcript, txt_output)),),
    )

    assert _infer_library_source_kind_from_result(result) == "local"
    assert _infer_library_source_media_path_from_result(result, transcript) == media.resolve()


def test_library_entry_helpers_format_missing_status_and_dates(tmp_path: Path) -> None:
    transcript = tmp_path / "lesson.json"
    transcript.write_text("{}", encoding="utf-8")
    output_dir = tmp_path
    entry = _build_library_entry(transcript, output_dir=output_dir)

    assert _format_library_datetime(None) == "never"
    assert _library_entry_missing_summary(entry) == "ok"


def test_library_entry_list_label_includes_required_fields(tmp_path: Path) -> None:
    transcript = tmp_path / "lesson.json"
    transcript.write_text("{}", encoding="utf-8")
    output_dir = tmp_path / "outputs"
    output_dir.mkdir()

    entry = _build_library_entry(
        transcript,
        output_dir=output_dir,
        source_kind="url",
    )
    label = _library_entry_list_label(entry)

    assert "lesson" in label
    assert "Source: url" in label
    assert "Created:" in label
    assert "Last opened:" in label
    assert f"Output dir: {output_dir.resolve()}" in label
    assert "Missing: ok" in label


def test_sort_library_entries_prefers_last_opened_then_recent_updates(tmp_path: Path) -> None:
    first = tmp_path / "first.json"
    first.write_text("{}", encoding="utf-8")
    second = tmp_path / "second.json"
    second.write_text("{}", encoding="utf-8")
    output_dir = tmp_path / "outputs"
    output_dir.mkdir()

    older = _build_library_entry(
        first,
        output_dir=output_dir,
        opened_at=datetime(2026, 5, 15, 8, 0, 0),
    )
    newer = _build_library_entry(
        second,
        output_dir=output_dir,
        opened_at=datetime(2026, 5, 15, 9, 0, 0),
    )

    ordered = _sort_library_entries((older, newer))

    assert ordered == (newer, older)
