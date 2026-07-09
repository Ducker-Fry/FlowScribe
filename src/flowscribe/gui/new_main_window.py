"""New simplified main window with QStackedWidget architecture."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtGui import QDesktopServices
from PySide6.QtCore import QThread, QUrl
from PySide6.QtWidgets import QApplication, QFileDialog, QMainWindow, QMessageBox, QStackedWidget, QToolBar

from flowscribe.config.resources import allow_implicit_model_download
from flowscribe.gui.dialogs.settings_dialog import SettingsDialog
from flowscribe.gui.icons import (
    get_app_icon,
    get_application_icon,
    get_help_icon,
    get_library_icon,
    get_queue_icon,
    get_settings_icon,
)
from flowscribe.gui.services.library_service import (
    ensure_library_entry_outputs,
    remove_library_entry_and_output_dir,
    upsert_library_entry_from_artifacts,
)
from flowscribe.gui.services.window_service import (
    open_multiple_output_directories,
    open_output_directory,
)
from flowscribe.gui.state_manager import batch_queue_store, transcript_library_store
from flowscribe.gui.theme_manager import get_current_theme
from flowscribe.gui.views.library_view import LibraryView
from flowscribe.gui.views.queue_view import QueueView
from flowscribe.gui.views.single_task_view import SingleTaskView
from flowscribe.gui.windows.new_main_window_queue import NewMainWindowQueueMixin
from flowscribe.gui.windows.new_main_window_server import NewMainWindowServerMixin
from flowscribe.model_manager import local_docs_index_path, local_model_guide_path, managed_models_present


def _default_settings() -> dict:
    return {
        "output_dir": "outputs",
        "output_name_base": "",
        "provider_name": "local-whisper",
        "model_name": "small",
        "language": None,
        "preset": None,
        "output_formats": ("txt", "md", "json"),
        "timestamps": True,
        "word_timestamps": False,
        "overwrite": False,
        "network_family": "auto",
        "proxy": None,
        "cookies_path": None,
        "execution_mode": "local",
        "server_target": None,
        "remote_token": None,
        "remote_poll_seconds": 1.0,
        "download_artifacts": True,
        "progressive_enabled": True,
        "progressive_resume": True,
        "progressive_chunk_seconds": 30.0,
        "progressive_max_workers": 1,
        "native_threads": None,
    }


class NewMainWindow(QMainWindow, NewMainWindowQueueMixin, NewMainWindowServerMixin):
    """Simplified main window with QStackedWidget architecture."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("FlowScribe")
        self.resize(1200, 820)

        self._settings = _default_settings()
        self._library_store = transcript_library_store()
        self._queue_store = batch_queue_store()
        self._queue_thread: QThread | None = None
        self._queue_runner = None
        self._queue_file_watcher = None
        self._server_thread: QThread | None = None
        self._server_worker = None
        self._server_port: int | None = None
        self._library_view_dialog = None
        self._missing_models_prompt_shown = False

        self._setup_ui()
        self._connect_signals()
        self._setup_queue_file_watcher()
        self._refresh_queue_view()
        self._maybe_prompt_for_models()

    def _setup_ui(self) -> None:
        app = QApplication.instance()
        theme = get_current_theme(app) if app else "light"

        app_icon = get_app_icon()
        if app:
            app.setWindowIcon(app_icon)
        self.setWindowIcon(app_icon)

        toolbar = QToolBar("Main")
        toolbar.setObjectName("Main")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        toolbar.addAction(get_settings_icon(theme), "Settings").triggered.connect(
            self._show_settings_dialog
        )
        toolbar.addAction(get_help_icon(theme), "Help").triggered.connect(self._show_help)
        toolbar.addSeparator()
        toolbar.addAction(get_application_icon(theme), "Single Task").triggered.connect(
            lambda: self._view_stack.setCurrentIndex(0)
        )
        toolbar.addAction(get_library_icon(theme), "Library").triggered.connect(
            lambda: self._view_stack.setCurrentIndex(1)
        )
        toolbar.addAction(get_queue_icon(theme), "Queue").triggered.connect(
            lambda: self._view_stack.setCurrentIndex(2)
        )

        self._view_stack = QStackedWidget()
        self._single_task_view = SingleTaskView(self._settings)
        self._library_view = LibraryView()
        self._queue_view = QueueView(self._settings)
        self._view_stack.addWidget(self._single_task_view)
        self._view_stack.addWidget(self._library_view)
        self._view_stack.addWidget(self._queue_view)
        self.setCentralWidget(self._view_stack)
        self.statusBar().showMessage("Ready")

    def _connect_signals(self) -> None:
        self._single_task_view.settings_requested.connect(self._show_settings_dialog)
        self._single_task_view.transcription_started.connect(self._on_transcription_started)
        self._single_task_view.transcription_finished.connect(self._on_transcription_finished)
        self._single_task_view.transcription_error.connect(self._on_transcription_error)

        self._library_view.transcript_open_requested.connect(self._on_library_open_transcript)
        self._library_view.output_dir_open_requested.connect(self._on_library_open_output_dir)
        self._library_view.output_dirs_open_requested.connect(self._on_library_open_output_dirs)
        self._library_view.media_rebind_requested.connect(self._on_library_rebind_media)
        self._library_view.entry_remove_requested.connect(self._on_library_remove_entry)
        self._library_view.entries_remove_requested.connect(self._on_library_remove_entries)
        self._library_view.artifact_open_requested.connect(self._on_library_open_artifact)
        self._library_view.missing_cleanup_requested.connect(self._on_library_cleanup_missing)

        self._queue_view.enqueue_urls_requested.connect(self._on_enqueue_urls)
        self._queue_view.enqueue_files_requested.connect(self._on_enqueue_files)
        self._queue_view.import_file_requested.connect(self._on_import_file)
        self._queue_view.start_queue_requested.connect(self._on_start_queue)
        self._queue_view.cancel_queue_requested.connect(self._on_cancel_queue)
        self._queue_view.skip_current_requested.connect(self._on_skip_current)
        self._queue_view.retry_item_requested.connect(self._on_retry_item)
        self._queue_view.remove_items_requested.connect(self._on_remove_items)
        self._queue_view.clear_completed_requested.connect(self._on_clear_completed)
        self._queue_view.reorder_requested.connect(self._on_reorder_queue)
        self._queue_view.edit_item_settings_requested.connect(self._on_edit_item_settings)
        self._queue_view.execution_settings_changed.connect(self._on_queue_execution_settings_changed)
        self._queue_view.server_start_requested.connect(self._on_server_start)
        self._queue_view.server_stop_requested.connect(self._on_server_stop)

    def _show_settings_dialog(self) -> None:
        dialog = SettingsDialog(self, self._settings)
        dialog.settings_changed.connect(self._on_settings_changed)
        dialog.model_manager_requested.connect(self._show_model_manager_dialog)
        if dialog.exec():
            self._settings = dialog.get_settings()
            self._single_task_view.update_settings(self._settings)
            self._queue_view.update_settings(self._settings)
            self._refresh_icons()
            self.statusBar().showMessage("Settings updated")

    def _show_model_manager_dialog(self) -> None:
        from flowscribe.gui.dialogs import ModelManagerDialog

        dialog = ModelManagerDialog(self)
        dialog.exec()
        self.statusBar().showMessage("Model Center closed")

    def _on_settings_changed(self, settings: dict) -> None:
        self._settings = settings
        self._single_task_view.update_settings(settings)
        self._queue_view.update_settings(settings)
        self._refresh_icons()
        self.statusBar().showMessage("Settings applied")

    def _on_queue_execution_settings_changed(self, settings: dict) -> None:
        self._settings.update(settings)

    def _refresh_icons(self) -> None:
        app = QApplication.instance()
        theme = get_current_theme(app) if app else "light"
        app_icon = get_app_icon()
        if app:
            app.setWindowIcon(app_icon)
        self.setWindowIcon(app_icon)

        toolbar = self.findChild(QToolBar, "Main")
        if toolbar:
            actions = toolbar.actions()
            if len(actions) >= 6:
                actions[0].setIcon(get_settings_icon(theme))
                actions[1].setIcon(get_help_icon(theme))
                actions[3].setIcon(get_application_icon(theme))
                actions[4].setIcon(get_library_icon(theme))
                actions[5].setIcon(get_queue_icon(theme))

    def _on_transcription_started(self) -> None:
        self.statusBar().showMessage("Transcription started")

    def _on_transcription_finished(self, result) -> None:
        self.statusBar().showMessage("Transcription finished")
        if result.outputs:
            for artifacts in result.outputs:
                for path in artifacts.paths:
                    if path.suffix.lower() == ".json":
                        self._add_transcript_to_library(path, artifacts)
            self._library_view.refresh_library()

    def _add_transcript_to_library(self, transcript_path: Path, artifacts=None) -> None:
        try:
            upsert_library_entry_from_artifacts(
                self._library_store,
                transcript_path,
                artifacts=artifacts,
                output_dir=transcript_path.parent,
            )
        except Exception as exc:
            self.statusBar().showMessage(f"Failed to add to library: {exc}")

    def _on_transcription_error(self, error: str) -> None:
        self.statusBar().showMessage(f"Transcription error: {error}")
        if "Model Center" in error or "is not installed" in error:
            self._show_model_manager_dialog()

    def _show_help(self) -> None:
        docs_path = local_docs_index_path()
        if docs_path is None:
            self.statusBar().showMessage("Local help is not installed.")
            return
        if QDesktopServices.openUrl(QUrl.fromLocalFile(str(docs_path))):
            self.statusBar().showMessage("Opened local help.")
        else:
            self.statusBar().showMessage(f"Could not open help: {docs_path}")

    def _maybe_prompt_for_models(self) -> None:
        if self._missing_models_prompt_shown or not bool(getattr(sys, "frozen", False)):
            return
        if allow_implicit_model_download() or managed_models_present():
            return

        self._missing_models_prompt_shown = True
        self.statusBar().showMessage(
            "No transcription model is installed yet. Open Model Center to download one."
        )
        message = QMessageBox(self)
        message.setWindowTitle("Download A Model Before First Use")
        message.setText(
            "FlowScribe does not auto-download transcription models on first use in the installed app.\n\n"
            "Download `small` now to avoid a long, silent wait later."
        )
        message.setInformativeText(
            "Choose Model Center to download now, or Help to open the local model guide."
        )
        model_center_button = message.addButton("Open Model Center", QMessageBox.ButtonRole.AcceptRole)
        help_button = message.addButton("Open Model Guide", QMessageBox.ButtonRole.HelpRole)
        message.addButton("Later", QMessageBox.ButtonRole.RejectRole)
        message.exec()
        clicked = message.clickedButton()
        if clicked is model_center_button:
            self._show_model_manager_dialog()
        elif clicked is help_button:
            guide_path = local_model_guide_path()
            if guide_path is not None:
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(guide_path)))

    def _on_library_open_transcript(self, entry) -> None:
        if not entry.transcript_path.is_file():
            self.statusBar().showMessage(f"Transcript not found: {entry.transcript_path}")
            self._library_view.refresh_library()
            return

        entry = self._ensure_library_outputs(entry)
        if self._library_view_dialog is None:
            from flowscribe.gui.dialogs import TranscriptionViewDialog

            self._library_view_dialog = TranscriptionViewDialog(
                self,
                transcript_path=None,
                run_output="",
                result=None,
                output_paths=None,
            )

        self._library_view_dialog.clear_content()
        output_paths = tuple(output.path for output in entry.outputs)
        self._library_view_dialog._load_transcript_with_artifacts(
            entry.transcript_path,
            output_paths,
        )
        if entry.media_binding is not None and entry.media_binding.media_path.is_file():
            self._library_view_dialog._bind_media(entry.media_binding.media_path)

        self._library_store.mark_opened(entry.entry_id)
        self._library_view.refresh_library()
        self._library_view_dialog.show()
        self._library_view_dialog.raise_()
        self._library_view_dialog.activateWindow()
        self.statusBar().showMessage(f"Opened transcript: {entry.display_label}")

    def _on_library_open_output_dir(self, entry) -> None:
        if entry.output_dir and open_output_directory(Path(entry.output_dir)):
            self.statusBar().showMessage(f"Opened: {entry.output_dir}")
        else:
            self.statusBar().showMessage("Output directory not found")

    def _on_library_open_output_dirs(self, entries: list) -> None:
        opened, missing = open_multiple_output_directories(entries)
        self.statusBar().showMessage(f"Opened {opened} output folder(s). Missing: {missing}.")

    def _on_library_rebind_media(self, entry) -> None:
        media_path_text, _ = QFileDialog.getOpenFileName(
            self,
            "Bind media to transcript",
            str(entry.output_dir if entry.output_dir.exists() else Path.home()),
            "Media files (*.mp4 *.mp3 *.wav *.m4a *.mkv *.avi *.flac *.ogg *.webm);;All files (*.*)",
        )
        if not media_path_text:
            return

        from dataclasses import replace
        from flowscribe.library.models import LibraryMediaBinding

        media_path = Path(media_path_text)
        updated = replace(
            entry,
            media_binding=LibraryMediaBinding.create(
                transcript_path=entry.transcript_path,
                media_path=media_path,
                binding_type="manual",
            ),
        ).refresh_missing_status()
        self._library_store.upsert_entry(updated)
        self._library_view.refresh_library()
        self.statusBar().showMessage(f"Bound media: {media_path.name}")

    def _on_library_remove_entry(self, entry) -> None:
        removed, disk_removed = remove_library_entry_and_output_dir(self._library_store, entry)
        if removed and not disk_removed:
            self.statusBar().showMessage(
                f"Removed library entry but could not delete: {entry.output_dir}"
            )
            self._library_view.refresh_library()
            return
        self._library_view.refresh_library()
        self.statusBar().showMessage("Entry removed from library and disk")

    def _on_library_remove_entries(self, entries: list) -> None:
        removed = 0
        for entry in entries:
            removed_entry, disk_removed = remove_library_entry_and_output_dir(self._library_store, entry)
            if removed_entry and disk_removed:
                removed += 1
        self._library_view.refresh_library()
        self.statusBar().showMessage(f"Removed {removed} entries from library and disk")

    def _on_library_open_artifact(self, path: Path) -> None:
        if path.is_file():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
            self.statusBar().showMessage(f"Opened artifact: {path.name}")
        else:
            self.statusBar().showMessage(f"Artifact not found: {path}")

    def _on_library_cleanup_missing(self) -> None:
        self._library_store.refresh_missing_statuses()
        removed = self._library_store.remove_missing_entries()
        self._library_view.refresh_library()
        self.statusBar().showMessage(f"Removed {len(removed)} missing entries")

    def _ensure_library_outputs(self, entry):
        return ensure_library_entry_outputs(self._library_store, entry)

    def _add_transcript_to_library_with_label(
        self,
        transcript_path: Path,
        display_label: str,
        artifacts=None,
        output_dir: Path | None = None,
    ) -> None:
        try:
            upsert_library_entry_from_artifacts(
                self._library_store,
                transcript_path,
                display_label=display_label,
                artifacts=artifacts,
                output_dir=output_dir or transcript_path.parent,
            )
        except Exception as exc:
            self.statusBar().showMessage(f"Failed to add to library: {exc}")
