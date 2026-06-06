"""Library view for browsing transcription history."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from flowscribe.gui.icons import (
    get_check_icon,
    get_delete_icon,
    get_document_icon,
    get_folder_icon,
    get_link_icon,
    get_open_icon,
    get_refresh_icon,
    get_search_icon,
)
from flowscribe.gui.state_manager import transcript_library_store
from flowscribe.gui.theme_manager import get_current_theme
from flowscribe.gui.utils.formatting import _format_library_datetime
from flowscribe.gui.utils.library import _library_entry_missing_summary, _library_results_summary
from flowscribe.library import (
    LibraryOutputRecord,
    TranscriptLibraryEntry,
    TranscriptLibraryStore,
    filter_transcript_library_entries,
    sort_transcript_library_entries,
)

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget as QWidgetType


class LibraryEntryCard(QWidget):
    """Compact visual card for one library entry."""

    def __init__(self, entry: TranscriptLibraryEntry, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("card", True)
        self.setProperty("selected", False)

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 8)
        root.setSpacing(6)

        header = QHBoxLayout()
        title = QLabel(entry.display_label)
        title.setWordWrap(True)
        title.setStyleSheet("font-weight: 600;")
        header.addWidget(title, 1)

        status = QLabel("Missing" if entry.missing else "Ready")
        status.setStyleSheet(
            "background-color: #EF4444; color: white; border-radius: 8px; padding: 2px 7px;"
            if entry.missing
            else "background-color: #10B981; color: white; border-radius: 8px; padding: 2px 7px;"
        )
        header.addWidget(status, 0, Qt.AlignmentFlag.AlignTop)
        root.addLayout(header)

        meta = QLabel(
            f"{entry.source_kind} | Created {_format_library_datetime(entry.created_at)} | "
            f"Opened {_format_library_datetime(entry.last_opened_at)}"
        )
        meta.setWordWrap(True)
        meta.setStyleSheet("color: #6B7280; font-size: 11px;")
        root.addWidget(meta)

        formats = ", ".join(_output_format_labels(entry.outputs)) or "no artifacts indexed"
        output = QLabel(f"Artifacts: {formats}")
        output.setWordWrap(True)
        output.setStyleSheet("color: #6B7280; font-size: 11px;")
        root.addWidget(output)

    def set_selected(self, selected: bool) -> None:
        self.setProperty("selected", selected)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()


class LibraryView(QWidget):
    """View for browsing and managing transcription library."""

    transcript_open_requested = Signal(object)
    output_dir_open_requested = Signal(object)
    output_dirs_open_requested = Signal(list)
    media_rebind_requested = Signal(object)
    entry_remove_requested = Signal(object)
    entries_remove_requested = Signal(list)
    artifact_open_requested = Signal(object)
    missing_cleanup_requested = Signal()

    def __init__(
        self,
        parent: QWidgetType | None = None,
        *,
        library_store: TranscriptLibraryStore | None = None,
    ):
        super().__init__(parent)
        self._library_store: TranscriptLibraryStore = library_store or transcript_library_store()
        self._entries_cache: tuple[TranscriptLibraryEntry, ...] = ()
        self._setup_ui()
        self.refresh_library()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        app = QApplication.instance()
        theme = get_current_theme(app) if app else "light"

        header = QHBoxLayout()
        header_label = QLabel("Transcript Library")
        header_label.setStyleSheet("font-size: 14pt; font-weight: bold;")
        header.addWidget(header_label)
        header.addStretch(1)
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Search name, path, or output directory")
        self._search_input.textChanged.connect(self.refresh_library)
        header.addWidget(self._search_input, 1)
        self._search_btn = QPushButton(get_search_icon(theme), "Search")
        self._search_btn.clicked.connect(self.refresh_library)
        header.addWidget(self._search_btn)
        layout.addLayout(header)

        filters_row = QHBoxLayout()
        filters_row.addWidget(QLabel("Source:"))
        self._source_filter_combo = QComboBox()
        for label, data in (
            ("All", "all"),
            ("Local", "local"),
            ("URL", "url"),
            ("Capture", "capture"),
            ("Unknown", "unknown"),
        ):
            self._source_filter_combo.addItem(label, data)
        self._source_filter_combo.currentIndexChanged.connect(self.refresh_library)
        filters_row.addWidget(self._source_filter_combo)

        filters_row.addWidget(QLabel("Status:"))
        self._missing_filter_combo = QComboBox()
        self._missing_filter_combo.addItem("All", "all")
        self._missing_filter_combo.addItem("Available", "available_only")
        self._missing_filter_combo.addItem("Missing", "missing_only")
        self._missing_filter_combo.currentIndexChanged.connect(self.refresh_library)
        filters_row.addWidget(self._missing_filter_combo)

        filters_row.addWidget(QLabel("Opened:"))
        self._opened_filter_combo = QComboBox()
        self._opened_filter_combo.addItem("All", "all")
        self._opened_filter_combo.addItem("Opened", "opened")
        self._opened_filter_combo.addItem("Not Opened", "never_opened")
        self._opened_filter_combo.currentIndexChanged.connect(self.refresh_library)
        filters_row.addWidget(self._opened_filter_combo)

        filters_row.addWidget(QLabel("Sort:"))
        self._sort_combo = QComboBox()
        self._sort_combo.addItem("Last Opened", "last_opened")
        self._sort_combo.addItem("Created", "created")
        self._sort_combo.addItem("Name", "label")
        self._sort_combo.currentIndexChanged.connect(self.refresh_library)
        filters_row.addWidget(self._sort_combo)

        self._sort_direction_combo = QComboBox()
        self._sort_direction_combo.addItem("Newest first", "desc")
        self._sort_direction_combo.addItem("Oldest first", "asc")
        self._sort_direction_combo.currentIndexChanged.connect(self.refresh_library)
        filters_row.addWidget(self._sort_direction_combo)
        filters_row.addStretch()
        layout.addLayout(filters_row)

        self._summary_label = QLabel("No transcripts in library")
        self._summary_label.setWordWrap(True)
        layout.addWidget(self._summary_label)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        self._entries_list = QListWidget()
        self._entries_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self._entries_list.itemActivated.connect(self._on_item_activated)
        self._entries_list.itemSelectionChanged.connect(self._on_selection_changed)
        splitter.addWidget(self._entries_list)

        detail = QGroupBox("Details")
        detail_layout = QVBoxLayout(detail)
        detail_layout.setSpacing(8)
        self._detail_title = QLabel("Select a transcript")
        self._detail_title.setWordWrap(True)
        self._detail_title.setStyleSheet("font-weight: 600;")
        detail_layout.addWidget(self._detail_title)

        self._detail_grid = QGridLayout()
        self._detail_grid.setColumnStretch(1, 1)
        self._path_value = _detail_value_label()
        self._output_dir_value = _detail_value_label()
        self._source_media_value = _detail_value_label()
        self._bound_media_value = _detail_value_label()
        self._missing_value = _detail_value_label()
        for row, (label, widget) in enumerate(
            (
                ("Transcript", self._path_value),
                ("Output dir", self._output_dir_value),
                ("Source media", self._source_media_value),
                ("Bound media", self._bound_media_value),
                ("Missing", self._missing_value),
            )
        ):
            self._detail_grid.addWidget(QLabel(label), row, 0, Qt.AlignmentFlag.AlignTop)
            self._detail_grid.addWidget(widget, row, 1)
        detail_layout.addLayout(self._detail_grid)

        detail_layout.addWidget(QLabel("Artifacts"))
        self._outputs_list = QListWidget()
        self._outputs_list.itemActivated.connect(self._on_open_selected_artifact)
        detail_layout.addWidget(self._outputs_list, 1)

        detail_actions = QHBoxLayout()
        self._detail_open_btn = QPushButton(get_document_icon(theme), "Open")
        self._detail_open_btn.clicked.connect(self._on_open_transcript)
        self._detail_dir_btn = QPushButton(get_folder_icon(theme), "Output Dir")
        self._detail_dir_btn.clicked.connect(self._on_open_output_dir)
        self._detail_copy_path_btn = QPushButton("Copy Path")
        self._detail_copy_path_btn.clicked.connect(self._on_copy_transcript_path)
        self._detail_rebind_btn = QPushButton(get_link_icon(theme), "Rebind")
        self._detail_rebind_btn.clicked.connect(self._on_rebind_media)
        self._artifact_open_btn = QPushButton(get_open_icon(theme), "Open Artifact")
        self._artifact_open_btn.clicked.connect(self._on_open_selected_artifact)
        self._artifact_copy_btn = QPushButton("Copy Artifact Path")
        self._artifact_copy_btn.clicked.connect(self._on_copy_selected_artifact_path)
        for button in (
            self._detail_open_btn,
            self._detail_dir_btn,
            self._detail_copy_path_btn,
            self._detail_rebind_btn,
            self._artifact_open_btn,
            self._artifact_copy_btn,
        ):
            detail_actions.addWidget(button)
        detail_actions.addStretch(1)
        detail_layout.addLayout(detail_actions)
        splitter.addWidget(detail)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter, 1)

        actions_row = QHBoxLayout()
        self._select_all_btn = QPushButton(get_check_icon(theme), "Select All")
        self._select_all_btn.clicked.connect(self._on_select_all)
        actions_row.addWidget(self._select_all_btn)
        self._open_btn = QPushButton(get_document_icon(theme), "Open Transcript")
        self._open_btn.clicked.connect(self._on_open_transcript)
        actions_row.addWidget(self._open_btn)
        self._open_dir_btn = QPushButton(get_folder_icon(theme), "Open Output Directory")
        self._open_dir_btn.clicked.connect(self._on_open_output_dir)
        actions_row.addWidget(self._open_dir_btn)
        self._rebind_btn = QPushButton(get_link_icon(theme), "Bind/Rebind Media")
        self._rebind_btn.clicked.connect(self._on_rebind_media)
        actions_row.addWidget(self._rebind_btn)
        self._remove_btn = QPushButton(get_delete_icon(theme), "Remove from Library")
        self._remove_btn.clicked.connect(self._on_remove_entry)
        actions_row.addWidget(self._remove_btn)
        self._cleanup_btn = QPushButton(get_refresh_icon(theme), "Clean Missing Entries")
        self._cleanup_btn.clicked.connect(self._on_cleanup_missing)
        actions_row.addWidget(self._cleanup_btn)
        actions_row.addStretch()
        layout.addLayout(actions_row)

        self._status_label = QLabel("Ready")
        layout.addWidget(self._status_label)
        self._refresh_detail_panel()

    def refresh_library(self) -> None:
        all_entries = self._library_store.list_entries()
        query = self._search_input.text().strip()

        entries = sort_transcript_library_entries(
            filter_transcript_library_entries(
                _filter_entries_by_query(all_entries, query),
                source_kind=self._source_filter_combo.currentData(),
                missing_filter=self._missing_filter_combo.currentData(),
                opened_filter=self._opened_filter_combo.currentData(),
            ),
            sort_mode=self._sort_combo.currentData(),
            descending=self._sort_direction_combo.currentData() != "asc",
        )
        self._entries_cache = entries

        summary = _library_results_summary(entries, total_count=len(all_entries))
        if query:
            summary += f" | search: {query}"
        if any(entry.missing for entry in all_entries):
            summary += " | Use Clean Missing Entries to drop broken records."
        self._summary_label.setText(summary)

        selected_ids = {entry.entry_id for entry in self._selected_entries()}
        self._entries_list.clear()
        for entry in entries:
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, entry.entry_id)
            item.setToolTip(str(entry.transcript_path))
            self._entries_list.addItem(item)
            card = LibraryEntryCard(entry, self._entries_list)
            item.setSizeHint(card.sizeHint())
            self._entries_list.setItemWidget(item, card)
            if entry.entry_id in selected_ids:
                item.setSelected(True)

        self._status_label.setText(f"Showing {len(entries)} of {len(all_entries)} transcripts")
        self._on_selection_changed()

    def _selected_entries(self) -> list[TranscriptLibraryEntry]:
        by_id = {entry.entry_id: entry for entry in self._entries_cache}
        result: list[TranscriptLibraryEntry] = []
        for item in self._entries_list.selectedItems():
            entry = by_id.get(str(item.data(Qt.ItemDataRole.UserRole)))
            if entry is not None:
                result.append(entry)
        if not result:
            row = self._entries_list.currentRow()
            if 0 <= row < len(self._entries_cache):
                result.append(self._entries_cache[row])
        return result

    def _get_selected_entry(self) -> TranscriptLibraryEntry | None:
        entries = self._selected_entries()
        return entries[0] if len(entries) == 1 else None

    def _on_selection_changed(self) -> None:
        selected_rows = {index.row() for index in self._entries_list.selectedIndexes()}
        for row in range(self._entries_list.count()):
            item = self._entries_list.item(row)
            card = self._entries_list.itemWidget(item) if item is not None else None
            if isinstance(card, LibraryEntryCard):
                card.set_selected(row in selected_rows)
        self._refresh_detail_panel()

    def _refresh_detail_panel(self) -> None:
        entries = self._selected_entries()
        single = entries[0] if len(entries) == 1 else None
        multi = len(entries) > 1

        self._outputs_list.clear()
        if single is None:
            self._detail_title.setText(f"{len(entries)} selected" if multi else "Select a transcript")
            self._path_value.setText("Multiple records selected" if multi else "-")
            self._output_dir_value.setText("Use batch actions below" if multi else "-")
            self._source_media_value.setText("-")
            self._bound_media_value.setText("-")
            self._missing_value.setText("-")
            self._set_single_entry_actions_enabled(False)
            self._open_dir_btn.setEnabled(bool(entries))
            self._remove_btn.setEnabled(bool(entries))
            return

        self._detail_title.setText(single.display_label)
        self._path_value.setText(str(single.transcript_path))
        self._output_dir_value.setText(str(single.output_dir))
        self._source_media_value.setText(str(single.source_media_path) if single.source_media_path else "None")
        self._bound_media_value.setText(
            str(single.media_binding.media_path) if single.media_binding else "None"
        )
        self._missing_value.setText(_library_entry_missing_summary(single))
        for output in single.outputs:
            item = QListWidgetItem(f"{output.kind.upper()} | {output.path.name}")
            item.setData(Qt.ItemDataRole.UserRole, output.path)
            item.setToolTip(str(output.path))
            self._outputs_list.addItem(item)
        self._set_single_entry_actions_enabled(True)
        self._open_dir_btn.setEnabled(True)
        self._remove_btn.setEnabled(True)

    def _set_single_entry_actions_enabled(self, enabled: bool) -> None:
        for button in (
            self._open_btn,
            self._rebind_btn,
            self._detail_open_btn,
            self._detail_copy_path_btn,
            self._detail_rebind_btn,
            self._artifact_open_btn,
            self._artifact_copy_btn,
        ):
            button.setEnabled(enabled)
        self._detail_dir_btn.setEnabled(enabled)

    def _on_item_activated(self, _item) -> None:
        self._on_open_transcript()

    def _on_open_transcript(self) -> None:
        entry = self._get_selected_entry()
        if entry is None:
            self._status_label.setText("Select one transcript first")
            return
        if not entry.transcript_path.is_file():
            self._status_label.setText(f"Transcript is missing: {entry.transcript_path}")
            return
        self.transcript_open_requested.emit(entry)

    def _on_open_output_dir(self) -> None:
        entries = self._selected_entries()
        if not entries:
            self._status_label.setText("Select at least one transcript first")
            return
        if len(entries) == 1:
            self.output_dir_open_requested.emit(entries[0])
            return
        self.output_dirs_open_requested.emit(entries)

    def _on_rebind_media(self) -> None:
        entry = self._get_selected_entry()
        if entry is None:
            self._status_label.setText("Select one transcript first")
            return
        if not entry.transcript_path.is_file():
            self._status_label.setText(f"Transcript is missing: {entry.transcript_path}")
            return
        self.media_rebind_requested.emit(entry)

    def _on_remove_entry(self) -> None:
        entries = self._selected_entries()
        if not entries:
            self._status_label.setText("Select at least one transcript first")
            return
        if len(entries) == 1:
            self.entry_remove_requested.emit(entries[0])
            return
        self.entries_remove_requested.emit(entries)

    def _on_cleanup_missing(self) -> None:
        missing_count = sum(1 for entry in self._library_store.list_entries() if entry.missing)
        if missing_count == 0:
            self._status_label.setText("No missing entries to clean up")
            return
        self.missing_cleanup_requested.emit()

    def _on_select_all(self) -> None:
        self._entries_list.selectAll()

    def _on_copy_transcript_path(self) -> None:
        entry = self._get_selected_entry()
        if entry is None:
            return
        QApplication.clipboard().setText(str(entry.transcript_path))
        self._status_label.setText("Copied transcript path")

    def _selected_output_record(self) -> LibraryOutputRecord | None:
        entry = self._get_selected_entry()
        row = self._outputs_list.currentRow()
        if entry is None or row < 0 or row >= len(entry.outputs):
            return None
        return entry.outputs[row]

    def _on_open_selected_artifact(self) -> None:
        record = self._selected_output_record()
        if record is None:
            self._status_label.setText("Select an artifact first")
            return
        self.artifact_open_requested.emit(record.path)

    def _on_copy_selected_artifact_path(self) -> None:
        record = self._selected_output_record()
        if record is None:
            self._status_label.setText("Select an artifact first")
            return
        QApplication.clipboard().setText(str(record.path))
        self._status_label.setText("Copied artifact path")


def _detail_value_label() -> QLabel:
    label = QLabel("-")
    label.setWordWrap(True)
    label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    return label


def _output_format_labels(outputs: tuple[LibraryOutputRecord, ...]) -> tuple[str, ...]:
    seen: list[str] = []
    for output in outputs:
        label = output.kind.upper()
        if label not in seen:
            seen.append(label)
    return tuple(seen)


def _filter_entries_by_query(
    entries: tuple[TranscriptLibraryEntry, ...], query: str
) -> tuple[TranscriptLibraryEntry, ...]:
    text = query.casefold()
    if not text:
        return entries
    return tuple(entry for entry in entries if _entry_matches_query(entry, text))


def _entry_matches_query(entry: TranscriptLibraryEntry, query: str) -> bool:
    haystacks = (
        entry.display_label,
        entry.transcript_path.name,
        str(entry.transcript_path),
        str(entry.output_dir),
    )
    return any(query in value.casefold() for value in haystacks)
