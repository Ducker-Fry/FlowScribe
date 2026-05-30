"""Queue view for batch transcription tasks."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QEvent, Qt, Signal
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
from flowscribe.gui.widgets import CollapsibleSection

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget as QWidgetType


_STATUS_ICONS: dict[QueueItemStatus, str] = {
    "pending": "[...]",
    "running": "[>>>]",
    "completed": "[OK]",
    "failed": "[ERR]",
    "canceled": "[---]",
}

_STATUS_COLORS: dict[QueueItemStatus, str] = {
    "pending": "#6B7280",
    "running": "#2563EB",
    "completed": "#10B981",
    "failed": "#EF4444",
    "canceled": "#F59E0B",
}

_STATUS_LABELS: dict[QueueItemStatus, str] = {
    "pending": "Pending",
    "running": "Running",
    "completed": "Completed",
    "failed": "Failed",
    "canceled": "Canceled",
}


class QueueItemCard(QWidget):
    """Compact card widget used as the visual representation of a queue item."""

    retry_requested = Signal(str)
    remove_requested = Signal(str)
    checked_changed = Signal(str, bool)

    def __init__(self, item: QueueItem, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._item_id = item.item_id
        self.setProperty("card", True)
        self.setProperty("selected", False)

        root_layout = QHBoxLayout(self)
        root_layout.setContentsMargins(10, 10, 10, 10)
        root_layout.setSpacing(10)

        self._check_button = QPushButton("✓")
        self._check_button.setProperty("queueCheck", True)
        self._check_button.setCheckable(True)
        self._check_button.setChecked(False)
        self._check_button.clicked.connect(self._on_checked_changed)
        root_layout.addWidget(self._check_button, 0, Qt.AlignmentFlag.AlignTop)

        status_label = QLabel(_STATUS_LABELS.get(item.status, "Unknown"))
        status_color = _STATUS_COLORS.get(item.status, "#6B7280")
        status_label.setStyleSheet(
            f"background-color: {status_color}; color: white; border-radius: 10px; "
            "padding: 2px 8px; font-size: 11px; font-weight: 600;"
        )
        root_layout.addWidget(status_label, 0, Qt.AlignmentFlag.AlignTop)

        text_column = QVBoxLayout()
        text_column.setContentsMargins(0, 0, 0, 0)
        text_column.setSpacing(4)

        title_label = QLabel(self._primary_text(item))
        title_label.setWordWrap(True)
        title_label.setStyleSheet("font-weight: 600;")
        text_column.addWidget(title_label)

        detail_label = QLabel(self._secondary_text(item))
        detail_label.setWordWrap(True)
        detail_label.setStyleSheet("color: #6B7280; font-size: 11px;")
        text_column.addWidget(detail_label)

        if item.error_message and item.status == "failed":
            error_label = QLabel(item.error_message[:120])
            error_label.setWordWrap(True)
            error_label.setStyleSheet("color: #EF4444; font-size: 11px;")
            text_column.addWidget(error_label)
        elif item.status == "running":
            running_label = QLabel(f"Attempt {item.attempt_count + 1} in progress")
            running_label.setStyleSheet("color: #2563EB; font-size: 11px;")
            text_column.addWidget(running_label)

        root_layout.addLayout(text_column, 1)

        actions_column = QVBoxLayout()
        actions_column.setContentsMargins(0, 0, 0, 0)
        actions_column.setSpacing(6)

        retry_button = QPushButton("Retry")
        retry_button.setProperty("secondary", True)
        retry_button.setProperty("cardAction", True)
        retry_button.clicked.connect(lambda: self.retry_requested.emit(self._item_id))
        retry_button.setVisible(item.status in {"failed", "canceled"})
        actions_column.addWidget(retry_button)

        remove_button = QPushButton("Remove")
        remove_button.setProperty("secondary", True)
        remove_button.setProperty("cardAction", True)
        remove_button.clicked.connect(lambda: self.remove_requested.emit(self._item_id))
        actions_column.addWidget(remove_button)
        actions_column.addStretch()

        root_layout.addLayout(actions_column)

    def set_checked(self, checked: bool) -> None:
        """Synchronize checkbox state without relying on list item painting."""
        self._check_button.blockSignals(True)
        self._check_button.setChecked(checked)
        self._check_button.blockSignals(False)

    def set_selected(self, selected: bool) -> None:
        """Update visual selection state for the card."""
        self.setProperty("selected", selected)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def _on_checked_changed(self, checked: bool) -> None:
        """Propagate card checkbox changes back to the queue view."""
        self.checked_changed.emit(self._item_id, checked)

    @staticmethod
    def _primary_text(item: QueueItem) -> str:
        if item.source.kind == "local":
            return Path(item.source.value).name
        display_name = item.display_label
        if len(display_name) > 90:
            return display_name[:87] + "..."
        return display_name

    @staticmethod
    def _secondary_text(item: QueueItem) -> str:
        if item.source.kind == "local":
            return f"Local file - {Path(item.source.value)}"
        return f"URL - {item.source.value}"


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
    edit_item_settings_requested = Signal(list)  # list[str] - item_ids
    server_start_requested = Signal(int)  # port
    server_stop_requested = Signal()

    def __init__(self, settings: dict, parent: QWidgetType | None = None):
        super().__init__(parent)
        self._settings = settings
        self._item_ids: list[str] = []
        self._items_cache: dict[str, QueueItem] = {}
        self._checked_item_ids: set[str] = set()
        self._current_running_item_id: str | None = None
        self._current_run_output: str = ""
        self._view_dialog = None  # Persistent dialog like Single Task
        self._setup_ui()
        self._create_view_dialog()  # Create dialog at initialization

    def _setup_ui(self) -> None:
        """Initialize UI components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        # Bookmarklet Server section
        advanced_section = CollapsibleSection("Advanced Settings", expanded=False)
        advanced_layout = advanced_section.content_layout
        advanced_layout.setSpacing(8)

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
        self._server_port_spin.setFixedWidth(118)
        server_control_row.addWidget(self._server_port_spin)

        self._server_status_label = QLabel("Server: Stopped")
        self._server_status_label.setStyleSheet("color: gray;")
        server_control_row.addWidget(self._server_status_label)
        server_control_row.addStretch()

        server_info = QLabel(
            "Enable server to add URLs from browser. "
            "Visit http://127.0.0.1:8765/bookmarklet.js for installation."
        )
        server_info.setWordWrap(True)
        server_info.setStyleSheet("color: gray; font-size: 10px;")
        server_info.setProperty("compactNote", True)
        advanced_layout.addLayout(server_control_row)
        advanced_layout.addWidget(server_info)

        # Add sources section
        add_group = QGroupBox("Add Sources")
        add_layout = QVBoxLayout(add_group)
        add_layout.setSpacing(10)

        self._add_files_btn = QPushButton("Add Local Files...")
        self._add_files_btn.clicked.connect(self._on_add_local_files)
        self._add_files_btn.setProperty("primary", True)
        add_layout.addWidget(self._add_files_btn)

        self._url_input = QTextEdit()
        self._url_input.setPlaceholderText(
            "https://example.com/video1\nhttps://example.com/video2\n...\n(Ctrl+Enter to add)"
        )
        self._url_input.setMaximumHeight(128)
        self._url_input.installEventFilter(self)
        add_layout.addWidget(self._url_input)

        url_actions = QHBoxLayout()
        url_actions.setSpacing(8)
        self._add_urls_btn = QPushButton("Add URLs")
        self._add_urls_btn.clicked.connect(self._on_add_urls)
        self._add_urls_btn.setProperty("primary", True)
        self._import_file_btn = QPushButton("Import from File...")
        self._import_file_btn.clicked.connect(self._on_import_file)
        self._import_file_btn.setProperty("secondary", True)
        url_actions.addWidget(self._add_urls_btn)
        url_actions.addWidget(self._import_file_btn)
        url_actions.addStretch()
        add_layout.addLayout(url_actions)

        # Default settings for new items
        defaults_group = QGroupBox("Default Settings for New Items")
        defaults_layout = QVBoxLayout(defaults_group)
        defaults_layout.setSpacing(8)

        settings_row = QHBoxLayout()
        settings_row.addWidget(QLabel("Max Retries:"))
        self._max_retries_spin = QSpinBox()
        self._max_retries_spin.setRange(0, 10)
        self._max_retries_spin.setValue(2)
        self._max_retries_spin.setFixedWidth(92)
        settings_row.addWidget(self._max_retries_spin)
        settings_row.addStretch()
        defaults_layout.addLayout(settings_row)

        download_row = QHBoxLayout()
        download_row.setSpacing(8)

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
        defaults_layout.addLayout(download_row)

        advanced_layout.addWidget(defaults_group)
        advanced_layout.addStretch()
        layout.addWidget(advanced_section)
        layout.addWidget(add_group, 2)

        # Queue section
        queue_group = QGroupBox("Queue")
        queue_layout = QVBoxLayout(queue_group)
        queue_layout.setSpacing(8)

        queue_header = QHBoxLayout()
        self._queue_summary_label = QLabel("0 total | 0 pending | 0 running | 0 completed | 0 failed")
        self._queue_summary_label.setStyleSheet("color: gray;")
        queue_header.addWidget(self._queue_summary_label)
        queue_header.addStretch()
        queue_layout.addLayout(queue_header)

        queue_content_layout = QHBoxLayout()
        queue_content_layout.setSpacing(10)
        self._queue_list = QListWidget()
        self._queue_list.setProperty("cardList", True)
        self._queue_list.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self._queue_list.setDefaultDropAction(Qt.DropAction.MoveAction)
        self._queue_list.setAlternatingRowColors(True)
        self._queue_list.setSpacing(2)
        self._queue_list.setMinimumHeight(260)
        self._queue_list.model().rowsMoved.connect(self._on_rows_moved)
        self._queue_list.itemSelectionChanged.connect(self._update_button_states)
        self._queue_list.itemSelectionChanged.connect(self._sync_card_selection_states)
        self._queue_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        queue_content_layout.addWidget(self._queue_list, 1)

        actions_group = QGroupBox("Actions")
        actions_layout = QHBoxLayout(actions_group)
        actions_layout.setSpacing(8)

        self._start_queue_btn = QPushButton("Start Queue")
        self._start_queue_btn.clicked.connect(self._on_start_queue)
        self._start_queue_btn.setProperty("primary", True)
        actions_layout.addWidget(self._start_queue_btn)

        self._cancel_queue_btn = QPushButton("Cancel Queue")
        self._cancel_queue_btn.clicked.connect(self._on_cancel_queue)
        self._cancel_queue_btn.setEnabled(False)
        self._cancel_queue_btn.setProperty("secondary", True)
        actions_layout.addWidget(self._cancel_queue_btn)

        self._skip_current_btn = QPushButton("Skip Current")
        self._skip_current_btn.clicked.connect(self._on_skip_current)
        self._skip_current_btn.setEnabled(False)
        self._skip_current_btn.setProperty("secondary", True)
        actions_layout.addWidget(self._skip_current_btn)

        self._open_view_btn = QPushButton("Open View")
        self._open_view_btn.clicked.connect(self._on_open_view)
        self._open_view_btn.setProperty("secondary", True)
        actions_layout.addWidget(self._open_view_btn)

        self._edit_settings_btn = QPushButton("Edit Settings")
        self._edit_settings_btn.clicked.connect(self._on_edit_settings)
        actions_layout.addWidget(self._edit_settings_btn)

        self._retry_btn = QPushButton("Retry Failed")
        self._retry_btn.clicked.connect(self._on_retry_failed)
        actions_layout.addWidget(self._retry_btn)

        self._remove_btn = QPushButton("Remove Selected")
        self._remove_btn.clicked.connect(self._on_remove_selected)
        actions_layout.addWidget(self._remove_btn)

        self._clear_completed_btn = QPushButton("Clear Completed")
        self._clear_completed_btn.clicked.connect(self._on_clear_completed)
        actions_layout.addWidget(self._clear_completed_btn)

        self._select_all_btn = QPushButton("Select All")
        self._select_all_btn.clicked.connect(self._on_select_all)
        actions_layout.addWidget(self._select_all_btn)

        queue_layout.addLayout(queue_content_layout, 1)
        queue_layout.addWidget(actions_group)

        # Status label
        self._status_label = QLabel("Queue is empty")
        queue_layout.addWidget(self._status_label)

        layout.addWidget(queue_group, 1)

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
        if not text:
            self._status_label.setText("Please enter at least one URL")
            return
        self.enqueue_urls_requested.emit(text)
        self._url_input.clear()
        self._status_label.setText("Processing URLs...")

    def eventFilter(self, watched, event) -> bool:
        if watched is self._url_input and event.type() == QEvent.Type.KeyPress:
            # Ctrl+Enter or Ctrl+Return to submit
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                    self._on_add_urls()
                    return True
        return super().eventFilter(watched, event)

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
        """Edit settings for selected items (supports batch editing)."""
        selected = self._get_selected_item_ids()
        if selected:
            self.edit_item_settings_requested.emit(selected)

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

    def _on_retry_single_item(self, item_id: str) -> None:
        """Retry a single item from its card action."""
        self.retry_item_requested.emit(item_id)

    def _on_remove_single_item(self, item_id: str) -> None:
        """Remove a single item from its card action."""
        self.remove_items_requested.emit([item_id])

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
        self._checked_item_ids = set(self._item_ids)
        self._sync_all_card_check_states()
        self._update_button_states()

    def _on_rows_moved(self, parent, start: int, end: int, dest, row: int) -> None:
        """Handle drag-drop reordering."""
        self.reorder_requested.emit(self._collect_item_order())

    def _get_selected_item_ids(self) -> list[str]:
        """Get IDs of checked items."""
        selected: list[str] = []
        selected_rows = {index.row() for index in self._queue_list.selectedIndexes()}
        for i in range(self._queue_list.count()):
            if i < len(self._item_ids):
                item_id = self._item_ids[i]
                if item_id in self._checked_item_ids or i in selected_rows:
                    selected.append(item_id)
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

    def _sync_all_card_check_states(self) -> None:
        """Refresh all visible card checkboxes from the checked item set."""
        for row, item_id in enumerate(self._item_ids):
            list_item = self._queue_list.item(row)
            if list_item is None:
                continue

            card = self._queue_list.itemWidget(list_item)
            if isinstance(card, QueueItemCard):
                card.set_checked(item_id in self._checked_item_ids)

    def _sync_card_selection_states(self) -> None:
        """Refresh card selection styling from the current list selection."""
        selected_rows = {index.row() for index in self._queue_list.selectedIndexes()}
        for row in range(self._queue_list.count()):
            list_item = self._queue_list.item(row)
            if list_item is None:
                continue

            card = self._queue_list.itemWidget(list_item)
            if isinstance(card, QueueItemCard):
                card.set_selected(row in selected_rows)

    def refresh_queue(self, items: list[QueueItem]) -> None:
        """Refresh queue display with current items."""
        self._queue_list.clear()
        self._item_ids.clear()
        self._items_cache.clear()
        self._checked_item_ids.clear()

        for item in items:
            self._item_ids.append(item.item_id)
            self._items_cache[item.item_id] = item  # Cache item for later access
            display_text = self._format_item_display(item)
            list_item = QListWidgetItem()
            list_item.setToolTip(display_text)
            self._queue_list.addItem(list_item)
            card = QueueItemCard(item, self._queue_list)
            card.set_checked(False)
            card.checked_changed.connect(self._on_card_checked_changed)
            card.retry_requested.connect(self._on_retry_single_item)
            card.remove_requested.connect(self._on_remove_single_item)
            list_item.setSizeHint(card.sizeHint())
            self._queue_list.setItemWidget(list_item, card)

        count = len(items)
        pending = sum(1 for item in items if item.status == "pending")
        running = sum(1 for item in items if item.status == "running")
        completed = sum(1 for item in items if item.status == "completed")
        failed = sum(1 for item in items if item.status == "failed")

        summary_text = (
            f"{count} total | {pending} pending | {running} running | "
            f"{completed} completed | {failed} failed"
        )
        self._queue_summary_label.setText(summary_text)
        self._status_label.setText("Queue is empty" if count == 0 else "Select items to manage the queue")

        self._sync_card_selection_states()
        self._update_button_states()

    def _on_card_checked_changed(self, item_id: str, checked: bool) -> None:
        """Track card checkbox changes using an explicit checked item set."""
        if checked:
            self._checked_item_ids.add(item_id)
        else:
            self._checked_item_ids.discard(item_id)
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
