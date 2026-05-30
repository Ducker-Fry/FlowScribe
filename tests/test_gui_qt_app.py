from datetime import datetime
from pathlib import Path

from flowscribe.app.models import ProgressEvent, SourceSpec, TranscriptionJob, TranscriptionResult
from flowscribe.core.models import OutputArtifacts, TranscriptSegment
from flowscribe.gui.export_profiles import ExportProfile
from flowscribe.gui.utils import (
    _artifact_format_label,
    _artifact_summary,
    _build_library_entry,
    _discover_transcript_output_paths,
    _format_library_datetime,
    _gui_state_payload,
    _infer_library_source_kind_from_result,
    _infer_library_source_media_path_from_result,
    _library_entry_list_label,
    _library_entry_missing_summary,
    _library_results_summary,
    _model_access_guidance_text,
    _normalize_gui_preferences_payload,
    _normalize_recent_work_entry_paths,
    _onboarding_state_payload,
    _onboarding_summary_text,
    _progress_event_status_line,
    _recent_work_payload,
    _recent_transcript_list_label,
    _read_viewable_artifact_text,
    _render_progress_segment_line,
    _render_json_artifact_html,
    _sort_library_entries,
    _sort_workspace_artifact_paths,
    _url_media_status_suffix,
    _user_facing_doctor_message,
    _user_facing_folder_label,
    _user_facing_state_file_label,
    _view_preferences_payload,
    _view_tab_key_for_artifact,
    _view_tab_title_for_artifact,
    _normalize_viewable_artifact_paths,
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
            "provider_name": "bad-provider",
            "model_name": "bad-model",
            "language": "fr",
            "preset": "bad-preset",
            "output_formats": ["txt", "bad", "json"],
            "timestamps": False,
            "word_timestamps": True,
            "overwrite": True,
            "keep_media": True,
            "url_media_kind": "video",
            "url_media_output_dir": "saved-url-media",
            "url_auto_bind_media": False,
            "network_family": "bad-network",
            "proxy": 123,
            "native_threads": -1,
        }
    )

    assert preferences == {
        "output_dir": "outputs",
        "output_name_base": "",
        "provider_name": "local-whisper",
        "model_name": "small",
        "language": "auto",
        "preset": "none",
        "output_formats": ["txt", "json"],
        "timestamps": False,
        "word_timestamps": True,
        "overwrite": True,
        "keep_media": True,
        "url_media_kind": "video",
        "url_media_output_dir": "saved-url-media",
        "url_auto_bind_media": False,
        "network_family": "auto",
        "proxy": "",
        "theme": "light",
        "native_threads": None,
    }


def test_onboarding_state_payload_defaults_and_reads_help_seen_flag() -> None:
    assert _onboarding_state_payload(None) == {"help_seen": False}
    assert _onboarding_state_payload({"help_seen": True}) == {"help_seen": True}


def test_model_access_guidance_and_onboarding_summary_include_next_steps(tmp_path: Path) -> None:
    output_dir = tmp_path / "outputs"
    guidance = _model_access_guidance_text("small")
    summary = _onboarding_summary_text(
        output_dir=output_dir,
        model_name="small",
        capture_message="System audio capture is unavailable on this machine.",
    )

    assert "Hugging Face" in guidance
    assert "Output folder:" in summary
    assert str(output_dir) not in summary
    assert '"outputs"' in summary
    assert "Capture:" in summary


def test_user_facing_helpers_hide_local_paths_in_help_text(tmp_path: Path) -> None:
    folder = tmp_path / "my-secret-output"

    assert _user_facing_folder_label(folder) == '"my-secret-output"'
    assert "user profile" in _user_facing_state_file_label()
    assert _user_facing_doctor_message(
        "ffmpeg",
        True,
        r"ffmpeg version test (C:\secret\ffmpeg.exe)",
    ) == "ffmpeg is available."


def test_progress_event_status_line_and_segment_rendering_include_eta_and_speed() -> None:
    segment = TranscriptSegment(
        text="hello world",
        start_seconds=0.0,
        end_seconds=5.0,
    )
    event = ProgressEvent(
        stage="transcribe",
        message="Processed chunk 1/4.",
        processed_duration_seconds=30.0,
        total_duration_seconds=120.0,
        eta_seconds=90.0,
        realtime_factor=3.2,
        chunk_index=1,
        chunk_count=4,
        segments=(segment,),
    )

    assert "Progress: 00:30 / 02:00" in _progress_event_status_line(event)
    assert "Chunk: 1/4" in _progress_event_status_line(event)
    assert "Speed: 3.2x" in _progress_event_status_line(event)
    assert "ETA: 01:30" in _progress_event_status_line(event)
    assert _render_progress_segment_line(segment) == "[00:00 - 00:05] hello world"


