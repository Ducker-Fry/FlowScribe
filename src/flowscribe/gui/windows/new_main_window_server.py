from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QFileSystemWatcher

from flowscribe.gui.services.runtime_service import start_bookmarklet_server_runtime


class NewMainWindowServerMixin:
    """Bookmarklet server and queue watcher helpers for the stacked main window."""

    def _on_server_start(self, port: int) -> None:
        if self._server_thread is not None:
            self.statusBar().showMessage("Server is already running")
            return

        self._server_thread, self._server_worker = start_bookmarklet_server_runtime(
            self,
            queue_store_path=self._queue_store._path,
            port=port,
            default_output_dir=Path(self._settings["output_dir"]),
            default_output_formats=self._settings["output_formats"],
            default_model_name=self._settings["model_name"],
            default_language=self._settings["language"],
            started=self._on_server_started,
            stopped=self._on_server_stopped,
            error=self._on_server_error,
        )
        self._server_port = port
        self.statusBar().showMessage(f"Starting server on port {port}...")

    def _on_server_started(self, port: int) -> None:
        self._queue_view.set_server_status(True, port)
        self.statusBar().showMessage(f"Server started on port {port}")

    def _on_server_stopped(self) -> None:
        self._server_thread = None
        self._server_worker = None
        self._server_port = None
        self._queue_view.set_server_status(False)
        self.statusBar().showMessage("Server stopped")

    def _on_server_error(self, error: str) -> None:
        self._queue_view.set_server_status(False)
        self.statusBar().showMessage(f"Server error: {error}")

    def _on_server_stop(self) -> None:
        if self._server_worker:
            self._server_worker.stop()
        self.statusBar().showMessage("Stopping server...")

    def _setup_queue_file_watcher(self) -> None:
        queue_file = self._queue_store._path
        queue_file.parent.mkdir(parents=True, exist_ok=True)
        self._queue_file_watcher = QFileSystemWatcher(self)
        if queue_file.exists():
            self._queue_file_watcher.addPath(str(queue_file))
        self._queue_file_watcher.addPath(str(queue_file.parent))
        self._queue_file_watcher.fileChanged.connect(self._on_queue_file_changed)
        self._queue_file_watcher.directoryChanged.connect(self._on_queue_directory_changed)

    def _watch_queue_file_if_available(self) -> None:
        if self._queue_file_watcher is None:
            return
        queue_file = self._queue_store._path
        if queue_file.exists():
            watched_files = set(self._queue_file_watcher.files())
            if str(queue_file) not in watched_files:
                self._queue_file_watcher.addPath(str(queue_file))

    def _on_queue_file_changed(self, path: str) -> None:
        self._watch_queue_file_if_available()
        self._refresh_queue_view()

    def _on_queue_directory_changed(self, path: str) -> None:
        self._watch_queue_file_if_available()
        self._refresh_queue_view()
