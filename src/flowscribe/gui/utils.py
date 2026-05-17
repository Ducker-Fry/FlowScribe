"""Stateless pure functions for the GUI layer.

All functions here are free of PySide6 dependencies and operate on
standard library types and domain models only.
"""

from __future__ import annotations

import json
from datetime import datetime
from html import escape
from pathlib import Path

from flowscribe.app.models import ProgressEvent
from flowscribe.cli.doctor import resolve_faster_whisper_repo
from flowscribe.core.models import OutputArtifacts
from flowscribe.gui.export_profiles import (
    ExportProfile,
    export_profiles_payload,
    normalize_export_profiles_payload,
)
from flowscribe.gui.state import SUPPORTED_GUI_FORMATS, is_acceptable_local_source
from flowscribe.gui.transcript_viewer import (
    load_transcript_view,
    resolve_transcript_media_path,
)
from flowscribe.library import (
    LibraryMediaBinding,
    LibraryOutputRecord,
    TranscriptLibraryEntry,
    sort_transcript_library_entries,
)
from flowscribe.output.time_format import format_timestamp

GUI_MODEL_OPTIONS = ("small", "tiny", "base", "medium", "large-v3-turbo", "large-v3")
GUI_LANGUAGE_OPTIONS = ("auto", "zh", "en")
GUI_PRESET_OPTIONS = ("none", "zh")
GUI_NETWORK_OPTIONS = ("auto", "ipv4", "ipv6")
DEFAULT_GUI_PREFERENCES = {
    "output_dir": "outputs",
    "output_name_base": "",
    "model_name": "small",
    "language": "auto",
    "preset": "none",
    "output_formats": ["txt", "md", "json"],
    "timestamps": True,
    "word_timestamps": False,
    "overwrite": False,
    "keep_media": False,
    "url_media_kind": "audio",
    "url_media_output_dir": "",
    "url_auto_bind_media": True,
    "network_family": "auto",
    "proxy": "",
}
DEFAULT_VIEW_PREFERENCES = {
    "visible_tabs": {
        "run_details": True,
        "transcript": True,
        "library": True,
        "queue": True,
    },
    "current_tab": "transcript",
}
DEFAULT_ONBOARDING_STATE = {
    "help_seen": False,
}
MAX_RECENT_TRANSCRIPTS = 8
MAX_RECENT_OUTPUT_DIRS = 8
MAX_RECENT_JOBS = 10
MAX_RECENT_MEDIA_BINDINGS = 8
LIBRARY_OUTPUT_SUFFIXES = (".txt", ".md", ".json", ".srt", ".vtt")
VIEW_ARTIFACT_SUFFIXES = (".json", ".txt", ".md", ".srt", ".vtt")


def _default_recent_work() -> dict[str, list[dict[str, object]] | list[str]]:
    return {
        "recent_transcripts": [],
        "recent_output_dirs": [],
        "recent_jobs": [],
        "recent_media_bindings": [],
    }


def _normalize_local_source_state_payload(payload: object) -> tuple[list[Path], set[str]]:
    if not isinstance(payload, dict):
        return [], set()

    saved_paths = payload.get("local_paths")
    checked_paths = payload.get("checked_paths")
    if checked_paths is None:
        checked_paths = payload.get("selected_paths")
    if not isinstance(saved_paths, list):
        return [], set()

    local_paths: list[Path] = []
    for raw_path in saved_paths:
        candidate = Path(str(raw_path))
        if is_acceptable_local_source(candidate):
            local_paths.append(candidate)

    checked = {
        str(Path(str(raw_path)))
        for raw_path in (checked_paths or [])
        if isinstance(raw_path, str)
    }
    return local_paths, checked


def _local_source_state_payload(paths: list[Path], checked_paths: list[Path]) -> dict:
    return {
        "local_paths": [str(item) for item in paths],
        "checked_paths": [str(item) for item in checked_paths],
    }