def test_url_media_status_suffix_explains_saved_media_and_fallback() -> None:
    assert _url_media_status_suffix(
        OutputArtifacts(
            paths=(),
            media_path=Path("saved.mp4"),
            media_kind="video",
            requested_media_kind="video",
        )
    ) == "Saved video media."
    assert _url_media_status_suffix(
        OutputArtifacts(
            paths=(),
            media_path=Path("saved.m4a"),
            media_kind="audio",
            requested_media_kind="video",
            media_fallback=True,
        )
    ) == "Requested video media, saved audio instead."


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
            "provider_name": "native-engine",
            "model_name": "medium",
            "language": "zh",
            "preset": "zh",
            "output_formats": ["txt", "md"],
            "timestamps": True,
            "word_timestamps": False,
            "overwrite": False,
            "keep_media": False,
            "url_media_kind": "audio",
            "url_media_output_dir": "saved-url-media",
            "url_auto_bind_media": True,
            "network_family": "ipv4",
            "proxy": "http://127.0.0.1:7890",
            "native_threads": 8,
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
        "version": 7,
        "preferences": {
            "output_dir": "saved-outputs",
            "output_name_base": "custom-name",
            "provider_name": "native-engine",
            "model_name": "medium",
            "language": "zh",
            "preset": "zh",
            "output_formats": ["txt", "md"],
            "timestamps": True,
            "word_timestamps": False,
            "overwrite": False,
            "keep_media": False,
            "url_media_kind": "audio",
            "url_media_output_dir": "saved-url-media",
            "url_auto_bind_media": True,
            "network_family": "ipv4",
            "proxy": "http://127.0.0.1:7890",
            "theme": "light",
            "native_threads": 8,
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
        "view_preferences": {
            "visible_tabs": {
                "run_details": True,
                "transcript": True,
                "library": True,
                "queue": True,
            },
            "current_tab": "transcript",
        },
        "onboarding_state": {
            "help_seen": False,
        },
    }


