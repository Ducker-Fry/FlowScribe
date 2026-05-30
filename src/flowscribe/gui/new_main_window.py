"""New simplified main window with QStackedWidget architecture."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QFileSystemWatcher, QThread, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QApplication, QMainWindow, QStackedWidget, QToolBar

from flowscribe.app.models import SourceSpec
from flowscribe.gui.dialogs.queue_item_settings_dialog import QueueItemSettingsDialog
from flowscribe.gui.dialogs.settings_dialog import SettingsDialog
from flowscribe.gui.icons import (
    get_app_icon,
    get_application_icon,
    get_library_icon,
    get_queue_icon,
    get_settings_icon,
)
from flowscribe.gui.state_manager import batch_queue_store, transcript_library_store
from flowscribe.gui.theme_manager import get_current_theme
from flowscribe.gui.views.library_view import LibraryView
from flowscribe.gui.views.queue_view import QueueView
from flowscribe.gui.views.single_task_view import SingleTaskView
from flowscribe.gui.workers.bookmarklet_server_worker import BookmarkletServerWorker
from flowscribe.gui.workers.queue_runner import QueueRunner
from flowscribe.queue.importers import import_urls_from_file, parse_urls_from_text
from flowscribe.queue.models import (
    QueueItem,
    QueueItemSettings,
    generate_queue_item_id,
)


def _default_settings() -> dict:
    """Return default application settings."""
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
        "progressive_enabled": True,
        "progressive_resume": True,
        "progressive_chunk_seconds": 30.0,
        "progressive_max_workers": 1,
        "native_threads": None,
    }


class NewMainWindow(QMainWindow):
    """Simplified main window with QStackedWidget architecture."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("FlowScribe")
        self.resize(1200, 820)

        # State
        self._settings = _default_settings()
        self._library_store = transcript_library_store()
        self._queue_store = batch_queue_store()
        self._queue_thread: QThread | None = None
        self._queue_runner: QueueRunner | None = None
        self._queue_file_watcher: QFileSystemWatcher | None = None
        self._server_thread: QThread | None = None
        self._server_worker = None
        self._server_port: int | None = None

        self._setup_ui()
        self._connect_signals()
        self._setup_queue_file_watcher()

    def _setup_ui(self) -> None:
        """Initialize UI components."""
        # Get current theme for icons
        app = QApplication.instance()
        theme = get_current_theme(app) if app else "light"

        # Set application icon
        app_icon = get_app_icon()
        if app:
            app.setWindowIcon(app_icon)
        self.setWindowIcon(app_icon)

        # Toolbar
        toolbar = QToolBar("Main")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        settings_action = toolbar.addAction(get_settings_icon(theme), "Settings")
        settings_action.triggered.connect(self._show_settings_dialog)

        toolbar.addSeparator()

        single_task_action = toolbar.addAction(get_application_icon(theme), "Single Task")
        single_task_action.triggered.connect(lambda: self._view_stack.setCurrentIndex(0))

        library_action = toolbar.addAction(get_library_icon(theme), "Library")
        library_action.triggered.connect(lambda: self._view_stack.setCurrentIndex(1))

        queue_action = toolbar.addAction(get_queue_icon(theme), "Queue")
        queue_action.triggered.connect(lambda: self._view_stack.setCurrentIndex(2))

        # Views
        self._view_stack = QStackedWidget()

        self._single_task_view = SingleTaskView(self._settings)
        self._library_view = LibraryView()
        self._queue_view = QueueView(self._settings)

        self._view_stack.addWidget(self._single_task_view)
        self._view_stack.addWidget(self._library_view)
        self._view_stack.addWidget(self._queue_view)

        self.setCentralWidget(self._view_stack)

        # Status bar
        self.statusBar().showMessage("Ready")

    def _connect_signals(self) -> None:
        """Connect signals between views and main window."""
        # SingleTaskView signals
        self._single_task_view.settings_requested.connect(self._show_settings_dialog)
        self._single_task_view.transcription_started.connect(self._on_transcription_started)
        self._single_task_view.transcription_finished.connect(self._on_transcription_finished)
        self._single_task_view.transcription_error.connect(self._on_transcription_error)

        # LibraryView signals
        self._library_view.transcript_open_requested.connect(self._on_library_open_transcript)
        self._library_view.output_dir_open_requested.connect(self._on_library_open_output_dir)
        self._library_view.media_rebind_requested.connect(self._on_library_rebind_media)
        self._library_view.entry_remove_requested.connect(self._on_library_remove_entry)
        self._library_view.missing_cleanup_requested.connect(self._on_library_cleanup_missing)

        # QueueView signals
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
        self._queue_view.server_start_requested.connect(self._on_server_start)
        self._queue_view.server_stop_requested.connect(self._on_server_stop)

    def _show_settings_dialog(self) -> None:
        """Show settings dialog."""
        dialog = SettingsDialog(self, self._settings)
        dialog.settings_changed.connect(self._on_settings_changed)
        if dialog.exec():
            self._settings = dialog.get_settings()
            self._single_task_view.update_settings(self._settings)
            self._queue_view.update_settings(self._settings)
            self._refresh_icons()
            self.statusBar().showMessage("Settings updated")

    def _on_settings_changed(self, settings: dict) -> None:
        """Handle settings changes from Apply button."""
        self._settings = settings
        self._single_task_view.update_settings(settings)
        self._queue_view.update_settings(settings)
        self._refresh_icons()
        self.statusBar().showMessage("Settings applied")

    def _refresh_icons(self) -> None:
        """Refresh all icons after theme change."""
        app = QApplication.instance()
        theme = get_current_theme(app) if app else "light"

        # Update window icon (app icon doesn't change with theme)
        app_icon = get_app_icon()
        if app:
            app.setWindowIcon(app_icon)
        self.setWindowIcon(app_icon)

        # Update toolbar icons
        toolbar = self.findChild(QToolBar, "Main")
        if toolbar:
            actions = toolbar.actions()
            if len(actions) >= 4:
                actions[0].setIcon(get_settings_icon(theme))  # Settings
                # Skip separator at index 1
                actions[2].setIcon(get_application_icon(theme))  # Single Task
                actions[3].setIcon(get_library_icon(theme))  # Library
                actions[4].setIcon(get_queue_icon(theme))  # Queue

    # SingleTaskView handlers
    def _on_transcription_started(self) -> None:
        """Handle transcription start."""
        self.statusBar().showMessage("Transcription started")

    def _on_transcription_finished(self, result) -> None:
        """Handle transcription completion."""
        self.statusBar().showMessage("Transcription finished")
        # Index in library
        if result.outputs:
            for artifacts in result.outputs:
                for path in artifacts.paths:
                    if path.suffix.lower() == ".json":
                        self._add_transcript_to_library(path, artifacts)
            self._library_view.refresh_library()

    def _add_transcript_to_library(self, transcript_path: Path, artifacts=None) -> None:
        """Add transcript to library."""
        from flowscribe.library import TranscriptLibraryEntry, LibraryOutputRecord
        from flowscribe.gui.utils.library import _discover_transcript_output_paths

        try:
            # Discover output files
            output_paths = _discover_transcript_output_paths(transcript_path)
            outputs = tuple(LibraryOutputRecord.from_path(p) for p in output_paths)

            # Extract media path from artifacts if available
            media_path = None
            source_media_path = None
            media_binding = None
            if artifacts is not None:
                if artifacts.media_path is not None:
                    media_path = Path(artifacts.media_path) if isinstance(artifacts.media_path, str) else artifacts.media_path
                    source_media_path = media_path
                    # Create media binding if auto-bind is enabled
                    if artifacts.auto_bind_media:
                        from flowscribe.library.models import LibraryMediaBinding
                        media_binding = LibraryMediaBinding.create(
                            transcript_path=transcript_path,
                            media_path=media_path,
                            binding_type="auto",
                        )
                # Determine source kind from artifacts
                source_kind = artifacts.source_kind or "local"
            else:
                source_kind = "local"

            # Create entry
            entry = TranscriptLibraryEntry.create(
                transcript_path=transcript_path,
                output_dir=transcript_path.parent,
                display_label=transcript_path.stem,
                source_kind=source_kind,
                outputs=outputs,
                source_media_path=source_media_path,
                media_binding=media_binding,
            )

            # Upsert to store
            self._library_store.upsert_entry(entry)
        except Exception as e:
            self.statusBar().showMessage(f"Failed to add to library: {e}")

    def _on_transcription_error(self, error: str) -> None:
        """Handle transcription error."""
        self.statusBar().showMessage(f"Transcription error: {error}")

    # LibraryView handlers
    def _on_library_open_transcript(self, entry) -> None:
        """Open transcript from library."""
        # TODO: Load transcript in workspace
        self.statusBar().showMessage(f"Opening transcript: {entry.transcript_path}")

    def _on_library_open_output_dir(self, entry) -> None:
        """Open output directory."""
        if entry.output_dir and entry.output_dir.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(entry.output_dir)))
            self.statusBar().showMessage(f"Opened: {entry.output_dir}")
        else:
            self.statusBar().showMessage("Output directory not found")

    def _on_library_rebind_media(self, entry) -> None:
        """Rebind media for transcript."""
        # TODO: Implement media rebinding
        self.statusBar().showMessage(f"Rebind media: {entry.transcript_path}")

    def _on_library_remove_entry(self, entry) -> None:
        """Remove entry from library."""
        self._library_store.remove_entry_by_transcript_path(entry.transcript_path)
        self._library_view.refresh_library()
        self.statusBar().showMessage("Entry removed from library")

    def _on_library_cleanup_missing(self) -> None:
        """Clean up missing library entries."""
        # First refresh to detect missing entries
        self._library_store.refresh_missing_statuses()
        # Then remove them
        removed = self._library_store.remove_missing_entries()
        self._library_view.refresh_library()
        self.statusBar().showMessage(f"Removed {len(removed)} missing entries")

    # QueueView handlers
    def _on_enqueue_urls(self, text: str) -> None:
        """Enqueue URLs from text."""
        try:
            from flowscribe.app.models import DownloadOptions

            urls = parse_urls_from_text(text)
            if not urls:
                self.statusBar().showMessage("No valid URLs found in input")
                return

            settings = self._settings_to_queue_settings()
            download_opts_dict = self._queue_view.get_download_options()
            download_opts = DownloadOptions(
                quality=download_opts_dict["quality"],
                prefer_format=download_opts_dict["prefer_format"],
            )
            items = []
            for url in urls:
                source = SourceSpec(
                    kind="url",
                    value=url,
                    keep_media=download_opts_dict["preserve_media"],
                    url_media_kind=download_opts_dict["media_kind"],
                    download_options=download_opts,
                    auto_bind_media=True,
                )
                item = QueueItem(
                    item_id=generate_queue_item_id(source),
                    source=source,
                    settings=settings,
                )
                items.append(item)
                self._queue_store.enqueue(item)
            self._refresh_queue_view()
            self.statusBar().showMessage(f"Added {len(items)} URL(s) to queue")
        except Exception as e:
            self.statusBar().showMessage(f"Error adding URLs: {e}")

    def _on_enqueue_files(self, paths: list[Path]) -> None:
        """Enqueue local files."""
        settings = self._settings_to_queue_settings()
        items = []
        for path in paths:
            source = SourceSpec(kind="local", value=str(path))
            item = QueueItem(
                item_id=generate_queue_item_id(source),
                source=source,
                settings=settings,
            )
            items.append(item)
            self._queue_store.enqueue(item)
        self._refresh_queue_view()
        self.statusBar().showMessage(f"Added {len(items)} file(s) to queue")

    def _on_import_file(self, file_path: str) -> None:
        """Import URLs from file."""
        from flowscribe.app.models import DownloadOptions

        urls = import_urls_from_file(Path(file_path))
        settings = self._settings_to_queue_settings()
        download_opts_dict = self._queue_view.get_download_options()
        download_opts = DownloadOptions(
            quality=download_opts_dict["quality"],
            prefer_format=download_opts_dict["prefer_format"],
        )
        items = []
        for url in urls:
            source = SourceSpec(
                kind="url",
                value=url,
                keep_media=download_opts_dict["preserve_media"],
                url_media_kind=download_opts_dict["media_kind"],
                download_options=download_opts,
                auto_bind_media=True,
            )
            item = QueueItem(
                item_id=generate_queue_item_id(source),
                source=source,
                settings=settings,
            )
            items.append(item)
            self._queue_store.enqueue(item)
        self._refresh_queue_view()
        self.statusBar().showMessage(f"Imported {len(items)} URL(s) from file")

    def _on_start_queue(self) -> None:
        """Start queue processing."""
        if self._queue_thread is not None:
            self.statusBar().showMessage("Queue is already running")
            return

        self._queue_thread = QThread(self)
        self._queue_runner = QueueRunner(self._queue_store)
        self._queue_runner.moveToThread(self._queue_thread)
        self._queue_thread.started.connect(self._queue_runner.run)
        self._queue_runner.item_started.connect(self._on_queue_item_started)
        self._queue_runner.item_progress.connect(self._on_queue_item_progress)
        self._queue_runner.item_completed.connect(self._on_queue_item_completed)
        self._queue_runner.item_failed.connect(self._on_queue_item_failed)
        self._queue_runner.item_canceled.connect(self._on_queue_item_canceled)
        self._queue_runner.queue_finished.connect(self._on_queue_finished)
        self._queue_runner.queue_finished.connect(self._queue_thread.quit)
        self._queue_thread.finished.connect(self._queue_runner.deleteLater)
        self._queue_thread.finished.connect(self._queue_thread.deleteLater)
        self._queue_thread.start()

        self._queue_view.set_queue_running(True)
        self.statusBar().showMessage("Queue processing started")

    def _on_cancel_queue(self) -> None:
        """Cancel queue processing."""
        if self._queue_runner:
            self._queue_runner.request_cancel_all()
        self.statusBar().showMessage("Queue cancellation requested")

    def _on_skip_current(self) -> None:
        """Skip current queue item."""
        if self._queue_runner:
            self._queue_runner.request_skip_current()
        self.statusBar().showMessage("Skip requested")

    def _on_retry_item(self, item_id: str) -> None:
        """Retry failed item."""
        self._queue_store.update_item(item_id, status="pending", started_at=None, error_message=None)
        self._refresh_queue_view()
        self.statusBar().showMessage("Item marked for retry")

    def _on_remove_items(self, item_ids: list[str]) -> None:
        """Remove items from queue."""
        for item_id in item_ids:
            self._queue_store.remove_item(item_id)
        self._refresh_queue_view()
        self.statusBar().showMessage(f"Removed {len(item_ids)} item(s)")

    def _on_clear_completed(self) -> None:
        """Clear completed items."""
        removed = self._queue_store.remove_completed()
        self._refresh_queue_view()
        self.statusBar().showMessage(f"Cleared {removed} completed item(s)")

    def _on_reorder_queue(self, item_ids: list[str]) -> None:
        """Reorder queue items."""
        self._queue_store.reorder_items(item_ids)
        self._refresh_queue_view()

    def _on_edit_item_settings(self, item_ids: list[str]) -> None:
        """Edit settings for queue items (supports batch editing)."""
        if not item_ids:
            self.statusBar().showMessage("No items selected")
            return

        # Get first item as template
        first_item = self._queue_store.get_item(item_ids[0])
        if first_item is None:
            self.statusBar().showMessage("Item not found")
            return

        # Determine label for dialog
        is_batch = len(item_ids) > 1
        if is_batch:
            item_label = f"{len(item_ids)} items"
        else:
            item_label = first_item.display_label

        # Show dialog with first item's settings as template
        dialog = QueueItemSettingsDialog(
            self, first_item.settings, first_item.source, item_label, is_batch=is_batch
        )
        if dialog.exec():
            result = dialog.get_settings()
            if result is not None:
                updated_settings, updated_source = result
                # Apply to all selected items
                for item_id in item_ids:
                    self._queue_store.update_item(
                        item_id,
                        settings=updated_settings,
                        source=updated_source,
                    )
                self._refresh_queue_view()
                if is_batch:
                    self.statusBar().showMessage(f"Updated settings for {len(item_ids)} items")
                else:
                    self.statusBar().showMessage("Item settings updated")

    def _on_server_start(self, port: int) -> None:
        """Start bookmarklet server."""
        if self._server_thread is not None:
            self.statusBar().showMessage("Server is already running")
            return

        self._server_thread = QThread(self)
        self._server_worker = BookmarkletServerWorker(
            queue_store_path=self._queue_store._path,
            port=port,
            default_output_dir=Path(self._settings["output_dir"]),
            default_output_formats=self._settings["output_formats"],
            default_model_name=self._settings["model_name"],
            default_language=self._settings["language"],
        )
        self._server_worker.moveToThread(self._server_thread)
        self._server_thread.started.connect(self._server_worker.run)
        self._server_worker.started.connect(self._on_server_started)
        self._server_worker.stopped.connect(self._on_server_stopped)
        self._server_worker.error.connect(self._on_server_error)
        self._server_worker.stopped.connect(self._server_thread.quit)
        self._server_thread.finished.connect(self._server_worker.deleteLater)
        self._server_thread.finished.connect(self._server_thread.deleteLater)
        self._server_thread.start()

        self._server_port = port
        self.statusBar().showMessage(f"Starting server on port {port}...")

    def _on_server_started(self, port: int) -> None:
        """Handle server start."""
        self._queue_view.set_server_status(True, port)
        self.statusBar().showMessage(f"Server started on port {port}")

    def _on_server_stopped(self) -> None:
        """Handle server stop."""
        self._server_thread = None
        self._server_worker = None
        self._server_port = None
        self._queue_view.set_server_status(False)
        self.statusBar().showMessage("Server stopped")

    def _on_server_error(self, error: str) -> None:
        """Handle server error."""
        self._queue_view.set_server_status(False)
        self.statusBar().showMessage(f"Server error: {error}")

    def _on_server_stop(self) -> None:
        """Stop bookmarklet server."""
        if self._server_worker:
            self._server_worker.stop()
        self.statusBar().showMessage("Stopping server...")

    def _on_queue_finished(self) -> None:
        """Handle queue processing completion."""
        self._queue_thread = None
        self._queue_runner = None
        self._queue_view.set_queue_running(False)
        self._refresh_queue_view()
        self._library_view.refresh_library()
        self.statusBar().showMessage("Queue processing finished")

    def _on_queue_item_started(self, item) -> None:
        """Handle queue item started."""
        self._queue_view.on_item_started(item)
        self._refresh_queue_view()

    def _on_queue_item_progress(self, event) -> None:
        """Handle queue item progress."""
        self._queue_view.on_item_progress(event)

    def _on_queue_item_completed(self, data: tuple) -> None:
        """Handle queue item completed."""
        self._queue_view.on_item_completed(data)
        self._refresh_queue_view()
        self._library_view.refresh_library()

    def _on_queue_item_failed(self, data: tuple) -> None:
        """Handle queue item failed."""
        self._queue_view.on_item_failed(data)
        self._refresh_queue_view()

    def _on_queue_item_canceled(self, item) -> None:
        """Handle queue item canceled."""
        self._queue_view.on_item_canceled(item)
        self._refresh_queue_view()

    def _refresh_queue_view(self) -> None:
        """Refresh queue view display."""
        items = self._queue_store.load_items()
        self._queue_view.refresh_queue(items)

    def _settings_to_queue_settings(self) -> QueueItemSettings:
        """Convert app settings to queue item settings."""
        return QueueItemSettings(
            output_dir=Path(self._settings["output_dir"]),
            output_name_base=self._settings.get("output_name_base", ""),
            provider_name=self._settings.get("provider_name", "local-whisper"),
            model_name=self._settings["model_name"],
            language=self._settings["language"],
            preset=self._settings["preset"],
            output_formats=self._settings["output_formats"],
            timestamps=self._settings["timestamps"],
            word_timestamps=self._settings["word_timestamps"],
            overwrite=self._settings["overwrite"],
            network_family=self._settings["network_family"],
            proxy=self._settings["proxy"],
            cookies_path=self._settings["cookies_path"],
            progressive_enabled=self._settings["progressive_enabled"],
            progressive_resume=self._settings["progressive_resume"],
            progressive_chunk_seconds=self._settings["progressive_chunk_seconds"],
            progressive_max_workers=self._settings["progressive_max_workers"],
            native_threads=self._settings.get("native_threads"),
        )

    def _setup_queue_file_watcher(self) -> None:
        """Setup file watcher for queue file."""
        queue_file = self._queue_store._path
        if queue_file.exists():
            self._queue_file_watcher = QFileSystemWatcher([str(queue_file)], self)
            self._queue_file_watcher.fileChanged.connect(self._on_queue_file_changed)

    def _on_queue_file_changed(self, path: str) -> None:
        """Handle queue file changes (e.g., from bookmarklet server)."""
        self._refresh_queue_view()