def _gui_preferences_payload(preferences: dict[str, object]) -> dict[str, object]:
    payload = _normalize_gui_preferences_payload(preferences)
    payload["output_formats"] = list(payload["output_formats"])
    return payload


def _normalize_gui_preferences_payload(payload: object) -> dict[str, object]:
    source = payload if isinstance(payload, dict) else {}
    if isinstance(source.get("preferences"), dict):
        source = source["preferences"]

    output_formats = source.get("output_formats")
    normalized_formats = [
        output_format
        for output_format in (output_formats or [])
        if output_format in SUPPORTED_GUI_FORMATS
    ]

    output_dir = source.get("output_dir")
    output_name_base = source.get("output_name_base")
    model_name = source.get("model_name")
    language = source.get("language")
    preset = source.get("preset")
    url_media_kind = source.get("url_media_kind")
    url_media_output_dir = source.get("url_media_output_dir")
    network_family = source.get("network_family")
    proxy = source.get("proxy")

    return {
        "output_dir": output_dir if isinstance(output_dir, str) and output_dir.strip() else "outputs",
        "output_name_base": output_name_base if isinstance(output_name_base, str) else "",
        "model_name": model_name if model_name in GUI_MODEL_OPTIONS else "small",
        "language": language if language in GUI_LANGUAGE_OPTIONS else "auto",
        "preset": preset if preset in GUI_PRESET_OPTIONS else "none",
        "output_formats": normalized_formats or ["txt", "md", "json"],
        "timestamps": bool(source.get("timestamps", True)),
        "word_timestamps": bool(source.get("word_timestamps", False)),
        "overwrite": bool(source.get("overwrite", False)),
        "keep_media": bool(source.get("keep_media", False)),
        "url_media_kind": url_media_kind if url_media_kind in {"audio", "video"} else "audio",
        "url_media_output_dir": (
            url_media_output_dir if isinstance(url_media_output_dir, str) else ""
        ),
        "url_auto_bind_media": bool(source.get("url_auto_bind_media", True)),
        "network_family": network_family if network_family in GUI_NETWORK_OPTIONS else "auto",
        "proxy": proxy if isinstance(proxy, str) else "",
    }


def _gui_state_payload(
    paths: list[Path],
    checked_paths: list[Path],
    preferences: dict[str, object],
    recent_work: dict[str, list[dict[str, object]] | list[str]] | None = None,
    export_profiles: tuple[ExportProfile, ...] = (),
    view_preferences: dict[str, object] | None = None,
    onboarding_state: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "version": 7,
        "preferences": _gui_preferences_payload(preferences),
        "local_sources": _local_source_state_payload(paths, checked_paths),
        "recent_work": _recent_work_payload(recent_work),
        "export_profiles": export_profiles_payload(export_profiles),
        "view_preferences": _view_preferences_payload(view_preferences),
        "onboarding_state": _onboarding_state_payload(onboarding_state),
    }


def _view_preferences_payload(preferences: object) -> dict[str, object]:
    source = preferences if isinstance(preferences, dict) else {}
    visible_tabs_source = source.get("visible_tabs")
    current_tab = source.get("current_tab")

    normalized_visible_tabs: dict[str, bool] = {}
    if isinstance(visible_tabs_source, dict):
        for key in DEFAULT_VIEW_PREFERENCES["visible_tabs"]:
            normalized_visible_tabs[key] = bool(
                visible_tabs_source.get(
                    key,
                    DEFAULT_VIEW_PREFERENCES["visible_tabs"][key],
                )
            )
    else:
        normalized_visible_tabs = dict(DEFAULT_VIEW_PREFERENCES["visible_tabs"])

    if not any(normalized_visible_tabs.values()):
        normalized_visible_tabs["transcript"] = True

    normalized_current_tab = (
        current_tab
        if isinstance(current_tab, str) and current_tab in normalized_visible_tabs
        else "transcript"
    )
    if not normalized_visible_tabs.get(normalized_current_tab, False):
        normalized_current_tab = next(
            key for key, visible in normalized_visible_tabs.items() if visible
        )

    return {
        "visible_tabs": normalized_visible_tabs,
        "current_tab": normalized_current_tab,
    }