def test_normalize_gui_state_payload_supports_nested_and_legacy_formats(tmp_path: Path) -> None:
    media = tmp_path / "sample.mp4"
    media.write_bytes(b"media")
    transcript = tmp_path / "result.json"
    transcript.write_text("{}", encoding="utf-8")
    outputs = tmp_path / "outputs"
    outputs.mkdir()

    local_paths, checked, preferences, recent_work, export_profiles, view_preferences, onboarding_state = _normalize_gui_state_payload(
        {
            "preferences": {
                "output_dir": "custom-out",
                "output_name_base": "phase4-note",
                "provider_name": "native-engine",
                "model_name": "medium",
                "language": "zh",
                "preset": "zh",
                "output_formats": ["txt", "vtt"],
                "timestamps": False,
                "word_timestamps": True,
                "overwrite": True,
                "keep_media": True,
                "url_media_kind": "video",
                "url_media_output_dir": "saved-url-media",
                "url_auto_bind_media": False,
                "network_family": "ipv4",
                "proxy": "http://127.0.0.1:7890",
                "native_threads": 4,
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
            "view_preferences": {
                "visible_tabs": {
                    "run_details": True,
                    "transcript": False,
                    "library": True,
                },
                "current_tab": "library",
            },
            "onboarding_state": {
                "help_seen": True,
            },
        }
    )

    assert local_paths == [media]
    assert checked == {str(media)}
    assert preferences["output_dir"] == "custom-out"
    assert preferences["output_name_base"] == "phase4-note"
    assert preferences["provider_name"] == "native-engine"
    assert preferences["model_name"] == "medium"
    assert preferences["output_formats"] == ["txt", "vtt"]
    assert preferences["url_media_kind"] == "video"
    assert preferences["url_media_output_dir"] == "saved-url-media"
    assert preferences["url_auto_bind_media"] is False
    assert preferences["native_threads"] == 4
    assert recent_work["recent_transcripts"] == [str(transcript)]
    assert recent_work["recent_output_dirs"] == [str(outputs)]
    assert export_profiles[0].name == "Review"
    assert export_profiles[0].output_formats == ("txt", "md")
    assert view_preferences == {
        "visible_tabs": {
            "run_details": True,
            "transcript": False,
            "library": True,
            "queue": True,
        },
        "current_tab": "library",
    }
    assert onboarding_state == {
        "help_seen": True,
    }

    legacy_local_paths, legacy_checked, legacy_preferences, legacy_recent_work, legacy_profiles, legacy_view_preferences, legacy_onboarding_state = _normalize_gui_state_payload(
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
    assert legacy_preferences["provider_name"] == "local-whisper"
    assert legacy_preferences["model_name"] == "tiny"
    assert legacy_preferences["language"] == "en"
    assert legacy_preferences["output_formats"] == ["json"]
    assert legacy_preferences["url_media_kind"] == "audio"
    assert legacy_preferences["url_media_output_dir"] == ""
    assert legacy_preferences["url_auto_bind_media"] is True
    assert legacy_recent_work == {
        "recent_transcripts": [],
        "recent_output_dirs": [],
        "recent_jobs": [],
        "recent_media_bindings": [],
    }
    assert legacy_profiles == ()
    assert legacy_view_preferences == {
        "visible_tabs": {
            "run_details": True,
            "transcript": True,
            "library": True,
            "queue": True,
        },
        "current_tab": "transcript",
    }
    assert legacy_onboarding_state == {
        "help_seen": False,
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


def test_view_preferences_payload_keeps_valid_state_and_falls_back_safely() -> None:
    assert _view_preferences_payload(
        {
            "visible_tabs": {
                "run_details": False,
                "transcript": False,
                "library": False,
                "queue": False,
            },
            "current_tab": "library",
        }
    ) == {
        "visible_tabs": {
            "run_details": False,
            "transcript": True,
            "library": False,
            "queue": False,
        },
        "current_tab": "transcript",
    }


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


def test_normalize_viewable_artifact_paths_filters_duplicates_and_unsupported_files(tmp_path: Path) -> None:
    transcript = tmp_path / "lesson.json"
    transcript.write_text("{}", encoding="utf-8")
    txt_output = tmp_path / "lesson.txt"
    txt_output.write_text("hello", encoding="utf-8")
    unsupported = tmp_path / "lesson.docx"
    unsupported.write_text("ignore", encoding="utf-8")

    normalized = _normalize_viewable_artifact_paths(
        (transcript, txt_output, transcript, unsupported)
    )

    assert normalized == (transcript.resolve(), txt_output.resolve())


def test_view_artifact_helpers_build_stable_keys_titles_and_text(tmp_path: Path) -> None:
    artifact = tmp_path / "lesson.srt"
    artifact.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello\n", encoding="utf-8")

    assert _view_tab_key_for_artifact(artifact.resolve()).startswith("artifact:")
    assert _artifact_format_label(artifact.resolve()) == "SRT Subtitles"
    assert _view_tab_title_for_artifact(artifact.resolve()) == "SRT Subtitles - lesson.srt"
    assert "Hello" in _read_viewable_artifact_text(artifact)
    assert "cues: 1" in _artifact_summary(artifact.resolve(), _read_viewable_artifact_text(artifact))


def test_view_artifact_helpers_pretty_print_json_and_sort_compare_targets(tmp_path: Path) -> None:
    transcript = tmp_path / "lesson.json"
    transcript.write_text('{"segments":[{"index":1,"text":"Hello"}]}', encoding="utf-8")
    corrected = tmp_path / "lesson.corrected.json"
    corrected.write_text(
        '{"segments":[{"index":1,"text":"Hello","correction":{"edited":true}}]}',
        encoding="utf-8",
    )
    srt_output = tmp_path / "lesson.srt"
    srt_output.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello\n", encoding="utf-8")
    txt_output = tmp_path / "lesson.txt"
    txt_output.write_text("Hello\n", encoding="utf-8")

    rendered_json = _read_viewable_artifact_text(transcript)
    rendered_corrected = _read_viewable_artifact_text(corrected)
    rendered_html = _render_json_artifact_html(transcript.resolve(), rendered_json)

    assert '"segments": [' in rendered_json
    assert "Full transcript" in rendered_html
    assert "Segment 1" in rendered_html
    assert "edited: 1" in _artifact_summary(corrected.resolve(), rendered_corrected)
    assert _sort_workspace_artifact_paths(
        (txt_output.resolve(), corrected.resolve(), srt_output.resolve(), transcript.resolve())
    ) == (
        transcript.resolve(),
        corrected.resolve(),
        srt_output.resolve(),
        txt_output.resolve(),
    )


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
    assert "Showing 1 of 1 transcript entry" in _library_results_summary((entry,), total_count=1)


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


def test_recent_transcript_list_label_includes_library_metadata_when_available(tmp_path: Path) -> None:
    transcript = tmp_path / "lesson.json"
    transcript.write_text("{}", encoding="utf-8")
    output_dir = tmp_path / "outputs"
    output_dir.mkdir()
    entry = _build_library_entry(
        transcript,
        output_dir=output_dir,
        source_kind="local",
        opened_at=datetime(2026, 5, 16, 9, 0, 0),
    )

    label = _recent_transcript_list_label(transcript.resolve(), entry=entry)

    assert "lesson.json | Source: local | Missing: ok" in label
    assert "Last opened: 2026-05-16 09:00:00" in label


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
