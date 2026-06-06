"""GUI state persistence — load/save GUI state JSON via PySide6 QStandardPaths."""

from __future__ import annotations

import json
from pathlib import Path

from flowscribe.gui.export_profiles import ExportProfile
from flowscribe.gui.utils import (
    DEFAULT_GUI_PREFERENCES,
    DEFAULT_ONBOARDING_STATE,
    DEFAULT_VIEW_PREFERENCES,
    _default_recent_work,
    _gui_preferences_payload,
    _gui_state_payload,
    _normalize_gui_state_payload,
    _onboarding_state_payload,
    _view_preferences_payload,
)
from flowscribe.library import TranscriptLibraryStore


def gui_state_path() -> Path:
    from PySide6.QtCore import QStandardPaths

    app_data = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
    base_dir = Path(app_data) if app_data else (Path.home() / ".flowscribe")
    return base_dir / "gui-state.json"


def batch_queue_path() -> Path:
    return gui_state_path().parent / "batch-queue.json"


def batch_queue_store():
    from flowscribe.tasks.queue_store import BatchQueueStore

    return BatchQueueStore(batch_queue_path())


def transcript_library_path() -> Path:
    return gui_state_path().parent / "transcript-library.json"


def transcript_library_store() -> TranscriptLibraryStore:
    return TranscriptLibraryStore(transcript_library_path())


def load_gui_state() -> tuple[
    list[Path],
    set[str],
    dict[str, object],
    dict[str, list[dict[str, object]] | list[str]],
    tuple[ExportProfile, ...],
    dict[str, object],
    dict[str, object],
    str | None,
]:
    path = gui_state_path()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        return (
            [],
            set(),
            _gui_preferences_payload(DEFAULT_GUI_PREFERENCES),
            _default_recent_work(),
            (),
            _view_preferences_payload(DEFAULT_VIEW_PREFERENCES),
            _onboarding_state_payload(DEFAULT_ONBOARDING_STATE),
            f"Could not read GUI state file. FlowScribe started with default settings. Details: {exc}",
        )
    except json.JSONDecodeError:
        return (
            [],
            set(),
            _gui_preferences_payload(DEFAULT_GUI_PREFERENCES),
            _default_recent_work(),
            (),
            _view_preferences_payload(DEFAULT_VIEW_PREFERENCES),
            _onboarding_state_payload(DEFAULT_ONBOARDING_STATE),
            "GUI state file was unreadable. FlowScribe started with default settings.",
        )
    local_paths, checked, preferences, recent_work, profiles, view_preferences, onboarding_state = _normalize_gui_state_payload(payload)
    return (
        local_paths,
        checked,
        preferences,
        recent_work,
        profiles,
        view_preferences,
        onboarding_state,
        None,
    )


def save_gui_state(
    paths: list[Path],
    checked_paths: list[Path],
    preferences: dict[str, object],
    recent_work: dict[str, list[dict[str, object]] | list[str]],
    export_profiles: tuple[ExportProfile, ...],
    view_preferences: dict[str, object],
    onboarding_state: dict[str, object],
) -> None:
    path = gui_state_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                _gui_state_payload(
                    paths,
                    checked_paths,
                    preferences,
                    recent_work,
                    export_profiles,
                    view_preferences,
                    onboarding_state,
                ),
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    except OSError:
        return
