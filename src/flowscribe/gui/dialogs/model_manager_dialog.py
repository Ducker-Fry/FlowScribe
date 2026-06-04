"""Dialog for managing FlowScribe transcription models."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from flowscribe.model_manager import (
    download_model,
    import_native_model,
    list_available_models,
    list_installed_models,
    local_model_guide_path,
    remove_model,
)


class ModelManagerDialog(QDialog):
    """Manage local transcription models and native imports."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Model Center")
        self.resize(860, 620)
        self._setup_ui()
        self._refresh_lists()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        summary = QLabel(
            "Install recommended models here before first use. "
            "This prevents long background downloads from looking like the app is stuck."
        )
        summary.setWordWrap(True)
        layout.addWidget(summary)

        split_row = QHBoxLayout()
        split_row.setSpacing(10)

        left = QVBoxLayout()
        left.addWidget(QLabel("Available Models"))
        self._available_list = QListWidget()
        left.addWidget(self._available_list, 1)
        self._download_button = QPushButton("Download Selected")
        self._download_button.clicked.connect(self._download_selected)
        left.addWidget(self._download_button)
        split_row.addLayout(left, 1)

        right = QVBoxLayout()
        right.addWidget(QLabel("Installed Models"))
        self._installed_list = QListWidget()
        right.addWidget(self._installed_list, 1)
        right_actions = QHBoxLayout()
        self._import_button = QPushButton("Import Native .bin")
        self._import_button.clicked.connect(self._import_native)
        self._remove_button = QPushButton("Remove Selected")
        self._remove_button.clicked.connect(self._remove_selected)
        right_actions.addWidget(self._import_button)
        right_actions.addWidget(self._remove_button)
        right.addLayout(right_actions)
        split_row.addLayout(right, 1)

        layout.addLayout(split_row, 1)

        self._log_output = QPlainTextEdit()
        self._log_output.setReadOnly(True)
        self._log_output.setPlaceholderText("Model downloads, removals, and imports will appear here.")
        layout.addWidget(self._log_output, 1)

        footer = QHBoxLayout()
        self._help_button = QPushButton("Open Model Guide")
        self._help_button.clicked.connect(self._open_model_guide)
        footer.addWidget(self._help_button)
        footer.addStretch(1)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        button_box.rejected.connect(self.reject)
        button_box.accepted.connect(self.accept)
        footer.addWidget(button_box)
        layout.addLayout(footer)

    def _refresh_lists(self) -> None:
        self._available_list.clear()
        for entry in list_available_models():
            recommended = " [recommended]" if entry.recommended else ""
            size = f" ({entry.approx_size_mb} MB)" if entry.approx_size_mb is not None else ""
            item = QListWidgetItem(f"{entry.model_id}{recommended}{size}\n{entry.description}")
            item.setData(Qt.ItemDataRole.UserRole, entry.model_id)
            self._available_list.addItem(item)

        self._installed_list.clear()
        for entry in list_installed_models():
            imported = " [imported]" if entry.imported else ""
            path_label = str(entry.path) if entry.path is not None else "managed path unavailable"
            item = QListWidgetItem(f"{entry.model_id}{imported}\n{path_label}")
            item.setData(Qt.ItemDataRole.UserRole, entry.model_id)
            self._installed_list.addItem(item)

    def _download_selected(self) -> None:
        item = self._available_list.currentItem()
        if item is None:
            self._append_log("Select a model to download first.")
            return
        model_id = item.data(Qt.ItemDataRole.UserRole)
        try:
            download_model(model_id, progress=self._append_log)
        except Exception as exc:
            QMessageBox.warning(self, "Model Download Failed", str(exc))
            self._append_log(f"Download failed: {exc}")
            return
        self._append_log(f"Installed model: {model_id}")
        self._refresh_lists()

    def _remove_selected(self) -> None:
        item = self._installed_list.currentItem()
        if item is None:
            self._append_log("Select an installed model to remove first.")
            return
        model_id = item.data(Qt.ItemDataRole.UserRole)
        if remove_model(model_id):
            self._append_log(f"Removed model: {model_id}")
        else:
            self._append_log(f"Model not found: {model_id}")
        self._refresh_lists()

    def _import_native(self) -> None:
        path_text, _ = QFileDialog.getOpenFileName(
            self,
            "Choose native whisper.cpp model",
            str(Path.home()),
            "Whisper.cpp Models (*.bin);;All files (*.*)",
        )
        if not path_text:
            return
        try:
            entry = import_native_model(Path(path_text))
        except Exception as exc:
            QMessageBox.warning(self, "Import Failed", str(exc))
            self._append_log(f"Native import failed: {exc}")
            return
        self._append_log(f"Imported native model: {entry.path}")
        self._refresh_lists()

    def _open_model_guide(self) -> None:
        path = local_model_guide_path()
        if path is None:
            self._append_log("Local model guide is not installed.")
            return
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))):
            self._append_log(f"Could not open model guide: {path}")

    def _append_log(self, message: str) -> None:
        self._log_output.appendPlainText(message)
