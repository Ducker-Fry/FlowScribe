"""Mixin for system audio capture controls in the FlowScribe GUI."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from flowscribe.core.errors import MediaPreparationError

if TYPE_CHECKING:
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QCheckBox, QLabel, QLineEdit, QListWidget, QPushButton

    from flowscribe.media.system_audio_capture_helper import CaptureController


class CaptureControlsMixin:
    """Mixin providing system audio capture control methods for MainWindow."""

    # Type hints for attributes that must be provided by the main window
    _capture_controller: CaptureController
    _capture_supported: bool
    _capture_default_device_name: str | None
    _capture_activity_timer: QTimer
    _active_capture_path: Path | None
    _temporary_capture_paths: set[Path]
    _thread: object | None
    _local_paths: list[Path]

    # UI elements
    output_dir_input: QLineEdit
    capture_status_label: QLabel
    status_label: QLabel
    start_capture_button: QPushButton
    stop_capture_button: QPushButton
    keep_capture_file_check: QCheckBox
    file_list: QListWidget

    # Methods that must be provided by the main window
    def _add_local_file(self, path: Path) -> None:
        """Add a local file to the source list."""
        raise NotImplementedError

    def _check_newly_added_sources(self, paths: list[Path]) -> None:
        """Check newly added sources for validity."""
        raise NotImplementedError

    def _persist_local_source_state(self) -> None:
        """Persist the local source state to disk."""
        raise NotImplementedError

    def _refresh_diagnostics_summary(self) -> None:
        """Refresh the diagnostics summary display."""
        raise NotImplementedError

    def _capture_output_dir(self) -> Path:
        """Return the output directory for captured audio files."""
        return Path(self.output_dir_input.text().strip() or "outputs") / ".flowscribe-capture"

    def _capture_support_message(self, supported: bool, reason: str | None) -> str:
        """Generate a user-friendly message about capture support status."""
        if supported:
            device_text = self._capture_default_device_name or "the default output device"
            return (
                f"Ready to capture Windows system playback from {device_text}. "
                "Start playback before or during capture so the helper has audio to record."
            )

        detail = (reason or "").strip()
        if "wasapicapturehelper.exe was not found" in detail.lower():
            return (
                "System audio capture helper is missing. Rebuild the GUI package or "
                "use a release bundle that includes WasapiCaptureHelper.exe."
            )
        if detail:
            return f"System audio capture is unavailable: {detail}"
        return "System audio capture is unavailable on this machine."

    def _refresh_capture_activity_feedback(self) -> None:
        """Update the capture status label with current activity information."""
        if not self._capture_controller.is_recording():
            self._capture_activity_timer.stop()
            return
        status = self._capture_controller.activity_status()
        device_text = self._capture_default_device_name or "default output device"
        if status.state == "active":
            self.capture_status_label.setText(
                f"Capturing system audio from {device_text}. {status.message}"
            )
            return
        if status.state == "stalled":
            self.capture_status_label.setText(
                f"Capturing system audio from {device_text}. {status.message}"
            )

    def _start_system_capture(self) -> None:
        """Start capturing system audio to a timestamped WAV file."""
        self._refresh_capture_support()
        if not self._capture_supported:
            self.status_label.setText("System audio capture is not available. Open Help for capture requirements and fallback options.")
            return
        if self._capture_controller.is_recording():
            self.capture_status_label.setText("System audio capture is already running.")
            return
        if self._thread is not None:
            self.capture_status_label.setText("Wait for the current transcription job to finish first.")
            return

        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        output_path = self._capture_output_dir() / f"capture-{timestamp}.wav"
        try:
            started = self._capture_controller.start_capture(output_path)
        except MediaPreparationError as exc:
            self.capture_status_label.setText(str(exc))
            self.status_label.setText("Could not start system audio capture. Open Help for helper and environment checks.")
            self._refresh_diagnostics_summary()
            return

        self._active_capture_path = started.output_path
        self.start_capture_button.setEnabled(False)
        self.stop_capture_button.setEnabled(True)
        device_name = started.device.name if started.device is not None else self._capture_default_device_name
        device_text = device_name or "default output device"
        self.capture_status_label.setText(
            f"Capturing system audio from {device_text}. Waiting for audio activity..."
        )
        self.status_label.setText("System audio capture started.")
        self._capture_activity_timer.start()
        self._refresh_diagnostics_summary()

    def _stop_system_capture(self) -> None:
        """Stop the current system audio capture and add the result to sources."""
        if not self._capture_controller.is_recording():
            self.capture_status_label.setText("System audio capture is not running.")
            return

        try:
            completed = self._capture_controller.stop_capture()
        except MediaPreparationError as exc:
            self.start_capture_button.setEnabled(True)
            self.stop_capture_button.setEnabled(False)
            self._active_capture_path = None
            self._capture_activity_timer.stop()
            self.capture_status_label.setText(str(exc))
            self.status_label.setText("System audio capture failed. Open Help for next-step diagnostics.")
            self._refresh_diagnostics_summary()
            return

        output_path = completed.output_path
        self.start_capture_button.setEnabled(True)
        self.stop_capture_button.setEnabled(False)
        self._active_capture_path = None
        self._capture_activity_timer.stop()
        self._add_local_file(output_path)
        self._check_newly_added_sources([output_path])
        if not self.keep_capture_file_check.isChecked():
            self._temporary_capture_paths.add(output_path)
            self.capture_status_label.setText(
                f"Captured audio ready for transcription. It will be deleted after the run: {output_path.name}"
            )
        else:
            self.capture_status_label.setText(
                f"Captured audio saved as local source: {output_path.name}"
            )
        self.status_label.setText(f"Captured system audio: {output_path.name}")
        self._persist_local_source_state()
        self._refresh_diagnostics_summary()

    def _cleanup_temporary_capture_files(self) -> None:
        """Remove temporary capture files and update the source list."""
        if not self._temporary_capture_paths:
            return

        removed_paths: list[Path] = []
        for path in list(self._temporary_capture_paths):
            try:
                path.unlink(missing_ok=True)
            except OSError:
                continue
            removed_paths.append(path)
            self._temporary_capture_paths.discard(path)

        if not removed_paths:
            return

        removed_set = {path.resolve() if path.exists() else path for path in removed_paths}
        self._local_paths = [
            path
            for path in self._local_paths
            if (path.resolve() if path.exists() else path) not in removed_set
        ]
        for index in range(self.file_list.count() - 1, -1, -1):
            item = self.file_list.item(index)
            if item is None:
                continue
            item_path = Path(item.text())
            comparable = item_path.resolve() if item_path.exists() else item_path
            if comparable in removed_set:
                self.file_list.takeItem(index)
        self._persist_local_source_state()

    def _refresh_capture_support(self) -> None:
        """Check capture support status and update UI accordingly."""
        try:
            status = self._capture_controller.support_status()
            supported = status.supported
            self._capture_default_device_name = (
                status.default_device.name if status.default_device is not None else None
            )
            message = self._capture_support_message(supported, status.reason)
        except MediaPreparationError as exc:
            supported = False
            self._capture_default_device_name = None
            message = self._capture_support_message(False, str(exc))

        self._capture_supported = supported
        if self._capture_controller.is_recording():
            self.start_capture_button.setEnabled(False)
            self.stop_capture_button.setEnabled(True)
            self._capture_activity_timer.start()
            return

        self.start_capture_button.setEnabled(supported and self._thread is None)
        self.stop_capture_button.setEnabled(False)
        self._capture_activity_timer.stop()
        if not supported:
            self.capture_status_label.setText(message)
        elif self.capture_status_label.text().startswith("Could not start system audio capture"):
            self.capture_status_label.setText(message)
        elif self.capture_status_label.text() == "System capture is idle.":
            self.capture_status_label.setText(message)
        self._refresh_diagnostics_summary()
