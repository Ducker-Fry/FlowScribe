"""Worker for running bookmarklet server in QThread."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Signal

from flowscribe.server.bookmarklet_server import BookmarkletServer


class BookmarkletServerWorker(QObject):
    """Worker to run bookmarklet server in background thread."""

    started = Signal(int)  # port
    stopped = Signal()
    error = Signal(str)

    def __init__(
        self,
        queue_store_path: Path,
        port: int = 8765,
        default_output_dir: Path | None = None,
        default_output_formats: tuple[str, ...] = ("json",),
        default_model_name: str = "small",
        default_language: str | None = None,
    ):
        super().__init__()
        self._port = port
        self._server = BookmarkletServer(
            queue_store_path=queue_store_path,
            host="127.0.0.1",
            port=port,
            default_output_dir=default_output_dir,
            default_output_formats=default_output_formats,
            default_model_name=default_model_name,
            default_language=default_language,
        )
        self._running = False

    def run(self) -> None:
        """Start the server."""
        try:
            self._running = True
            self.started.emit(self._port)
            self._server.start()
        except Exception as e:
            self.error.emit(str(e))
        finally:
            self._running = False
            self.stopped.emit()

    def stop(self) -> None:
        """Stop the server."""
        if self._running:
            self._server.stop()