def _onboarding_state_payload(payload: object) -> dict[str, object]:
    source = payload if isinstance(payload, dict) else {}
    return {
        "help_seen": bool(source.get("help_seen", False)),
    }


def _normalize_recent_work_entry_paths(
    values: object,
    *,
    max_items: int,
    expect_directory: bool = False,
) -> list[str]:
    if not isinstance(values, list):
        return []

    seen: set[str] = set()
    normalized: list[str] = []
    for raw_value in values:
        if not isinstance(raw_value, str) or not raw_value.strip():
            continue
        try:
            path = Path(raw_value)
        except OSError:
            continue
        path_text = str(path)
        if path_text in seen:
            continue
        if path.exists():
            if expect_directory and not path.is_dir():
                continue
            if not expect_directory and not path.is_file():
                continue
        seen.add(path_text)
        normalized.append(path_text)
        if len(normalized) >= max_items:
            break
    return normalized


def _normalize_recent_job_entries(values: object) -> list[dict[str, str]]:
    if not isinstance(values, list):
        return []

    normalized: list[dict[str, str]] = []
    seen: set[tuple[str, str, str, str, str]] = set()
    for raw_value in values:
        if not isinstance(raw_value, dict):
            continue

        label = raw_value.get("label")
        status = raw_value.get("status")
        output_dir = raw_value.get("output_dir")
        transcript_path = raw_value.get("transcript_path")
        media_path = raw_value.get("media_path")

        if not isinstance(label, str) or not label.strip():
            continue
        if not isinstance(status, str) or not status.strip():
            continue
        if not isinstance(output_dir, str) or not output_dir.strip():
            continue
        if transcript_path is not None and not isinstance(transcript_path, str):
            transcript_path = None
        if media_path is not None and not isinstance(media_path, str):
            media_path = None

        identity = (
            label.strip(),
            status.strip(),
            output_dir.strip(),
            (transcript_path or "").strip(),
            (media_path or "").strip(),
        )
        if identity in seen:
            continue
        seen.add(identity)
        normalized.append(
            {
                "label": identity[0],
                "status": identity[1],
                "output_dir": identity[2],
                "transcript_path": identity[3],
                "media_path": identity[4],
            }
        )
        if len(normalized) >= MAX_RECENT_JOBS:
            break
    return normalized


def _normalize_recent_media_bindings(values: object) -> list[dict[str, str]]:
    if not isinstance(values, list):
        return []

    normalized: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for raw_value in values:
        if not isinstance(raw_value, dict):
            continue
        transcript_path = raw_value.get("transcript_path")
        media_path = raw_value.get("media_path")
        if not isinstance(transcript_path, str) or not transcript_path.strip():
            continue
        if not isinstance(media_path, str) or not media_path.strip():
            continue
        identity = (transcript_path.strip(), media_path.strip())
        if identity in seen:
            continue
        seen.add(identity)
        normalized.append(
            {
                "transcript_path": identity[0],
                "media_path": identity[1],
            }
        )
        if len(normalized) >= MAX_RECENT_MEDIA_BINDINGS:
            break
    return normalized


def _recent_work_payload(payload: object) -> dict[str, list[dict[str, object]] | list[str]]:
    source = payload if isinstance(payload, dict) else {}
    return {
        "recent_transcripts": _normalize_recent_work_entry_paths(
            source.get("recent_transcripts"),
            max_items=MAX_RECENT_TRANSCRIPTS,
        ),
        "recent_output_dirs": _normalize_recent_work_entry_paths(
            source.get("recent_output_dirs"),
            max_items=MAX_RECENT_OUTPUT_DIRS,
            expect_directory=True,
        ),
        "recent_jobs": _normalize_recent_job_entries(source.get("recent_jobs")),
        "recent_media_bindings": _normalize_recent_media_bindings(
            source.get("recent_media_bindings")
        ),
    }


