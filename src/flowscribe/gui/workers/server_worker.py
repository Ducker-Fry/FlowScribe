"""QThread worker for running Bookmarklet server."""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QObject, Signal

logger = logging.getLogger(__name__)


def _is_address_in_use_error(exc: OSError) -> bool:
    if exc.errno in {98, 10048}:
        return True
    if getattr(exc, "winerror", None) == 10048:
        return True
    return "address already in use" in str(exc).lower()


class ServerWorker(QObject):
    """Worker for running Bookmarklet server in background thread."""

    started = Signal(int)  # port
    stopped = Signal()
    error = Signal(str)

    def __init__(
        self,
        queue_store_path: Path,
        port: int,
        output_dir: Path,
        output_formats: tuple[str, ...],
        model_name: str,
        language: str | None,
    ) -> None:
        super().__init__()
        self.queue_store_path = queue_store_path
        self.port = port
        self.output_dir = output_dir
        self.output_formats = output_formats
        self.model_name = model_name
        self.language = language
        self._server = None

    def run(self) -> None:
        """Start the server (blocking)."""
        try:
            from flowscribe.server import BookmarkletServer

            # Configure logging to suppress server logs in GUI
            logging.getLogger("flowscribe.server").setLevel(logging.WARNING)

            self._server = BookmarkletServer(
                queue_store_path=self.queue_store_path,
                host="127.0.0.1",
                port=self.port,
                status_interval=30,
                default_output_dir=self.output_dir,
                default_output_formats=self.output_formats,
                default_model_name=self.model_name,
                default_language=self.language,
            )

            self.started.emit(self.port)
            self._server.start()  # Blocking call

        except OSError as e:
            if _is_address_in_use_error(e):
                self.error.emit(f"Port {self.port} is already in use")
            else:
                self.error.emit(str(e))
        except Exception as e:
            logger.exception("Server error")
            self.error.emit(str(e))
        finally:
            self.stopped.emit()

    def stop(self) -> None:
        """Stop the server."""
        if self._server:
            self._server.stop()
