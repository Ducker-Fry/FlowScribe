from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtWidgets import QFileDialog


class SingleTaskViewDialogMixin:
    """Dialog bridge and progressive cache helpers for the single-task view."""

    def _open_transcript(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Transcript JSON",
            "",
            "JSON files (*.json);;All files (*.*)",
        )
        if not file_path:
            return

        try:
            path = Path(file_path)
            transcript_data = json.loads(path.read_text(encoding="utf-8"))
            if "segments" not in transcript_data:
                self.status_label.setText("Invalid transcript format - missing segments")
                return

            self._last_transcript_path = path
            self._last_output_paths = [path]
            self._current_run_output = f"Opened existing transcript: {path.name}\n"
            self._load_dialog_transcript(path)
            self._show_view_dialog()
            self.transcript_loaded.emit(path)
        except Exception as exc:
            self.status_label.setText(f"Error loading transcript: {exc}")

    def _create_view_dialog(self) -> None:
        from flowscribe.gui.dialogs import TranscriptionViewDialog

        self._view_dialog = TranscriptionViewDialog(
            self,
            transcript_path=None,
            run_output="",
            result=None,
            output_paths=None,
        )

    def _open_view(self) -> None:
        if self._view_dialog is None:
            self._create_view_dialog()

        if self._last_transcript_path is not None:
            self._load_dialog_transcript(self._last_transcript_path)
        self._show_view_dialog()

    def _load_dialog_transcript(self, path: Path) -> None:
        if self._view_dialog is None:
            return
        if self._last_output_paths:
            self._view_dialog._load_transcript_with_artifacts(path, tuple(self._last_output_paths))
        else:
            self._view_dialog._load_transcript(path)
        self._view_dialog.update_run_output(self._current_run_output)

    def _show_view_dialog(self) -> None:
        if self._view_dialog is None:
            return
        self._view_dialog.update_run_output(self._current_run_output)
        self._view_dialog.show()
        self._view_dialog.raise_()
        self._view_dialog.activateWindow()
        status_msg = (
            f"Opened view for {self._last_transcript_path.name}"
            if self._last_transcript_path
            else "Opened view"
        )
        self.status_label.setText(status_msg)

    def _sync_view_dialog_from_result(self) -> None:
        if self._last_transcript_path is None or self._view_dialog is None:
            return
        if self._view_dialog.isVisible():
            self._load_dialog_transcript(self._last_transcript_path)

    def _detect_progressive_cache(self) -> None:
        if self._current_output_dir is None:
            return

        try:
            search_root = self._current_output_dir.parent
            if not search_root.exists():
                search_root = self._current_output_dir

            progressive_files: list[Path] = []
            for item in search_root.iterdir():
                if item.is_dir():
                    progressive_path = item / ".progressive" / "partial-transcript.json"
                    if (
                        progressive_path.exists()
                        and progressive_path.stat().st_mtime >= self._transcription_start_time
                    ):
                        progressive_files.append(progressive_path)

            if not progressive_files and self._current_output_dir.exists():
                json_files = [
                    json_file
                    for json_file in self._current_output_dir.glob("*.json")
                    if json_file.stat().st_mtime >= self._transcription_start_time
                ]
                if json_files:
                    progressive_files = [max(json_files, key=lambda path: path.stat().st_mtime)]

            if not progressive_files:
                return

            latest_cache = max(progressive_files, key=lambda path: path.stat().st_mtime)
            data = json.loads(latest_cache.read_text(encoding="utf-8"))
            if "segments" not in data or not data["segments"]:
                return

            self._last_transcript_path = latest_cache
            if latest_cache not in self._last_output_paths:
                self._last_output_paths.append(latest_cache)

            if self._view_dialog is not None and self._view_dialog.isVisible():
                self._load_dialog_transcript(latest_cache)

            self.status_label.setText(
                "Progressive cache detected - You can now open View to see progress"
            )
        except Exception:
            pass