def _normalize_gui_state_payload(
    payload: object,
) -> tuple[
    list[Path],
    set[str],
    dict[str, object],
    dict[str, list[dict[str, object]] | list[str]],
    tuple[ExportProfile, ...],
    dict[str, object],
    dict[str, object],
]:
    if not isinstance(payload, dict):
        return (
            [],
            set(),
            _gui_preferences_payload(DEFAULT_GUI_PREFERENCES),
            _default_recent_work(),
            (),
            _view_preferences_payload(DEFAULT_VIEW_PREFERENCES),
            _onboarding_state_payload(DEFAULT_ONBOARDING_STATE),
        )

    local_payload = payload.get("local_sources") if isinstance(payload.get("local_sources"), dict) else payload
    local_paths, checked = _normalize_local_source_state_payload(local_payload)
    preferences = _normalize_gui_preferences_payload(payload)
    recent_work = _recent_work_payload(payload.get("recent_work"))
    profiles = normalize_export_profiles_payload(payload.get("export_profiles"))
    view_preferences = _view_preferences_payload(payload.get("view_preferences"))
    onboarding_state = _onboarding_state_payload(payload.get("onboarding_state"))
    return (
        local_paths,
        checked,
        preferences,
        recent_work,
        profiles,
        view_preferences,
        onboarding_state,
    )


def _transcript_output_records_from_paths(paths: tuple[Path, ...]) -> tuple[LibraryOutputRecord, ...]:
    seen: set[Path] = set()
    records: list[LibraryOutputRecord] = []
    for path in paths:
        try:
            normalized = path.expanduser().resolve()
        except OSError:
            normalized = path
        if normalized in seen:
            continue
        seen.add(normalized)
        records.append(LibraryOutputRecord.from_path(normalized))
    return tuple(records)


def _discover_transcript_output_paths(transcript_path: Path) -> tuple[Path, ...]:
    try:
        normalized = transcript_path.expanduser().resolve()
    except OSError:
        normalized = transcript_path
    discovered: list[Path] = []
    if normalized.is_file():
        discovered.append(normalized)
    for suffix in LIBRARY_OUTPUT_SUFFIXES:
        candidate = normalized.with_suffix(suffix)
        if candidate == normalized:
            continue
        if candidate.is_file():
            discovered.append(candidate)
    return tuple(discovered)


def _is_viewable_artifact_path(path: Path) -> bool:
    return path.suffix.lower() in VIEW_ARTIFACT_SUFFIXES


def _normalize_viewable_artifact_paths(paths: tuple[Path, ...]) -> tuple[Path, ...]:
    normalized: list[Path] = []
    seen: set[Path] = set()
    for path in paths:
        if not _is_viewable_artifact_path(path):
            continue
        try:
            candidate = path.expanduser().resolve()
        except OSError:
            candidate = path
        if candidate in seen:
            continue
        seen.add(candidate)
        normalized.append(candidate)
    return tuple(normalized)


def _view_tab_key_for_artifact(path: Path) -> str:
    return f"artifact:{str(path).lower()}"


def _artifact_format_label(path: Path) -> str:
    suffix = path.suffix.lower()
    stem = path.stem.lower()
    if suffix == ".json":
        if ".corrected" in stem:
            return "Corrected JSON"
        return "Transcript JSON"
    if suffix == ".txt":
        return "Text Export"
    if suffix == ".md":
        return "Markdown Export"
    if suffix == ".srt":
        return "SRT Subtitles"
    if suffix == ".vtt":
        return "VTT Subtitles"
    return f"{suffix.lstrip('.').upper() or 'File'} Artifact"


