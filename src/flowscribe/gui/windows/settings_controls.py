"""Settings and preferences control mixin for MainWindow."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from PySide6.QtCore import QSignalBlocker, Qt

from flowscribe.gui.export_profiles import (
    ExportProfile,
    apply_export_profile,
    create_export_profile,
    export_profiles_payload,
    profile_list_label,
    remove_export_profile,
    upsert_export_profile,
)
from flowscribe.gui.state_manager import load_gui_state, save_gui_state
from flowscribe.gui.utils import (
    _gui_preferences_payload,
    _recent_work_payload,
)

if TYPE_CHECKING:
    from flowscribe.gui.main_window import MainWindow


class SettingsControlsMixin:
    """Mixin providing settings and preferences management for MainWindow."""

    def _current_gui_preferences(self: MainWindow) -> dict[str, object]:
        return {
            "output_dir": self.output_dir_input.text().strip() or "outputs",
            "output_name_base": self.output_name_input.text(),
            "provider_name": (
                self.provider_combo.currentData()
                if hasattr(self, "provider_combo")
                else "local-whisper"
            ) or "local-whisper",
            "model_name": self.model_combo.currentText(),
            "language": self.language_combo.currentText(),
            "preset": self.preset_combo.currentText(),
            "output_formats": [
                output_format
                for output_format, checkbox in self.format_checks.items()
                if checkbox.isChecked()
            ],
            "timestamps": self.timestamps_check.isChecked(),
            "word_timestamps": self.word_timestamps_check.isChecked(),
            "overwrite": self.overwrite_check.isChecked(),
            "keep_media": self._current_url_media_kind() != "none",
            "url_media_kind": (
                "audio"
                if self._current_url_media_kind() == "none"
                else self._current_url_media_kind()
            ),
            "url_media_output_dir": self.url_media_dir_input.text().strip(),
            "url_auto_bind_media": self.url_auto_bind_check.isChecked(),
            "network_family": self.network_combo.currentText(),
            "proxy": self.proxy_input.text(),
            "native_threads": (
                self.native_threads_spin.value()
                if hasattr(self, "native_threads_spin")
                and self.native_threads_spin.value() > 0
                else None
            ),
        }

    def _current_export_preferences(self: MainWindow) -> dict[str, object]:
        preferences = self._current_gui_preferences()
        return {
            "output_formats": preferences["output_formats"],
            "timestamps": preferences["timestamps"],
            "word_timestamps": preferences["word_timestamps"],
        }

    def _apply_export_preferences(self: MainWindow, preferences: dict[str, object]) -> None:
        enabled_formats = {str(value) for value in preferences["output_formats"]}
        for output_format, checkbox in self.format_checks.items():
            checkbox.setChecked(output_format in enabled_formats)
        self.timestamps_check.setChecked(bool(preferences["timestamps"]))
        self.word_timestamps_check.setChecked(bool(preferences["word_timestamps"]))

    def _apply_gui_preferences(self: MainWindow, preferences: dict[str, object]) -> None:
        self.output_dir_input.setText(str(preferences["output_dir"]))
        self.output_name_input.setText(str(preferences["output_name_base"]))
        if hasattr(self, "provider_combo"):
            index = self.provider_combo.findData(preferences.get("provider_name", "local-whisper"))
            if index >= 0:
                self.provider_combo.setCurrentIndex(index)
        self.model_combo.setCurrentText(str(preferences["model_name"]))
        self.language_combo.setCurrentText(str(preferences["language"]))
        self.preset_combo.setCurrentText(str(preferences["preset"]))
        target_url_media_kind = (
            str(preferences["url_media_kind"])
            if preferences.get("keep_media", False)
            else "none"
        )
        index = self.url_media_mode_combo.findData(target_url_media_kind)
        if index >= 0:
            self.url_media_mode_combo.setCurrentIndex(index)
        self.url_media_dir_input.setText(str(preferences.get("url_media_output_dir", "")))
        self.url_auto_bind_check.setChecked(bool(preferences.get("url_auto_bind_media", True)))
        self.network_combo.setCurrentText(str(preferences["network_family"]))
        self.proxy_input.setText(str(preferences["proxy"]))
        if hasattr(self, "native_threads_spin"):
            self.native_threads_spin.setValue(int(preferences.get("native_threads") or 0))
        self._apply_export_preferences(preferences)
        self.overwrite_check.setChecked(bool(preferences["overwrite"]))
        self._sync_url_media_controls()
        self._refresh_diagnostics_summary()

    def _save_settings(self: MainWindow) -> None:
        self._saved_preferences = _gui_preferences_payload(self._current_gui_preferences())
        self._persist_gui_state()
        self._refresh_diagnostics_summary()
        self.status_label.setText("GUI settings saved. Output, model, and export defaults are ready for the next run.")

    def _show_saved_settings(self: MainWindow) -> None:
        from PySide6.QtWidgets import QDialog, QHBoxLayout, QPlainTextEdit, QPushButton, QVBoxLayout

        current_preferences = _gui_preferences_payload(self._current_gui_preferences())
        payload = {
            "saved_preferences": self._saved_preferences,
            "current_preferences": current_preferences,
            "export_profiles": export_profiles_payload(self._export_profiles),
        }
        self.status_label.setText("Showing GUI preferences.")
        if self._settings_dialog is None:
            dialog = QDialog(self)
            dialog.setWindowTitle("GUI Preferences")
            dialog.resize(720, 560)

            layout = QVBoxLayout(dialog)
            viewer = QPlainTextEdit(dialog)
            viewer.setReadOnly(True)
            layout.addWidget(viewer)

            close_button = QPushButton("Close", dialog)
            close_button.clicked.connect(dialog.accept)

            button_row = QHBoxLayout()
            button_row.addStretch(1)
            button_row.addWidget(close_button)
            layout.addLayout(button_row)

            self._settings_dialog = dialog
            self._settings_viewer = viewer

        if self._settings_viewer is not None:
            self._settings_viewer.setPlainText(json.dumps(payload, ensure_ascii=False, indent=2))

        self._settings_dialog.show()
        self._settings_dialog.raise_()
        self._settings_dialog.activateWindow()

    def _show_export_profiles(self: MainWindow) -> None:
        from PySide6.QtWidgets import QDialog, QHBoxLayout, QListWidget, QPushButton, QVBoxLayout

        self.status_label.setText("Showing export profiles.")
        if self._export_profiles_dialog is None:
            dialog = QDialog(self)
            dialog.setWindowTitle("Export Profiles")
            dialog.resize(760, 560)

            layout = QVBoxLayout(dialog)
            export_profiles_list = QListWidget(dialog)
            layout.addWidget(export_profiles_list)

            action_row = QHBoxLayout()
            save_current_button = QPushButton("Save Current As New", dialog)
            save_current_button.clicked.connect(self._save_current_export_profile_as_new)
            update_selected_button = QPushButton("Update Selected", dialog)
            update_selected_button.clicked.connect(self._update_selected_export_profile)
            apply_selected_button = QPushButton("Apply Selected", dialog)
            apply_selected_button.clicked.connect(self._apply_selected_export_profile)
            delete_selected_button = QPushButton("Delete Selected", dialog)
            delete_selected_button.clicked.connect(self._delete_selected_export_profile)
            action_row.addWidget(save_current_button)
            action_row.addWidget(update_selected_button)
            action_row.addWidget(apply_selected_button)
            action_row.addWidget(delete_selected_button)
            layout.addLayout(action_row)

            close_button = QPushButton("Close", dialog)
            close_button.clicked.connect(dialog.accept)
            close_row = QHBoxLayout()
            close_row.addStretch(1)
            close_row.addWidget(close_button)
            layout.addLayout(close_row)

            self._export_profiles_dialog = dialog
            self._export_profiles_list = export_profiles_list

        self._refresh_export_profiles_list()
        self._export_profiles_dialog.show()
        self._export_profiles_dialog.raise_()
        self._export_profiles_dialog.activateWindow()

    def _refresh_export_profiles_list(self: MainWindow) -> None:
        if self._export_profiles_list is None:
            return
        self._export_profiles_list.clear()
        for profile in self._export_profiles:
            self._export_profiles_list.addItem(profile_list_label(profile))

    def _selected_export_profile(self: MainWindow) -> ExportProfile | None:
        if self._export_profiles_list is None:
            return None
        row = self._export_profiles_list.currentRow()
        if row < 0 or row >= len(self._export_profiles):
            return None
        return self._export_profiles[row]

    def _prompt_export_profile_name(self: MainWindow, *, title: str, text: str, value: str = "") -> str | None:
        from PySide6.QtWidgets import QInputDialog

        name, ok = QInputDialog.getText(self, title, text, text=value)
        if not ok:
            return None
        normalized = str(name).strip()
        return normalized or None

    def _save_current_export_profile_as_new(self: MainWindow) -> None:
        name = self._prompt_export_profile_name(
            title="Save export profile",
            text="Profile name:",
        )
        if not name:
            self.status_label.setText("Export profile save canceled.")
            return
        try:
            profile = create_export_profile(name, self._current_export_preferences())
        except ValueError as exc:
            self.status_label.setText(str(exc))
            return
        self._export_profiles = upsert_export_profile(self._export_profiles, profile)
        self._persist_gui_state()
        self._refresh_export_profiles_list()
        self.status_label.setText(f"Saved export profile: {profile.name}")

    def _update_selected_export_profile(self: MainWindow) -> None:
        profile = self._selected_export_profile()
        if profile is None:
            self.status_label.setText("Select an export profile first.")
            return
        updated = create_export_profile(profile.name, self._current_export_preferences())
        self._export_profiles = upsert_export_profile(self._export_profiles, updated)
        self._persist_gui_state()
        self._refresh_export_profiles_list()
        self.status_label.setText(f"Updated export profile: {updated.name}")

    def _apply_selected_export_profile(self: MainWindow) -> None:
        profile = self._selected_export_profile()
        if profile is None:
            self.status_label.setText("Select an export profile first.")
            return
        updated_preferences = apply_export_profile(profile, self._current_gui_preferences())
        self._apply_export_preferences(updated_preferences)
        self.status_label.setText(f"Applied export profile: {profile.name}")

    def _delete_selected_export_profile(self: MainWindow) -> None:
        profile = self._selected_export_profile()
        if profile is None:
            self.status_label.setText("Select an export profile first.")
            return
        self._export_profiles = remove_export_profile(self._export_profiles, profile.name)
        self._persist_gui_state()
        self._refresh_export_profiles_list()
        self.status_label.setText(f"Deleted export profile: {profile.name}")

    def _restore_gui_state(self: MainWindow) -> None:
        (
            local_paths,
            checked,
            preferences,
            recent_work,
            export_profiles,
            view_preferences,
            onboarding_state,
            state_load_warning,
        ) = load_gui_state()
        self._saved_checked_local_paths = checked
        self._saved_preferences = preferences
        self._recent_work = _recent_work_payload(recent_work)
        self._export_profiles = export_profiles
        self._view_preferences = view_preferences
        self._onboarding_state = onboarding_state
        self._state_load_warning = state_load_warning
        blocker = QSignalBlocker(self.file_list)
        try:
            self._apply_gui_preferences(preferences)
            for path in local_paths:
                self._add_local_file(path)
            for index in range(self.file_list.count()):
                item = self.file_list.item(index)
                if item is not None and item.text() in self._saved_checked_local_paths:
                    item.setCheckState(Qt.CheckState.Checked)
        finally:
            del blocker
        self._view_tab_visibility.update(
            self._view_preferences.get("visible_tabs", {})
        )
        for key, visible in self._view_preferences.get("visible_tabs", {}).items():
            self._set_view_tab_visible(key, visible)
        self._set_current_view_tab(self._view_preferences.get("current_tab", "transcript"))
        self._refresh_diagnostics_summary()
        self._persist_gui_state()
        if not self._onboarding_state.get("help_seen", False):
            self._show_help()
        self._refresh_queue_tab()

    def _persist_gui_state(self: MainWindow) -> None:
        self._view_preferences = self._capture_view_preferences()
        save_gui_state(
            self._local_paths,
            self._checked_local_paths(),
            self._saved_preferences,
            self._recent_work,
            self._export_profiles,
            self._view_preferences,
            self._onboarding_state,
        )

    def _persist_local_source_state(self: MainWindow) -> None:
        self._persist_gui_state()
