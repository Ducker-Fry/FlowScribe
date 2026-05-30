"""GUI utility functions package.

This package provides stateless pure functions for the GUI layer, organized into
focused modules:

- formatting: Display formatting and rendering functions
- state: State and preferences payload functions
- library: Library-related operations
- artifacts: Artifact-related operations

All functions are re-exported from this package for backward compatibility.
"""

from __future__ import annotations

# Re-export all functions from submodules for backward compatibility
from flowscribe.gui.utils.artifacts import (
    VIEW_ARTIFACT_SUFFIXES,
    _discover_transcript_output_paths,
    _is_viewable_artifact_path,
    _normalize_viewable_artifact_paths,
    _read_viewable_artifact_text,
    _sort_workspace_artifact_paths,
    _transcript_output_records_from_paths,
)
from flowscribe.gui.utils.formatting import (
    _artifact_compare_group,
    _artifact_format_label,
    _artifact_selector_label,
    _artifact_summary,
    _compact_duration_label,
    _format_elapsed_time,
    _format_library_datetime,
    _model_access_guidance_text,
    _normalize_subtitle_artifact_text,
    _onboarding_summary_text,
    _progress_event_status_line,
    _render_json_artifact_html,
    _render_progress_segment_line,
    _render_viewable_artifact_text,
    _subtitle_cue_count,
    _url_media_status_suffix,
    _user_facing_doctor_message,
    _user_facing_folder_label,
    _user_facing_state_file_label,
    _view_tab_key_for_artifact,
    _view_tab_title_for_artifact,
)
from flowscribe.gui.utils.library import (
    LIBRARY_OUTPUT_SUFFIXES,
    _build_library_entry,
    _infer_library_source_kind_from_result,
    _infer_library_source_media_path_from_result,
    _library_entry_list_label,
    _library_entry_missing_summary,
    _library_results_summary,
    _merge_library_output_records,
    _recent_transcript_list_label,
    _resolve_library_source_media_path,
    _sort_library_entries,
)
from flowscribe.gui.utils.state import (
    DEFAULT_GUI_PREFERENCES,
    DEFAULT_ONBOARDING_STATE,
    DEFAULT_VIEW_PREFERENCES,
    GUI_LANGUAGE_OPTIONS,
    GUI_MODEL_OPTIONS,
    GUI_NETWORK_OPTIONS,
    GUI_PRESET_OPTIONS,
    GUI_PROVIDER_LABELS,
    GUI_PROVIDER_OPTIONS,
    MAX_RECENT_JOBS,
    MAX_RECENT_MEDIA_BINDINGS,
    MAX_RECENT_OUTPUT_DIRS,
    MAX_RECENT_TRANSCRIPTS,
    _default_recent_work,
    _gui_preferences_payload,
    _gui_state_payload,
    _local_source_state_payload,
    _normalize_gui_preferences_payload,
    _normalize_gui_state_payload,
    _normalize_local_source_state_payload,
    _normalize_recent_job_entries,
    _normalize_recent_media_bindings,
    _normalize_recent_work_entry_paths,
    _onboarding_state_payload,
    _recent_work_payload,
    _view_preferences_payload,
)

__all__ = [
    # Constants from state
    "GUI_MODEL_OPTIONS",
    "GUI_LANGUAGE_OPTIONS",
    "GUI_PRESET_OPTIONS",
    "GUI_NETWORK_OPTIONS",
    "GUI_PROVIDER_OPTIONS",
    "GUI_PROVIDER_LABELS",
    "DEFAULT_GUI_PREFERENCES",
    "DEFAULT_VIEW_PREFERENCES",
    "DEFAULT_ONBOARDING_STATE",
    "MAX_RECENT_TRANSCRIPTS",
    "MAX_RECENT_OUTPUT_DIRS",
    "MAX_RECENT_JOBS",
    "MAX_RECENT_MEDIA_BINDINGS",
    # Constants from library
    "LIBRARY_OUTPUT_SUFFIXES",
    # Constants from artifacts
    "VIEW_ARTIFACT_SUFFIXES",
    # State functions
    "_default_recent_work",
    "_gui_preferences_payload",
    "_normalize_gui_preferences_payload",
    "_gui_state_payload",
    "_view_preferences_payload",
    "_onboarding_state_payload",
    "_local_source_state_payload",
    "_normalize_local_source_state_payload",
    "_recent_work_payload",
    "_normalize_recent_work_entry_paths",
    "_normalize_recent_job_entries",
    "_normalize_recent_media_bindings",
    "_normalize_gui_state_payload",
    # Formatting functions
    "_format_elapsed_time",
    "_compact_duration_label",
    "_format_library_datetime",
    "_render_progress_segment_line",
    "_progress_event_status_line",
    "_render_json_artifact_html",
    "_render_viewable_artifact_text",
    "_normalize_subtitle_artifact_text",
    "_subtitle_cue_count",
    "_artifact_summary",
    "_artifact_format_label",
    "_artifact_selector_label",
    "_artifact_compare_group",
    "_view_tab_key_for_artifact",
    "_view_tab_title_for_artifact",
    "_url_media_status_suffix",
    "_user_facing_folder_label",
    "_user_facing_state_file_label",
    "_user_facing_doctor_message",
    "_model_access_guidance_text",
    "_onboarding_summary_text",
    # Library functions
    "_resolve_library_source_media_path",
    "_infer_library_source_kind_from_result",
    "_infer_library_source_media_path_from_result",
    "_merge_library_output_records",
    "_build_library_entry",
    "_library_entry_missing_summary",
    "_sort_library_entries",
    "_library_results_summary",
    "_library_entry_list_label",
    "_recent_transcript_list_label",
    # Artifact functions
    "_transcript_output_records_from_paths",
    "_discover_transcript_output_paths",
    "_is_viewable_artifact_path",
    "_normalize_viewable_artifact_paths",
    "_sort_workspace_artifact_paths",
    "_read_viewable_artifact_text",
]
