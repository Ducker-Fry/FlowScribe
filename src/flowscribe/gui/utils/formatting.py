"""Formatting and rendering functions for the GUI layer.

All functions here are stateless pure functions that format data for display.
"""

from __future__ import annotations

import json
from datetime import datetime
from html import escape
from pathlib import Path

from flowscribe.tasks.models import ProgressEvent
from flowscribe.core.models import OutputArtifacts
from flowscribe.model_catalog import resolve_faster_whisper_repo
from flowscribe.output.time_format import format_timestamp


def _format_elapsed_time(seconds: float | None) -> str:
    """Format elapsed time in human-readable form (e.g., '2m 34s', '1h 5m 23s')."""
    if seconds is None:
        return ""
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s"
    minutes = seconds // 60
    secs = seconds % 60
    if minutes < 60:
        return f"{minutes}m {secs}s"
    hours = minutes // 60
    mins = minutes % 60
    return f"{hours}h {mins}m {secs}s"


def _compact_duration_label(value: float | None) -> str:
    if value is None:
        return "?"
    total_seconds = max(0, int(round(value)))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


def _format_library_datetime(value: datetime | None) -> str:
    if value is None:
        return "never"
    return value.strftime("%Y-%m-%d %H:%M:%S")


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


def _artifact_selector_label(path: Path) -> str:
    return f"{_artifact_format_label(path)} | {path.name}"


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


def _view_tab_key_for_artifact(path: Path) -> str:
    return f"artifact:{str(path).lower()}"


def _view_tab_title_for_artifact(path: Path) -> str:
    return f"{_artifact_format_label(path)} - {path.name}"


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
