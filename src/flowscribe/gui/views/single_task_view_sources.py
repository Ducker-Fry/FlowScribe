from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog, QListWidgetItem

from flowscribe.gui.state import is_acceptable_local_source


class SingleTaskViewSourcesMixin:
    """Source input and capture helpers for the single-task view."""

    def _choose_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, "Choose media files")
        if not paths:
            return
        for path in paths:
            self._add_local_file(Path(path))
        self._refresh_file_summary()
        self._refresh_action_buttons()

    def _add_local_file(self, path: Path) -> bool:
        if not is_acceptable_local_source(path):
            self.status_label.setText(f"Unsupported file: {path}")
            return False
        if path in self._local_paths:
            return False
        self._local_paths.append(path)
        item = QListWidgetItem(str(path))
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        item.setCheckState(Qt.CheckState.Unchecked)
        self.file_list.addItem(item)
        self._refresh_file_summary()
        self._refresh_action_buttons()
        return True

    def _add_dropped_files(self, paths: list[Path]) -> None:
        added = 0
        for path in paths:
            if self._add_local_file(path):
                added += 1
        self.status_label.setText(f"Added {added} file(s)" if added else "No new files added")
        self._refresh_action_buttons()

    def _select_all_files(self) -> None:
        for index in range(self.file_list.count()):
            item = self.file_list.item(index)
            if item:
                item.setCheckState(Qt.CheckState.Checked)
        self._refresh_file_summary()
        self._refresh_action_buttons()

    def _clear_files(self) -> None:
        self._local_paths.clear()
        self.file_list.clear()
        self._refresh_file_summary()
        self._refresh_action_buttons()
        self.status_label.setText("Files cleared")

    def _on_file_list_changed(self) -> None:
        self._refresh_file_summary()
        self._refresh_action_buttons()

    def _refresh_file_summary(self) -> None:
        total = self.file_list.count()
        checked = sum(
            1
            for index in range(total)
            if (item := self.file_list.item(index))
            and item.checkState() == Qt.CheckState.Checked
        )
        noun = "file" if total == 1 else "files"
        self.file_summary_label.setText(f"{checked}/{total} {noun} selected")

    def _start_capture(self) -> None:
        self.capture_status_label.setText("Capturing...")
        self.status_label.setText("System audio capture started")
        self._refresh_action_buttons()

    def _stop_capture(self) -> None:
        self.capture_status_label.setText("Not capturing")
        self.status_label.setText("System audio capture stopped")
        self._refresh_action_buttons()

    def _get_checked_paths(self) -> list[Path]:
        checked: list[Path] = []
        for index in range(self.file_list.count()):
            item = self.file_list.item(index)
            if item and item.checkState() == Qt.CheckState.Checked:
                checked.append(Path(item.text()))
        return checked

    def _has_selected_sources(self) -> bool:
        return bool(self._get_checked_paths() or self.url_input.text().strip())

    def _is_capture_running(self) -> bool:
        return self.capture_status_label.text().strip() != "Not capturing"

