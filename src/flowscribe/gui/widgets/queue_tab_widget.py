"""Queue management tab widget for the Views dialog."""

from __future__ import annotations


from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from flowscribe.tasks.queue_models import QueueItem, QueueItemStatus


_STATUS_ICONS: dict[QueueItemStatus, str] = {
    "pending": "[...]",
    "running": "[>>>]",
    "completed": "[OK]",
    "failed": "[ERR]",
    "canceled": "[---]",
}


class QueueTabWidget(QWidget):

    enqueue_urls_requested = Signal(str)
    import_file_requested = Signal(str)
    start_queue_requested = Signal()
    cancel_queue_requested = Signal()
    skip_current_requested = Signal()
    retry_item_requested = Signal(str)
    remove_items_requested = Signal(list)  # list[str]
    clear_completed_requested = Signal()
    reorder_requested = Signal(list)
    max_retries_changed = Signal(int)
    server_start_requested = Signal(int)  # port
    server_stop_requested = Signal()
    edit_item_settings_requested = Signal(list)  # list[str] - item_ids

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._item_ids: list[str] = []
        self._setup_ui()
        self._queue_list.itemChanged.connect(self._update_button_states)
        self._queue_list.itemSelectionChanged.connect(self._update_button_states)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Bookmarklet Server section
        server_group = QGroupBox("Bookmarklet Server")
        server_layout = QVBoxLayout(server_group)
        server_layout.setSpacing(4)

        server_control_row = QHBoxLayout()
        self._server_enabled_check = QCheckBox("Enable Server")
        self._server_enabled_check.setToolTip("Start HTTP server to receive URLs from browser bookmarklet")
        self._server_enabled_check.stateChanged.connect(self._on_server_toggle)
        server_control_row.addWidget(self._server_enabled_check)

        server_control_row.addWidget(QLabel("Port:"))
        self._server_port_spin = QSpinBox()
        self._server_port_spin.setRange(1024, 65535)
        self._server_port_spin.setValue(8765)
        self._server_port_spin.setMaximumWidth(80)
        self._server_port_spin.setToolTip("Server port (default: 8765)")
        server_control_row.addWidget(self._server_port_spin)

        self._server_status_label = QLabel("Server: Stopped")
        self._server_status_label.setStyleSheet("color: gray;")
        server_control_row.addWidget(self._server_status_label)
        server_control_row.addStretch()

        server_layout.addLayout(server_control_row)

        self._server_info_label = QLabel(
            "Enable server to add URLs from browser. "
            "Visit http://127.0.0.1:8765/bookmarklet.js for installation."
        )
        self._server_info_label.setWordWrap(True)
        self._server_info_label.setStyleSheet("color: gray; font-size: 10px;")
        server_layout.addWidget(self._server_info_label)

        layout.addWidget(server_group)

        import_label = QLabel("Paste URLs (one per line) or import from file:")
        layout.addWidget(import_label)

        self._url_input = QTextEdit()
        self._url_input.setPlaceholderText(
            "https://example.com/video1\nhttps://example.com/video2\n..."
        )
        self._url_input.setMaximumHeight(100)
        layout.addWidget(self._url_input)

        import_row = QHBoxLayout()
        self._add_urls_btn = QPushButton("Add URLs")
        self._add_urls_btn.clicked.connect(self._on_add_urls)
        import_row.addWidget(self._add_urls_btn)

        self._import_file_btn = QPushButton("Import File...")
        self._import_file_btn.clicked.connect(self._on_import_file)
        import_row.addWidget(self._import_file_btn)
        import_row.addStretch()
        layout.addLayout(import_row)

        settings_row = QHBoxLayout()
        settings_row.addWidget(QLabel("Max Retries:"))
        self._max_retries_spin = QSpinBox()
        self._max_retries_spin.setRange(0, 10)
        self._max_retries_spin.setValue(2)
        self._max_retries_spin.valueChanged.connect(self.max_retries_changed.emit)
        settings_row.addWidget(self._max_retries_spin)
        settings_row.addStretch()
        layout.addLayout(settings_row)

        self._output_dir_label = QLabel()
        self._output_dir_label.setStyleSheet("color: #888; font-size: 10pt;")
        layout.addWidget(self._output_dir_label)

        queue_label = QLabel("Queue:")
        layout.addWidget(queue_label)

        self._queue_list = QListWidget()
        self._queue_list.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self._queue_list.setDefaultDropAction(Qt.DropAction.MoveAction)
        self._queue_list.model().rowsMoved.connect(self._on_rows_moved)
        layout.addWidget(self._queue_list, stretch=1)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        layout.addWidget(self._progress_bar)

        self._status_label = QLabel("Queue idle.")
        layout.addWidget(self._status_label)

        action_row = QHBoxLayout()
        self._start_btn = QPushButton("Start Queue")
        self._start_btn.clicked.connect(self.start_queue_requested.emit)
        action_row.addWidget(self._start_btn)

        self._cancel_btn = QPushButton("Cancel All")
        self._cancel_btn.setEnabled(False)
        self._cancel_btn.clicked.connect(self.cancel_queue_requested.emit)
        action_row.addWidget(self._cancel_btn)

        self._skip_btn = QPushButton("Skip Current")
        self._skip_btn.setEnabled(False)
        self._skip_btn.clicked.connect(self.skip_current_requested.emit)
        action_row.addWidget(self._skip_btn)
        layout.addLayout(action_row)

        action_row2 = QHBoxLayout()
        self._retry_btn = QPushButton("Retry Selected")
        self._retry_btn.clicked.connect(self._on_retry_selected)
        action_row2.addWidget(self._retry_btn)

        self._edit_settings_btn = QPushButton("Edit Settings")
        self._edit_settings_btn.clicked.connect(self._on_edit_settings)
        action_row2.addWidget(self._edit_settings_btn)

        self._remove_btn = QPushButton("Remove Selected")
        self._remove_btn.clicked.connect(self._on_remove_selected)
        action_row2.addWidget(self._remove_btn)

        self._clear_btn = QPushButton("Clear Completed")
        self._clear_btn.clicked.connect(self.clear_completed_requested.emit)
        action_row2.addWidget(self._clear_btn)

        self._select_all_btn = QPushButton("Select All")
        self._select_all_btn.clicked.connect(self._on_select_all)
        action_row2.addWidget(self._select_all_btn)

        layout.addLayout(action_row2)

    def refresh_queue_list(self, items: list[QueueItem]) -> None:
        self._queue_list.clear()
        self._item_ids.clear()
        for item in items:
            icon = _STATUS_ICONS.get(item.status, "[?]")
            label = item.display_label
            if item.error_message and item.status == "failed":
                text = f"{icon} {label}  ({item.error_message[:60]})"
            elif item.status == "running":
                text = f"{icon} {label}  (attempt {item.attempt_count + 1})"
            else:
                text = f"{icon} {label}"
            list_item = QListWidgetItem(text)
            list_item.setData(Qt.ItemDataRole.UserRole, item.item_id)
            list_item.setFlags(list_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            list_item.setCheckState(Qt.CheckState.Unchecked)
            self._queue_list.addItem(list_item)
            self._item_ids.append(item.item_id)

    def set_overall_progress(self, completed: int, total: int) -> None:
        if total > 0:
            self._progress_bar.setValue(int(completed / total * 100))
        else:
            self._progress_bar.setValue(0)
        self._status_label.setText(f"Completed {completed}/{total}")

    def set_running(self, running: bool) -> None:
        self._start_btn.setEnabled(not running)
        self._cancel_btn.setEnabled(running)
        self._skip_btn.setEnabled(running)
        self._add_urls_btn.setEnabled(not running)
        self._import_file_btn.setEnabled(not running)
        if not running:
            self._status_label.setText("Queue idle.")

    def set_current_item_status(self, label: str) -> None:
        self._status_label.setText(label)

    @property
    def max_retries(self) -> int:
        return self._max_retries_spin.value()

    def set_output_dir_display(self, output_dir: str, output_formats: tuple[str, ...] = ()) -> None:
        """Update the output directory display label."""
        formats_text = ", ".join(output_formats) if output_formats else "json (default)"
        self._output_dir_label.setText(f"Output: {output_dir} | Formats: {formats_text}")

    def get_checked_item_ids(self) -> list[str]:
        """Return IDs of all checked items."""
        checked = []
        for i in range(self._queue_list.count()):
            item = self._queue_list.item(i)
            if item and item.checkState() == Qt.CheckState.Checked:
                item_id = item.data(Qt.ItemDataRole.UserRole)
                if item_id:
                    checked.append(item_id)
        return checked

    def get_selected_or_checked_item_ids(self) -> list[str]:
        """Return checked items (priority) or current selected item."""
        checked = self.get_checked_item_ids()
        if checked:
            return checked

        current = self._queue_list.currentItem()
        if current:
            item_id = current.data(Qt.ItemDataRole.UserRole)
            if item_id:
                return [item_id]

        return []

    def _on_add_urls(self) -> None:
        text = self._url_input.toPlainText().strip()
        if not text:
            return

        # Try to extract URLs from rich text if plain text doesn't contain URLs
        from PySide6.QtGui import QGuiApplication
        clipboard = QGuiApplication.clipboard()
        mime_data = clipboard.mimeData()

        # If plain text doesn't look like URLs, try HTML
        if mime_data and mime_data.hasHtml() and not text.startswith("http"):
            html = mime_data.html()
            # Extract href attributes from HTML
            import re
            urls = re.findall(r'href=["\']([^"\']+)["\']', html)
            if urls:
                # Filter to http/https URLs
                http_urls = [u for u in urls if u.startswith(("http://", "https://"))]
                if http_urls:
                    text = "\n".join(http_urls)

        self.enqueue_urls_requested.emit(text)
        self._url_input.clear()

    def _on_import_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Import URLs from file",
            "",
            "Supported Files (*.txt *.csv *.xlsx);;Text Files (*.txt);;CSV Files (*.csv);;Excel Files (*.xlsx)",
        )
        if path:
            self.import_file_requested.emit(path)

    def _on_retry_selected(self) -> None:
        current = self._queue_list.currentItem()
        if current:
            item_id = current.data(Qt.ItemDataRole.UserRole)
            if item_id:
                self.retry_item_requested.emit(item_id)

    def _on_edit_settings(self) -> None:
        """Edit settings for selected/checked items (supports batch editing)."""
        item_ids = self.get_selected_or_checked_item_ids()
        if item_ids:
            self.edit_item_settings_requested.emit(item_ids)

    def _on_remove_selected(self) -> None:
        item_ids = self.get_selected_or_checked_item_ids()
        if item_ids:
            self.remove_items_requested.emit(item_ids)

    def _on_select_all(self) -> None:
        """Select all items in queue."""
        for i in range(self._queue_list.count()):
            item = self._queue_list.item(i)
            if item:
                item.setCheckState(Qt.CheckState.Checked)

    def _update_button_states(self) -> None:
        """Update button text and enabled state based on selection/checked items."""
        checked_count = len(self.get_checked_item_ids())
        selected = self._queue_list.currentItem()

        if checked_count > 0:
            self._remove_btn.setText(f"Remove Checked ({checked_count})")
            self._remove_btn.setEnabled(True)
        elif selected:
            self._remove_btn.setText("Remove Selected")
            self._remove_btn.setEnabled(True)
        else:
            self._remove_btn.setText("Remove Selected")
            self._remove_btn.setEnabled(False)

    def keyPressEvent(self, event) -> None:
        """Handle keyboard shortcuts."""
        if event.key() == Qt.Key.Key_Space:
            current = self._queue_list.currentItem()
            if current:
                current.setCheckState(
                    Qt.CheckState.Unchecked
                    if current.checkState() == Qt.CheckState.Checked
                    else Qt.CheckState.Checked
                )
                event.accept()
                return
        elif event.key() == Qt.Key.Key_Delete:
            self._on_remove_selected()
            event.accept()
            return
        elif event.matches(QKeySequence.StandardKey.SelectAll):
            for i in range(self._queue_list.count()):
                item = self._queue_list.item(i)
                if item:
                    item.setCheckState(Qt.CheckState.Checked)
            event.accept()
            return

        super().keyPressEvent(event)

    def _on_rows_moved(self) -> None:
        new_order: list[str] = []
        for i in range(self._queue_list.count()):
            item = self._queue_list.item(i)
            if item:
                item_id = item.data(Qt.ItemDataRole.UserRole)
                if item_id:
                    new_order.append(item_id)
        if new_order:
            self.reorder_requested.emit(new_order)

    def _on_server_toggle(self, state: int) -> None:
        """Handle server enable/disable toggle."""
        if state == Qt.CheckState.Checked.value:
            port = self._server_port_spin.value()
            self._server_port_spin.setEnabled(False)
            self.server_start_requested.emit(port)
        else:
            self._server_port_spin.setEnabled(True)
            self.server_stop_requested.emit()

    def set_server_status(self, running: bool, port: int | None = None) -> None:
        """Update server status display."""
        if running and port:
            self._server_status_label.setText(f"Server: Running on port {port}")
            self._server_status_label.setStyleSheet("color: green;")
            self._server_info_label.setText(
                f"Server running. Visit http://127.0.0.1:{port}/bookmarklet.js for installation."
            )
            self._server_enabled_check.setChecked(True)
            self._server_port_spin.setEnabled(False)
        else:
            self._server_status_label.setText("Server: Stopped")
            self._server_status_label.setStyleSheet("color: gray;")
            self._server_info_label.setText(
                "Enable server to add URLs from browser. "
                "Visit http://127.0.0.1:8765/bookmarklet.js for installation."
            )
            self._server_enabled_check.setChecked(False)
            self._server_port_spin.setEnabled(True)
