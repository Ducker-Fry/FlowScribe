"""State and preferences payload functions for the GUI layer.

All functions here are stateless pure functions that handle state serialization
and normalization.
"""

from __future__ import annotations

from pathlib import Path

from flowscribe.gui.export_profiles import (
    ExportProfile,
    export_profiles_payload,
    normalize_export_profiles_payload,
)
from flowscribe.gui.state import SUPPORTED_GUI_FORMATS, is_acceptable_local_source

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


def _default_recent_work() -> dict[str, list[dict[str, object]] | list[str]]:
    return {
        "recent_transcripts": [],
        "recent_output_dirs": [],
        "recent_jobs": [],
        "recent_media_bindings": [],
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


def _local_source_state_payload(paths: list[Path], checked_paths: list[Path]) -> dict:
    return {
        "local_paths": [str(item) for item in paths],
        "checked_paths": [str(item) for item in checked_paths],
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