def _artifact_compare_group(path: Path) -> str:
    suffix = path.suffix.lower()
    stem = path.stem.lower()
    if suffix == ".json":
        if ".corrected" in stem:
            return "corrected_json"
        return "transcript_json"
    if suffix == ".srt":
        return "srt"
    if suffix == ".vtt":
        return "vtt"
    if suffix == ".md":
        return "md"
    if suffix == ".txt":
        return "txt"
    return "other"


def _sort_workspace_artifact_paths(paths: tuple[Path, ...]) -> tuple[Path, ...]:
    priorities = {
        "transcript_json": 0,
        "corrected_json": 1,
        "srt": 2,
        "vtt": 3,
        "md": 4,
        "txt": 5,
        "other": 6,
    }
    return tuple(
        sorted(
            paths,
            key=lambda path: (
                priorities.get(_artifact_compare_group(path), 99),
                path.name.lower(),
            ),
        )
    )


def _view_tab_title_for_artifact(path: Path) -> str:
    return f"{_artifact_format_label(path)} - {path.name}"


def _artifact_selector_label(path: Path) -> str:
    return f"{_artifact_format_label(path)} | {path.name}"


def _url_media_status_suffix(artifacts: OutputArtifacts) -> str:
    if artifacts.media_path is None or artifacts.requested_media_kind is None:
        return ""
    if artifacts.media_fallback and artifacts.media_kind is not None:
        return (
            f"Requested {artifacts.requested_media_kind} media, "
            f"saved {artifacts.media_kind} instead."
        )
    if artifacts.media_kind is not None:
        return f"Saved {artifacts.media_kind} media."
    return ""


def _normalize_subtitle_artifact_text(path: Path, text: str) -> str:
    lines = [line.rstrip() for line in text.replace("\r\n", "\n").split("\n")]
    normalized_lines: list[str] = []
    blank_pending = False
    for line in lines:
        if not line.strip():
            if normalized_lines and not blank_pending:
                normalized_lines.append("")
            blank_pending = True
            continue
        blank_pending = False
        normalized_lines.append(line)
    normalized = "\n".join(normalized_lines).strip()
    if path.suffix.lower() == ".vtt" and normalized and not normalized.startswith("WEBVTT"):
        normalized = "WEBVTT\n\n" + normalized
    return normalized + ("\n" if normalized else "")


def _subtitle_cue_count(text: str) -> int:
    blocks = [block for block in text.strip().split("\n\n") if block.strip()]
    count = 0
    for block in blocks:
        if "-->" in block:
            count += 1
    return count


def _artifact_summary(path: Path, text: str) -> str:
    format_label = _artifact_format_label(path)
    if path.suffix.lower() == ".json":
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            return f"{format_label} | raw JSON view"
        segments = payload.get("segments")
        segment_count = len(segments) if isinstance(segments, list) else 0
        edited_count = 0
        if isinstance(segments, list):
            edited_count = sum(
                1
                for segment in segments
                if isinstance(segment, dict)
                and isinstance(segment.get("correction"), dict)
                and segment["correction"].get("edited") is True
            )
        if edited_count:
            return f"{format_label} | segments: {segment_count} | edited: {edited_count}"
        return f"{format_label} | segments: {segment_count}"
    if path.suffix.lower() in {".srt", ".vtt"}:
        return f"{format_label} | cues: {_subtitle_cue_count(text)}"
    line_count = len(text.splitlines())
    return f"{format_label} | lines: {line_count}"


def _compact_duration_label(value: float | None) -> str:
    if value is None:
        return "?"
    total_seconds = max(0, int(round(value)))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


def _render_progress_segment_line(segment) -> str:
    start_label = _compact_duration_label(segment.start_seconds)
    end_label = _compact_duration_label(segment.end_seconds)
    text = segment.text.strip() or "(no text)"
    return f"[{start_label} - {end_label}] {text}"


