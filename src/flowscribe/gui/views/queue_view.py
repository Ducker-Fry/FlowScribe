"""Queue view for batch transcription tasks."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from flowscribe.gui.remote_targets import inspect_remote_target
from flowscribe.gui.widgets import CollapsibleSection, RemoteExecutionWidget
from flowscribe.tasks.queue_models import QueueItem, QueueItemStatus

from .queue_view_controls import QueueViewControlsMixin
from .queue_view_dialog import QueueViewDialogMixin
from .queue_view_runtime import QueueViewRuntimeMixin
from .queue_view_selection import QueueViewSelectionMixin

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

        self._check_button = QPushButton("X")
        self._check_button.setProperty("queueCheck", True)
        self._check_button.setCheckable(True)
        self._check_button.setChecked(False)
        self._check_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
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
        retry_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        retry_button.clicked.connect(lambda: self.retry_requested.emit(self._item_id))
        retry_button.setVisible(item.status in {"failed", "canceled"})
        actions_column.addWidget(retry_button)

        remove_button = QPushButton("Remove")
        remove_button.setProperty("secondary", True)
        remove_button.setProperty("cardAction", True)
        remove_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        remove_button.clicked.connect(lambda: self.remove_requested.emit(self._item_id))
        actions_column.addWidget(remove_button)
        actions_column.addStretch()
        root_layout.addLayout(actions_column)

    def set_checked(self, checked: bool) -> None:
        self._check_button.blockSignals(True)
        self._check_button.setChecked(checked)
        self._check_button.blockSignals(False)

    def set_selected(self, selected: bool) -> None:
        self.setProperty("selected", selected)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def _on_checked_changed(self, checked: bool) -> None:
        self.checked_changed.emit(self._item_id, checked)

    @staticmethod
    def _primary_text(item: QueueItem) -> str:
        if item.source.kind == "local":
            return Path(item.source.value).name
        display_name = item.display_label
        return display_name[:87] + "..." if len(display_name) > 90 else display_name

    @staticmethod
    def _secondary_text(item: QueueItem) -> str:
        if item.source.kind == "local":
            return f"Local file - {Path(item.source.value)}"
        return f"URL - {item.source.value}"


class QueueListWidget(QListWidget):
    """List widget that avoids starting item drags from embedded action buttons."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._allow_drag_from_press = True

    def mousePressEvent(self, event) -> None:
        self._allow_drag_from_press = not _is_card_action_widget(self.viewport().childAt(event.pos()))
        super().mousePressEvent(event)

    def startDrag(self, supportedActions) -> None:
        if not self._allow_drag_from_press:
            return
        super().startDrag(supportedActions)


