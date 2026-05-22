"""Queue view for batch transcription tasks."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from flowscribe.queue.models import QueueItem, QueueItemStatus

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget as QWidgetType


_STATUS_ICONS: dict[QueueItemStatus, str] = {
    "pending": "[...]",
    "running": "[>>>]",
    "completed": "[OK]",
    "failed": "[ERR]",
    "canceled": "[---]",
}


class QueueView(QWidget):
    """View for managing batch transcription queue."""

    # Signals
    enqueue_urls_requested = Signal(str)
    enqueue_files_requested = Signal(list)  # list[Path]
    import_file_requested = Signal(str)
    start_queue_requested = Signal()
    cancel_queue_requested = Signal()
    skip_current_requested = Signal()
    retry_item_requested = Signal(str)
    remove_items_requested = Signal(list)  # list[str]
    clear_completed_requested = Signal()
    reorder_requested = Signal(list)
    edit_item_settings_requested = Signal(str)
    server_start_requested = Signal(int)  # port
    server_stop_requested = Signal()

    def __init__(self, settings: dict, parent: QWidgetType | None = None):
        super().__init__(parent)
        self._settings = settings
        self._item_ids: list[str] = []
        self._items_cache: dict[str, QueueItem] = {}
        self._current_running_item_id: str | None = None
        self._current_run_output: str = ""
        self._view_dialog = None  # Persistent dialog like Single Task
        self._setup_ui()
        self._create_view_dialog()  # Create dialog at initialization

    def _setup_ui(self) -> None:
        """Initialize UI components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Bookmarklet Server section
        server_group = QGroupBox("Bookmarklet Server")
        server_layout = QVBoxLayout(server_group)
        server_layout.setSpacing(6)

        server_control_row = QHBoxLayout()
        self._server_enabled_check = QCheckBox("Enable Server")
        self._server_enabled_check.setToolTip(
            "Start HTTP server to receive URLs from browser bookmarklet"
        )
        self._server_enabled_check.stateChanged.connect(self._on_server_toggle)
        server_control_row.addWidget(self._server_enabled_check)

        server_control_row.addWidget(QLabel("Port:"))
        self._server_port_spin = QSpinBox()
        self._server_port_spin.setRange(1024, 65535)
        self._server_port_spin.setValue(8765)
        self._server_port_spin.setMaximumWidth(80)
        server_control_row.addWidget(self._server_port_spin)

        self._server_status_label = QLabel("Server: Stopped")
        self._server_status_label.setStyleSheet("color: gray;")
        server_control_row.addWidget(self._server_status_label)
        server_control_row.addStretch()

        server_layout.addLayout(server_control_row)

        server_info = QLabel(
            "Enable server to add URLs from browser. "
            "Visit http://127.0.0.1:8765/bookmarklet.js for installation."
        )
        server_info.setWordWrap(True)
        server_info.setStyleSheet("color: gray; font-size: 10px;")
        server_layout.addWidget(server_info)

        layout.addWidget(server_group)

        # Add sources section
        add_group = QGroupBox("Add Sources")
        add_layout = QVBoxLayout(add_group)
        add_layout.setSpacing(8)

        # Local files
        local_label = QLabel("Local Files:")
        add_layout.addWidget(local_label)

        local_buttons = QHBoxLayout()
        self._add_files_btn = QPushButton("Add Local Files...")
        self._add_files_btn.clicked.connect(self._on_add_local_files)
        local_buttons.addWidget(self._add_files_btn)
        local_buttons.addStretch()
        add_layout.addLayout(local_buttons)

        # URLs
        url_label = QLabel("URLs (one per line):")
        add_layout.addWidget(url_label)

        self._url_input = QTextEdit()
        self._url_input.setPlaceholderText(
            "https://example.com/video1\nhttps://example.com/video2\n..."
        )
        self._url_input.setMaximumHeight(80)
        add_layout.addWidget(self._url_input)

        url_buttons = QHBoxLayout()
        self._add_urls_btn = QPushButton("Add URLs")
        self._add_urls_btn.clicked.connect(self._on_add_urls)
        url_buttons.addWidget(self._add_urls_btn)

        self._import_file_btn = QPushButton("Import from File...")
        self._import_file_btn.clicked.connect(self._on_import_file)
        url_buttons.addWidget(self._import_file_btn)
        url_buttons.addStretch()
        add_layout.addLayout(url_buttons)

        layout.addWidget(add_group)

        # Queue settings
        settings_row = QHBoxLayout()
        settings_row.addWidget(QLabel("Max Retries:"))
        self._max_retries_spin = QSpinBox()
        self._max_retries_spin.setRange(0, 10)
        self._max_retries_spin.setValue(2)
        settings_row.addWidget(self._max_retries_spin)
        settings_row.addStretch()
        layout.addLayout(settings_row)

        # Download options row
        download_row = QHBoxLayout()

        self._preserve_media_check = QCheckBox("Preserve media")
        download_row.addWidget(self._preserve_media_check)

        download_row.addWidget(QLabel("Type:"))
        self._media_type_combo = QComboBox()
        self._media_type_combo.addItems(["Audio", "Video"])
        self._media_type_combo.setCurrentText("Audio")
        download_row.addWidget(self._media_type_combo)

        download_row.addWidget(QLabel("Quality:"))
        self._download_quality_combo = QComboBox()
        self._download_quality_combo.addItems(["Best", "High", "Medium", "Low"])
        self._download_quality_combo.setCurrentText("Best")
        download_row.addWidget(self._download_quality_combo)

        download_row.addWidget(QLabel("Format:"))
        self._download_format_combo = QComboBox()
        self._download_format_combo.addItems(["Auto", "mp4", "webm", "mp3", "m4a", "opus"])
        self._download_format_combo.setCurrentText("Auto")
        download_row.addWidget(self._download_format_combo)

        download_row.addStretch()
        layout.addLayout(download_row)

        # Queue list
        queue_label = QLabel("Queue:")
        layout.addWidget(queue_label)

        self._queue_list = QListWidget()
        self._queue_list.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self._queue_list.setDefaultDropAction(Qt.DropAction.MoveAction)
        self._queue_list.model().rowsMoved.connect(self._on_rows_moved)
        self._queue_list.itemChanged.connect(self._update_button_states)
        self._queue_list.itemSelectionChanged.connect(self._update_button_states)
        layout.addWidget(self._queue_list, 1)

        # Queue controls
        controls_row = QHBoxLayout()
        self._start_queue_btn = QPushButton("Start Queue")
        self._start_queue_btn.clicked.connect(self._on_start_queue)
        controls_row.addWidget(self._start_queue_btn)

        self._cancel_queue_btn = QPushButton("Cancel Queue")
        self._cancel_queue_btn.clicked.connect(self._on_cancel_queue)
        self._cancel_queue_btn.setEnabled(False)
        controls_row.addWidget(self._cancel_queue_btn)

        self._skip_current_btn = QPushButton("Skip Current")
        self._skip_current_btn.clicked.connect(self._on_skip_current)
        self._skip_current_btn.setEnabled(False)
        controls_row.addWidget(self._skip_current_btn)

        controls_row.addStretch()
        layout.addLayout(controls_row)

        item_controls_row = QHBoxLayout()
        self._edit_settings_btn = QPushButton("Edit Settings")
        self._edit_settings_btn.clicked.connect(self._on_edit_settings)
        item_controls_row.addWidget(self._edit_settings_btn)

        self._retry_btn = QPushButton("Retry Failed")
        self._retry_btn.clicked.connect(self._on_retry_failed)
        item_controls_row.addWidget(self._retry_btn)

        self._open_view_btn = QPushButton("Open View")
        self._open_view_btn.clicked.connect(self._on_open_view)
        item_controls_row.addWidget(self._open_view_btn)

        self._remove_btn = QPushButton("Remove Selected")
        self._remove_btn.clicked.connect(self._on_remove_selected)
        item_controls_row.addWidget(self._remove_btn)

        self._clear_completed_btn = QPushButton("Clear Completed")
        self._clear_completed_btn.clicked.connect(self._on_clear_completed)
        item_controls_row.addWidget(self._clear_completed_btn)

        self._select_all_btn = QPushButton("Select All")
        self._select_all_btn.clicked.connect(self._on_select_all)
        item_controls_row.addWidget(self._select_all_btn)

        item_controls_row.addStretch()
        layout.addLayout(item_controls_row)

        # Status label
        self._status_label = QLabel("Queue is empty")
        layout.addWidget(self._status_label)

        self._update_button_states()

    def update_settings(self, settings: dict) -> None:
        """Update view with new settings."""
        self._settings = settings

    def _on_add_local_files(self) -> None:
        """Open file chooser to add local files."""
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Add Local Files to Queue", "", "Media files (*.mp3 *.mp4 *.wav *.m4a *.flac *.ogg *.webm);;All files (*.*)"
        )
        if paths:
            file_paths = [Path(p) for p in paths]
            self.enqueue_files_requested.emit(file_paths)
            self._status_label.setText(f"Added {len(file_paths)} local file(s) to queue")

    def _on_add_urls(self) -> None:
        """Add URLs from text input."""
        text = self._url_input.toPlainText().strip()
        if text:
            self.enqueue_urls_requested.emit(text)
            self._url_input.clear()

    def get_download_options(self) -> dict:
        """Get current download options from UI."""
        quality_map = {"Best": "best", "High": "high", "Medium": "medium", "Low": "low"}
        quality = quality_map.get(self._download_quality_combo.currentText(), "best")
        prefer_format = None
        if self._download_format_combo.currentText() != "Auto":
            prefer_format = self._download_format_combo.currentText()
        media_kind = "video" if self._media_type_combo.currentText() == "Video" else "audio"
        return {
            "quality": quality,
            "prefer_format": prefer_format,
            "preserve_media": self._preserve_media_check.isChecked(),
            "media_kind": media_kind,
        }

    def _on_import_file(self) -> None:
        """Import URLs from file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Import URLs from File",
            "",
            "Text files (*.txt);;CSV files (*.csv);;Excel files (*.xlsx);;All files (*.*)",
        )
        if file_path:
            self.import_file_requested.emit(file_path)

    def _on_server_toggle(self, state: int) -> None:
        """Handle server enable/disable."""
        if state == Qt.CheckState.Checked.value:
            port = self._server_port_spin.value()
            self.server_start_requested.emit(port)
        else:
            self.server_stop_requested.emit()

    def _on_start_queue(self) -> None:
        """Start queue processing."""
        self.start_queue_requested.emit()
        self._start_queue_btn.setEnabled(False)
        self._cancel_queue_btn.setEnabled(True)
        self._skip_current_btn.setEnabled(True)

    def _on_cancel_queue(self) -> None:
        """Cancel queue processing."""
        self.cancel_queue_requested.emit()

    def _on_skip_current(self) -> None:
        """Skip current item."""
        self.skip_current_requested.emit()

    def _on_edit_settings(self) -> None:
        """Edit settings for selected item."""
        selected = self._get_selected_item_ids()
        if selected:
            self.edit_item_settings_requested.emit(selected[0])

    def _on_retry_failed(self) -> None:
        """Retry failed items."""
        selected = self._get_selected_item_ids()
        if selected:
            self.retry_item_requested.emit(selected[0])

    def _on_remove_selected(self) -> None:
        """Remove selected items."""
        selected = self._get_selected_item_ids()
        if selected:
            self.remove_items_requested.emit(selected)

    def _create_view_dialog(self) -> None:
        """Create View Dialog at initialization (like Single Task)."""
        from flowscribe.gui.dialogs import TranscriptionViewDialog

        self._view_dialog = TranscriptionViewDialog(
            self,
            transcript_path=None,  # No transcript initially
            run_output="",
            result=None,
            output_paths=None,
        )
        # Don't show it yet - user will click "Open View" to show it

    def _on_open_view(self) -> None:
        """Open view for selected queue item (using persistent dialog like Single Task)."""
        selected = self._get_selected_item_ids()
        if not selected:
            self._status_label.setText("Please select a queue item first")
            return

        if len(selected) > 1:
            self._status_label.setText("Please select only one item to open its view")
            return

        item_id = selected[0]
        item = self._items_cache.get(item_id)
        if not item:
            self._status_label.setText("Selected item not found in queue")
            return

        if item.status == "pending":
            self._status_label.setText("This item hasn't been transcribed yet. Start the queue to process it.")
            return

        if item.status == "failed":
            self._status_label.setText("This item failed to transcribe. Check error message or retry.")
            return

        # For running or completed items, use persistent dialog
        if self._view_dialog is None:
            self._create_view_dialog()

        # Clear previous content before loading new item
        self._view_dialog.clear_content()

        # Update dialog with current item's state
        if item.status == "running":
            if item_id != self._current_running_item_id:
                self._status_label.setText("Cannot open view: item status is inconsistent")
                return

            # Load live view with current run output
            self._view_dialog.update_run_output(self._current_run_output)
            self._status_label.setText(f"Opened live view for: {item.display_label}")

        elif item.status == "completed":
            if not item.transcript_path or not item.transcript_path.is_file():
                self._status_label.setText(
                    "Transcript file not found. The file may have been moved or deleted."
                )
                return

            # Load completed transcript with artifacts
            try:
                self._view_dialog._load_transcript(item.transcript_path)
                self._view_dialog.update_run_output(item.run_detail or "")
                self._status_label.setText(f"Opened view for: {item.display_label}")
            except Exception as e:
                self._status_label.setText(f"Error loading transcript: {e}")
                return

        else:
            self._status_label.setText(f"Cannot open view for item with status: {item.status}")
            return

        # Show the dialog
        self._view_dialog.show()
        self._view_dialog.raise_()
        self._view_dialog.activateWindow()

    def _on_clear_completed(self) -> None:
        """Clear completed items."""
        self.clear_completed_requested.emit()

    def _on_select_all(self) -> None:
        """Select all items."""
        for i in range(self._queue_list.count()):
            item = self._queue_list.item(i)
            if item:
                item.setCheckState(Qt.CheckState.Checked)

    def _on_rows_moved(self, parent, start: int, end: int, dest, row: int) -> None:
        """Handle drag-drop reordering."""
        self.reorder_requested.emit(self._collect_item_order())

    def _get_selected_item_ids(self) -> list[str]:
        """Get IDs of checked items."""
        selected = []
        for i in range(self._queue_list.count()):
            item = self._queue_list.item(i)
            if item and item.checkState() == Qt.CheckState.Checked:
                if i < len(self._item_ids):
                    selected.append(self._item_ids[i])
        return selected

    def _collect_item_order(self) -> list[str]:
        """Collect current item order."""
        order = []
        for i in range(self._queue_list.count()):
            if i < len(self._item_ids):
                order.append(self._item_ids[i])
        return order

    def _update_button_states(self) -> None:
        """Update button enabled states."""
        has_items = self._queue_list.count() > 0
        has_selection = len(self._get_selected_item_ids()) > 0

        self._start_queue_btn.setEnabled(has_items)
        self._edit_settings_btn.setEnabled(has_selection)
        self._retry_btn.setEnabled(has_selection)
        self._remove_btn.setEnabled(has_selection)
        self._clear_completed_btn.setEnabled(has_items)
        self._select_all_btn.setEnabled(has_items)

    def refresh_queue(self, items: list[QueueItem]) -> None:
        """Refresh queue display with current items."""
        self._queue_list.clear()
        self._item_ids.clear()
        self._items_cache.clear()

        for item in items:
            self._item_ids.append(item.item_id)
            self._items_cache[item.item_id] = item  # Cache item for later access
            display_text = self._format_item_display(item)
            list_item = QListWidgetItem(display_text)
            list_item.setFlags(
                list_item.flags() | Qt.ItemFlag.ItemIsUserCheckable
            )
            list_item.setCheckState(Qt.CheckState.Unchecked)
            self._queue_list.addItem(list_item)

        count = len(items)
        pending = sum(1 for item in items if item.status == "pending")
        running = sum(1 for item in items if item.status == "running")
        completed = sum(1 for item in items if item.status == "completed")
        failed = sum(1 for item in items if item.status == "failed")

        self._status_label.setText(
            f"Queue: {count} total | {pending} pending | {running} running | "
            f"{completed} completed | {failed} failed"
        )

        self._update_button_states()

    def _format_item_display(self, item: QueueItem) -> str:
        """Format queue item for display."""
        icon = _STATUS_ICONS.get(item.status, "[?]")
        if item.source.kind == "local":
            source_label = f"[FILE] {Path(item.source.value).name}"
        else:
            # Use display_label which prioritizes title over URL
            display_name = item.display_label
            # Truncate if too long
            if len(display_name) > 80:
                display_name = display_name[:77] + "..."
            source_label = f"[URL] {display_name}"

        return f"{icon} {source_label}"

    def set_server_status(self, running: bool, port: int | None = None) -> None:
        """Update server status display."""
        if running and port:
            self._server_status_label.setText(f"Server: Running on port {port}")
            self._server_status_label.setStyleSheet("color: green;")
            self._server_enabled_check.setChecked(True)
        else:
            self._server_status_label.setText("Server: Stopped")
            self._server_status_label.setStyleSheet("color: gray;")
            self._server_enabled_check.setChecked(False)

    def set_queue_running(self, running: bool) -> None:
        """Update queue running state."""
        self._start_queue_btn.setEnabled(not running)
        self._cancel_queue_btn.setEnabled(running)
        self._skip_current_btn.setEnabled(running)

    def on_item_started(self, item: QueueItem) -> None:
        """Handle item started event."""
        self._current_running_item_id = item.item_id
        self._current_run_output = ""
        self._status_label.setText(f"Processing: {item.display_label}")

    def on_item_progress(self, event) -> None:
        """Handle item progress event."""
        from flowscribe.app.models import ProgressEvent
        if isinstance(event, ProgressEvent) and event.message:
            self._current_run_output += event.message + "\n"
            # Update persistent view dialog if open
            if self._view_dialog is not None and self._view_dialog.isVisible():
                self._view_dialog.update_run_output(self._current_run_output)

        # Update View Dialog with progressive segments in real-time (like Single Task)
        if isinstance(event, ProgressEvent) and event.segments:
            if self._view_dialog is not None and self._view_dialog.isVisible():
                self._view_dialog.append_progress_segments(event)

    def on_item_completed(self, data: tuple) -> None:
        """Handle item completed event."""
        self._current_running_item_id = None
        self._current_run_output = ""

    def on_item_failed(self, data: tuple) -> None:
        """Handle item failed event."""
        self._current_running_item_id = None
        self._current_run_output = ""

    def on_item_canceled(self, item: QueueItem) -> None:
        """Handle item canceled event."""
        self._current_running_item_id = None
        self._current_run_output = ""