def _progress_event_status_line(event: ProgressEvent) -> str:
    parts: list[str] = []
    if (
        event.processed_duration_seconds is not None
        and event.total_duration_seconds is not None
        and event.total_duration_seconds > 0
    ):
        parts.append(
            "Progress: "
            f"{_compact_duration_label(event.processed_duration_seconds)} / "
            f"{_compact_duration_label(event.total_duration_seconds)}"
        )
    if event.chunk_index is not None and event.chunk_count is not None:
        chunk_text = f"Chunk: {event.chunk_index}/{event.chunk_count}"
        if event.failed_chunks is not None and event.failed_chunks > 0:
            chunk_text += f" ({event.failed_chunks} failed)"
        parts.append(chunk_text)
    if event.realtime_factor is not None:
        parts.append(f"Speed: {event.realtime_factor:.1f}x")
    if event.eta_seconds is not None:
        parts.append(f"ETA: {_compact_duration_label(event.eta_seconds)}")
    return " | ".join(parts)


def _render_json_artifact_html(path: Path, text: str) -> str:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return (
            "<h3>JSON preview</h3>"
            "<p>FlowScribe could not turn this file into a friendly summary, so it is shown as raw JSON.</p>"
            f"<pre>{escape(text)}</pre>"
        )

    source = escape(str(payload.get("source") or "Unknown source"))
    language = escape(str(payload.get("language") or "Unknown"))
    model = escape(str(payload.get("model") or "Unknown"))
    transcript_text = escape(str(payload.get("text") or ""))
    segments = payload.get("segments")
    segment_list = segments if isinstance(segments, list) else []
    edited_count = sum(
        1
        for segment in segment_list
        if isinstance(segment, dict)
        and isinstance(segment.get("correction"), dict)
        and segment["correction"].get("edited") is True
    )

    segment_items: list[str] = []
    for raw_segment in segment_list:
        if not isinstance(raw_segment, dict):
            continue
        index = raw_segment.get("index")
        start_seconds = raw_segment.get("start_seconds")
        end_seconds = raw_segment.get("end_seconds")
        segment_text = escape(str(raw_segment.get("text") or ""))
        original_text = ""
        correction = raw_segment.get("correction")
        if isinstance(correction, dict) and correction.get("edited") is True:
            original_text = escape(str(correction.get("original_text") or ""))
        start_label = (
            format_timestamp(float(start_seconds))
            if isinstance(start_seconds, (int, float))
            else "unknown"
        )
        end_label = (
            format_timestamp(float(end_seconds))
            if isinstance(end_seconds, (int, float))
            else "unknown"
        )
        segment_block = (
            f"<div style='margin:0 0 12px 0; padding:10px; border:1px solid #555; border-radius:6px;'>"
            f"<div><strong>Segment {escape(str(index or '?'))}</strong> | {start_label} - {end_label}</div>"
            f"<div style='margin-top:6px;'>{segment_text or '<em>No text</em>'}</div>"
        )
        if original_text:
            segment_block += (
                f"<div style='margin-top:6px; color:#c9b27c;'><strong>Original:</strong> {original_text}</div>"
            )
        segment_block += "</div>"
        segment_items.append(segment_block)

    transcript_section = (
        f"<div style='margin:12px 0; padding:10px; border:1px solid #555; border-radius:6px;'>"
        f"<div><strong>Full transcript</strong></div>"
        f"<div style='margin-top:6px; white-space:pre-wrap;'>{transcript_text or '<em>No transcript text</em>'}</div>"
        f"</div>"
    )

    segment_section = "".join(segment_items) or "<p>No segment list is available in this JSON file.</p>"
    edited_note = f"<li>Edited segments: {edited_count}</li>" if edited_count else ""

    return (
        "<html><body>"
        f"<h3 style='margin-bottom:8px;'>{escape(_artifact_format_label(path))}</h3>"
        "<ul>"
        f"<li>Source: {source}</li>"
        f"<li>Language: {language}</li>"
        f"<li>Model: {model}</li>"
        f"<li>Segments: {len(segment_list)}</li>"
        f"{edited_note}"
        "</ul>"
        f"{transcript_section}"
        "<h4>Segments</h4>"
        f"{segment_section}"
        "</body></html>"
    )


