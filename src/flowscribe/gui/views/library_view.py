"""Library view for browsing transcription history."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from flowscribe.gui.icons import (
    get_check_icon,
    get_delete_icon,
    get_document_icon,
    get_folder_icon,
    get_link_icon,
    get_refresh_icon,
)
from flowscribe.gui.state_manager import transcript_library_store
from flowscribe.gui.theme_manager import get_current_theme
from flowscribe.gui.utils.library import _library_entry_list_label, _library_results_summary
from flowscribe.library import (
    TranscriptLibraryEntry,
    TranscriptLibraryStore,
    filter_transcript_library_entries,
    sort_transcript_library_entries,
)

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget as QWidgetType


class LibraryView(QWidget):
    """View for browsing and managing transcription library."""

    # Signals
    transcript_open_requested = Signal(object)  # TranscriptLibraryEntry
    output_dir_open_requested = Signal(object)  # TranscriptLibraryEntry
    media_rebind_requested = Signal(object)  # TranscriptLibraryEntry
    entry_remove_requested = Signal(object)  # TranscriptLibraryEntry
    missing_cleanup_requested = Signal()

    def __init__(self, parent: QWidgetType | None = None):
        super().__init__(parent)
        self._library_store: TranscriptLibraryStore = transcript_library_store()
        self._entries_cache: tuple[TranscriptLibraryEntry, ...] = ()
        self._setup_ui()
        self.refresh_library()

    def _setup_ui(self) -> None:
        """Initialize UI components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Get current theme for icons
        app = QApplication.instance()
        theme = get_current_theme(app) if app else "light"

        # Header
        header_label = QLabel("Transcript Library")
        header_label.setStyleSheet("font-size: 14pt; font-weight: bold;")
        layout.addWidget(header_label)

        # Filters
        filters_row = QHBoxLayout()

        filters_row.addWidget(QLabel("Source:"))
        self._source_filter_combo = QComboBox()
        self._source_filter_combo.addItem("All", "all")
        self._source_filter_combo.addItem("Local", "local")
        self._source_filter_combo.addItem("URL", "url")
        self._source_filter_combo.addItem("Capture", "capture")
        self._source_filter_combo.addItem("Unknown", "unknown")
        self._source_filter_combo.currentIndexChanged.connect(self.refresh_library)
        filters_row.addWidget(self._source_filter_combo)

        filters_row.addWidget(QLabel("Status:"))
        self._missing_filter_combo = QComboBox()
        self._missing_filter_combo.addItem("All", "all")
        self._missing_filter_combo.addItem("Available", "available")
        self._missing_filter_combo.addItem("Missing", "missing")
        self._missing_filter_combo.currentIndexChanged.connect(self.refresh_library)
        filters_row.addWidget(self._missing_filter_combo)

        filters_row.addWidget(QLabel("Opened:"))
        self._opened_filter_combo = QComboBox()
        self._opened_filter_combo.addItem("All", "all")
        self._opened_filter_combo.addItem("Opened", "opened")
        self._opened_filter_combo.addItem("Not Opened", "not_opened")
        self._opened_filter_combo.currentIndexChanged.connect(self.refresh_library)
        filters_row.addWidget(self._opened_filter_combo)

        filters_row.addWidget(QLabel("Sort:"))
        self._sort_combo = QComboBox()
        self._sort_combo.addItem("Last Opened", "last_opened")
        self._sort_combo.addItem("Created", "created")
        self._sort_combo.addItem("Name", "name")
        self._sort_combo.currentIndexChanged.connect(self.refresh_library)
        filters_row.addWidget(self._sort_combo)

        self._sort_direction_combo = QComboBox()
        self._sort_direction_combo.addItem("Newest first", "desc")
        self._sort_direction_combo.addItem("Oldest first", "asc")
        self._sort_direction_combo.currentIndexChanged.connect(self.refresh_library)
        filters_row.addWidget(self._sort_direction_combo)

        filters_row.addStretch()
        layout.addLayout(filters_row)

        # Summary
        self._summary_label = QLabel("No transcripts in library")
        self._summary_label.setWordWrap(True)
        layout.addWidget(self._summary_label)

        # List
        self._entries_list = QListWidget()
        self._entries_list.itemActivated.connect(self._on_item_activated)
        layout.addWidget(self._entries_list, 1)

        # Actions
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

        # Status
        self._status_label = QLabel("Ready")
        layout.addWidget(self._status_label)

    def refresh_library(self) -> None:
        """Refresh library display."""
        all_entries = self._library_store.list_entries()

        source_kind = self._source_filter_combo.currentData()
        missing_filter = self._missing_filter_combo.currentData()
        opened_filter = self._opened_filter_combo.currentData()
        sort_mode = self._sort_combo.currentData()
        descending = self._sort_direction_combo.currentData() != "asc"

        entries = sort_transcript_library_entries(
            filter_transcript_library_entries(
                all_entries,
                source_kind=source_kind,
                missing_filter=missing_filter,
                opened_filter=opened_filter,
            ),
            sort_mode=sort_mode,
            descending=descending,
        )

        self._entries_cache = entries

        # Update summary
        summary = _library_results_summary(entries, total_count=len(all_entries))
        if any(entry.missing for entry in all_entries):
            summary += " | Use Clean Missing Entries to drop broken records."
        self._summary_label.setText(summary)

        # Update list
        self._entries_list.clear()
        for entry in entries:
            self._entries_list.addItem(_library_entry_list_label(entry))

        # Update status
        self._status_label.setText(f"Showing {len(entries)} of {len(all_entries)} transcripts")

    def _get_selected_entry(self) -> TranscriptLibraryEntry | None:
        """Get currently selected library entry."""
        row = self._entries_list.currentRow()
        if row < 0 or row >= len(self._entries_cache):
            return None
        return self._entries_cache[row]

    def _on_item_activated(self, item) -> None:
        """Handle double-click on item."""
        self._on_open_transcript()

    def _on_open_transcript(self) -> None:
        """Open selected transcript."""
        entry = self._get_selected_entry()
        if entry is None:
            self._status_label.setText("Select a transcript first")
            return
        if entry.missing:
            self._status_label.setText(f"Transcript is missing: {entry.transcript_path}")
            return
        self.transcript_open_requested.emit(entry)

    def _on_open_output_dir(self) -> None:
        """Open output directory for selected entry."""
        entry = self._get_selected_entry()
        if entry is None:
            self._status_label.setText("Select a transcript first")
            return
        self.output_dir_open_requested.emit(entry)

    def _on_rebind_media(self) -> None:
        """Rebind media for selected entry."""
        entry = self._get_selected_entry()
        if entry is None:
            self._status_label.setText("Select a transcript first")
            return
        if entry.missing:
            self._status_label.setText(f"Transcript is missing: {entry.transcript_path}")
            return
        self.media_rebind_requested.emit(entry)

    def _on_remove_entry(self) -> None:
        """Remove selected entry from library."""
        entry = self._get_selected_entry()
        if entry is None:
            self._status_label.setText("Select a transcript first")
            return
        self.entry_remove_requested.emit(entry)

    def _on_cleanup_missing(self) -> None:
        """Clean up missing entries."""
        # Auto-detect and remove all entries with any missing paths
        all_entries = self._library_store.list_entries()
        missing_count = sum(1 for entry in all_entries if entry.missing)

        if missing_count == 0:
            self._status_label.setText("No missing entries to clean up")
            return

        self.missing_cleanup_requested.emit()

    def _on_select_all(self) -> None:
        """Select all entries in the list."""
        self._entries_list.selectAll()