class QueueView(
    QWidget,
    QueueViewControlsMixin,
    QueueViewDialogMixin,
    QueueViewSelectionMixin,
    QueueViewRuntimeMixin,
):
    """View for managing batch transcription queue."""

    enqueue_urls_requested = Signal(str)
    enqueue_files_requested = Signal(list)
    import_file_requested = Signal(str)
    start_queue_requested = Signal()
    cancel_queue_requested = Signal()
    skip_current_requested = Signal()
    retry_item_requested = Signal(str)
    remove_items_requested = Signal(list)
    clear_completed_requested = Signal()
    reorder_requested = Signal(list)
    edit_item_settings_requested = Signal(list)
    execution_settings_changed = Signal(dict)
    server_start_requested = Signal(int)
    server_stop_requested = Signal()

    def __init__(self, settings: dict, parent: QWidgetType | None = None):
        super().__init__(parent)
        self._settings = settings
        self._loading_execution_settings = False
        self._item_ids: list[str] = []
        self._items_cache: dict[str, QueueItem] = {}
        self._checked_item_ids: set[str] = set()
        self._current_running_item_id: str | None = None
        self._current_run_output = ""
        self._view_dialog = None
        self._setup_ui()
        self._create_view_dialog()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

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

        self._remote_execution_widget = RemoteExecutionWidget(self)
        self._remote_execution_widget.settings_changed.connect(self._emit_execution_settings_changed)
        defaults_layout.addWidget(self._remote_execution_widget)
        self._execution_mode_combo = self._remote_execution_widget.execution_mode_combo
        self._server_target_combo = self._remote_execution_widget.server_target_combo
        self._remote_token_input = self._remote_execution_widget.remote_token_input
        self._remote_poll_seconds_spin = self._remote_execution_widget.remote_poll_seconds_spin
        self._download_artifacts_check = self._remote_execution_widget.download_artifacts_check
        self._resolved_target_label = self._remote_execution_widget.resolved_target_label
        self._manage_remote_servers_btn = self._remote_execution_widget.manage_remote_servers_button

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
        defaults_layout.addLayout(download_row)

        advanced_layout.addWidget(defaults_group)
        advanced_layout.addStretch()
        layout.addWidget(advanced_section)
        layout.addWidget(add_group, 2)

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
        self._queue_list = QueueListWidget()
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
        self._start_queue_btn = QPushButton("Start Queue")
        self._start_queue_btn.clicked.connect(self._on_start_queue)
        self._start_queue_btn.setProperty("primary", True)
        self._cancel_queue_btn = QPushButton("Cancel Queue")
        self._cancel_queue_btn.clicked.connect(self._on_cancel_queue)
        self._cancel_queue_btn.setProperty("secondary", True)
        self._skip_current_btn = QPushButton("Skip Current")
        self._skip_current_btn.clicked.connect(self._on_skip_current)
        self._skip_current_btn.setProperty("secondary", True)
        self._open_view_btn = QPushButton("Open View")
        self._open_view_btn.clicked.connect(self._on_open_view)
        self._open_view_btn.setProperty("secondary", True)
        self._edit_settings_btn = QPushButton("Edit Settings")
        self._edit_settings_btn.clicked.connect(self._on_edit_settings)
        self._retry_btn = QPushButton("Retry Failed")
        self._retry_btn.clicked.connect(self._on_retry_failed)
        self._remove_btn = QPushButton("Remove Selected")
        self._remove_btn.clicked.connect(self._on_remove_selected)
        self._clear_completed_btn = QPushButton("Clear Completed")
        self._clear_completed_btn.clicked.connect(self._on_clear_completed)
        self._select_all_btn = QPushButton("Select All")
        self._select_all_btn.clicked.connect(self._on_select_all)
        for button in (
            self._start_queue_btn,
            self._cancel_queue_btn,
            self._skip_current_btn,
            self._open_view_btn,
            self._edit_settings_btn,
            self._retry_btn,
            self._remove_btn,
            self._clear_completed_btn,
            self._select_all_btn,
        ):
            actions_layout.addWidget(button)

        queue_layout.addLayout(queue_content_layout, 1)
        queue_layout.addWidget(actions_group)
        self._status_label = QLabel("Queue is empty")
        queue_layout.addWidget(self._status_label)
        layout.addWidget(queue_group, 1)
        self._load_execution_settings(self._settings)
        self._update_button_states()

    def update_settings(self, settings: dict) -> None:
        self._settings = settings
        self._load_execution_settings(settings)

    def eventFilter(self, watched, event) -> bool:
        return QueueViewControlsMixin.eventFilter(self, watched, event)

    def get_execution_settings(self) -> dict:
        return self._remote_execution_widget.settings()

    def refresh_remote_server_profiles(self) -> None:
        self._remote_execution_widget.refresh_remote_server_targets()

    def _load_execution_settings(self, settings: dict) -> None:
        self._loading_execution_settings = True
        self._remote_execution_widget.load_settings(settings)
        self._loading_execution_settings = False

    def _emit_execution_settings_changed(self, *_args) -> None:
        if self._loading_execution_settings:
            return
        self.execution_settings_changed.emit(self.get_execution_settings())

    def validate_execution_settings(self) -> str | None:
        settings = self.get_execution_settings()
        if settings.get("execution_mode") != "remote":
            return None
        inspection = inspect_remote_target(settings.get("server_target"))
        return inspection.error


def _is_card_action_widget(widget: QObject | None) -> bool:
    current = widget
    while current is not None:
        property_getter = getattr(current, "property", None)
        if callable(property_getter):
            if bool(property_getter("cardAction")) or bool(property_getter("queueCheck")):
                return True
        current = current.parent()
    return False