def _render_viewable_artifact_text(path: Path, text: str) -> str:
    suffix = path.suffix.lower()
    if suffix == ".json":
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            return text
        return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if suffix in {".srt", ".vtt"}:
        return _normalize_subtitle_artifact_text(path, text)
    return text


def _read_viewable_artifact_text(path: Path) -> str:
    for encoding in ("utf-8", "utf-8-sig", "utf-16"):
        try:
            return _render_viewable_artifact_text(path, path.read_text(encoding=encoding))
        except UnicodeError:
            continue
    return _render_viewable_artifact_text(
        path,
        path.read_text(encoding="utf-8", errors="replace"),
    )


def _resolve_library_source_media_path(transcript_path: Path) -> Path | None:
    try:
        view = load_transcript_view(transcript_path)
    except ValueError:
        return None
    return resolve_transcript_media_path(view)


def _infer_library_source_kind_from_result(result) -> str:
    kinds = {
        source.kind
        for source in result.job.sources
        if getattr(source, "kind", None) in {"local", "url", "capture"}
    }
    if len(kinds) == 1:
        return next(iter(kinds))
    return "unknown"


def _infer_library_source_media_path_from_result(result, transcript_path: Path) -> Path | None:
    if len(result.job.sources) == 1:
        source = result.job.sources[0]
        if source.kind == "local":
            candidate = Path(source.value)
            if candidate.is_file():
                return candidate.resolve()
    return _resolve_library_source_media_path(transcript_path)


def _merge_library_output_records(
    existing: tuple[LibraryOutputRecord, ...],
    incoming: tuple[LibraryOutputRecord, ...],
) -> tuple[LibraryOutputRecord, ...]:
    merged: dict[Path, LibraryOutputRecord] = {}
    for record in existing + incoming:
        merged[record.path] = record
    return tuple(merged.values())


def _build_library_entry(
    transcript_path: Path,
    *,
    output_dir: Path | None = None,
    source_kind: str = "unknown",
    source_media_path: Path | None = None,
    media_path: Path | None = None,
    output_paths: tuple[Path, ...] | None = None,
    opened_at: datetime | None = None,
    existing: TranscriptLibraryEntry | None = None,
) -> TranscriptLibraryEntry:
    normalized_transcript = transcript_path.expanduser().resolve()
    resolved_output_dir = (
        output_dir.expanduser().resolve()
        if output_dir is not None
        else normalized_transcript.parent.resolve()
    )
    discovered_output_paths = (
        output_paths
        if output_paths is not None
        else _discover_transcript_output_paths(normalized_transcript)
    )
    merged_outputs = _merge_library_output_records(
        existing.outputs if existing is not None else (),
        _transcript_output_records_from_paths(discovered_output_paths),
    )
    effective_source_media_path = (
        source_media_path
        or (existing.source_media_path if existing is not None else None)
        or _resolve_library_source_media_path(normalized_transcript)
    )
    effective_source_kind = source_kind
    if effective_source_kind == "unknown" and existing is not None:
        effective_source_kind = existing.source_kind
    media_binding = existing.media_binding if existing is not None else None
    if media_path is not None:
        media_binding = LibraryMediaBinding.create(
            transcript_path=normalized_transcript,
            media_path=media_path,
            binding_type="manual",
            updated_at=opened_at or datetime.now(),
        )
    last_opened_at = opened_at if opened_at is not None else (existing.last_opened_at if existing else None)
    created_at = existing.created_at if existing is not None else (opened_at or datetime.now())

    return TranscriptLibraryEntry.create(
        transcript_path=normalized_transcript,
        output_dir=resolved_output_dir,
        display_label=normalized_transcript.stem,
        source_kind=effective_source_kind,
        source_media_path=effective_source_media_path,
        created_at=created_at,
        updated_at=opened_at or datetime.now(),
        last_opened_at=last_opened_at,
        media_binding=media_binding,
        outputs=merged_outputs,
    )


def _format_library_datetime(value: datetime | None) -> str:
    if value is None:
        return "never"
    return value.strftime("%Y-%m-%d %H:%M:%S")


def _library_entry_missing_summary(entry: TranscriptLibraryEntry) -> str:
    if not entry.missing_paths:
        return "ok"
    return ", ".join(entry.missing_paths)


def _sort_library_entries(
    entries: tuple[TranscriptLibraryEntry, ...],
) -> tuple[TranscriptLibraryEntry, ...]:
    return sort_transcript_library_entries(entries)


def _library_results_summary(
    entries: tuple[TranscriptLibraryEntry, ...],
    *,
    total_count: int,
) -> str:
    missing_count = sum(1 for entry in entries if entry.missing)
    opened_count = sum(1 for entry in entries if entry.last_opened_at is not None)
    return (
        f"Showing {len(entries)} of {total_count} transcript entr{'y' if total_count == 1 else 'ies'}"
        f" | missing: {missing_count}"
        f" | opened: {opened_count}"
    )


def _recent_transcript_list_label(
    transcript_path: Path,
    *,
    entry: TranscriptLibraryEntry | None = None,
) -> str:
    if entry is None:
        return f"{transcript_path.name}\n{transcript_path}"
    return "\n".join(
        [
            f"{transcript_path.name} | Source: {entry.source_kind} | Missing: {_library_entry_missing_summary(entry)}",
            f"Last opened: {_format_library_datetime(entry.last_opened_at)} | Output dir: {entry.output_dir}",
        ]
    )


def _model_access_guidance_text(model_name: str) -> str:
    repo_id = resolve_faster_whisper_repo(model_name)
    if repo_id is not None:
        return (
            f"Model `{model_name}` will use `{repo_id}`. "
            "The first real transcription may download model files from Hugging Face."
        )
    model_path = Path(model_name).expanduser()
    if model_path.exists():
        return f"Model path is local: {model_path.resolve()}"
    return (
        f"Model `{model_name}` is custom. Make sure it is a valid local path or a known "
        "faster-whisper model name before you start."
    )


def _user_facing_folder_label(path: Path) -> str:
    name = path.expanduser().name.strip()
    if name:
        return f'"{name}"'
    return "your selected folder"


def _user_facing_state_file_label() -> str:
    return "your FlowScribe app settings file in the user profile"


def _user_facing_doctor_message(check_name: str, ok: bool, message: str) -> str:
    if check_name == "Output directory":
        if ok:
            return "Current output folder is writable."
        return "Current output folder is not writable. Choose another folder or check permissions."
    if check_name == "faster-whisper":
        if ok:
            return "faster-whisper is installed and ready."
        return "faster-whisper is unavailable. Install the required package before running transcription."
    if check_name == "ffmpeg":
        if ok:
            return "ffmpeg is available."
        return "ffmpeg is unavailable. Install ffmpeg or use a packaged release build."
    return message


def _onboarding_summary_text(
    *,
    output_dir: Path,
    model_name: str,
    capture_message: str,
) -> str:
    return (
        f"Output folder: {_user_facing_folder_label(output_dir)} | "
        f"{_model_access_guidance_text(model_name)} | "
        f"Capture: {capture_message}"
    )


def _library_entry_list_label(entry: TranscriptLibraryEntry) -> str:
    return "\n".join(
        [
            entry.display_label,
            (
                f"Source: {entry.source_kind} | "
                f"Created: {_format_library_datetime(entry.created_at)} | "
                f"Last opened: {_format_library_datetime(entry.last_opened_at)}"
            ),
            (
                f"Output dir: {entry.output_dir} | "
                f"Missing: {_library_entry_missing_summary(entry)}"
            ),
        ]
    )
