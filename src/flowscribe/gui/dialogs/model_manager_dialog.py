"""Dialog for managing FlowScribe transcription models."""

from __future__ import annotations

from pathlib import Path
import logging

from PySide6.QtCore import QObject, QThread, Qt, QUrl, Signal, Slot
from PySide6.QtGui import QCloseEvent, QDesktopServices
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from flowscribe.config.resources import resolve_resource_paths
from flowscribe.utils.runtime_logging import active_log_file_path, flowscribe_log_dir
from flowscribe.model_manager import (
    download_model,
    import_native_model,
    list_available_models,
    list_installed_models,
    local_model_guide_path,
    remove_model,
)

LOGGER = logging.getLogger(__name__)


class ModelDownloadWorker(QObject):
    """Runs a model download off the UI thread."""

    progress = Signal(str)
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, model_id: str, models_dir: Path) -> None:
        super().__init__()
        self._model_id = model_id
        self._models_dir = models_dir

    @Slot()
    def run(self) -> None:
        try:
            result = download_model(
                self._model_id,
                progress=self.progress.emit,
                models_dir=self._models_dir,
            )
        except Exception as exc:  # pragma: no cover - GUI boundary
            self.failed.emit(str(exc))
            return
        self.finished.emit(result)


class ModelManagerDialog(QDialog):
    """Manage local transcription models and native imports."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Model Center")
        self.resize(860, 620)
        self._download_thread: QThread | None = None
        self._download_worker: ModelDownloadWorker | None = None
        self._setup_ui()
        self._refresh_lists()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        summary = QLabel(
            "Install recommended models here before first use. "
            "Downloads now run in the background so the window stays responsive."
        )
        summary.setWordWrap(True)
        layout.addWidget(summary)

        location_row = QHBoxLayout()
        location_row.setSpacing(8)
        location_row.addWidget(QLabel("Download Directory"))
        self._models_dir_input = QLineEdit(str(resolve_resource_paths().models_dir))
        self._models_dir_input.setPlaceholderText("Choose where downloaded models should be stored")
        self._models_dir_input.setClearButtonEnabled(True)
        location_row.addWidget(self._models_dir_input, 1)
        self._browse_button = QPushButton("Browse...")
        self._browse_button.clicked.connect(self._choose_models_dir)
        location_row.addWidget(self._browse_button)
        layout.addLayout(location_row)

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
        self._open_logs_button = QPushButton("Open Logs")
        self._open_logs_button.clicked.connect(self._open_logs_dir)
        footer.addWidget(self._open_logs_button)
        self._help_button = QPushButton("Open Model Guide")
        self._help_button.clicked.connect(self._open_model_guide)
        footer.addWidget(self._help_button)
        footer.addStretch(1)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        button_box.rejected.connect(self.reject)
        button_box.accepted.connect(self.accept)
        footer.addWidget(button_box)
        layout.addLayout(footer)

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._download_thread is not None:
            self._append_log("A model download is still running. Wait for it to finish before closing Model Center.")
            QMessageBox.information(
                self,
                "Download In Progress",
                "A model download is still running. Please wait for it to finish before closing Model Center.",
            )
            event.ignore()
            return
        super().closeEvent(event)

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
        if self._download_thread is not None:
            self._append_log("A model download is already running.")
            return
        item = self._available_list.currentItem()
        if item is None:
            self._append_log("Select a model to download first.")
            return
        model_id = item.data(Qt.ItemDataRole.UserRole)
        models_dir = self._selected_models_dir()
        if models_dir is None:
            return

        self._append_log(f"Queued download for `{model_id}`")
        LOGGER.info("Model Center queued download: model_id=%s models_dir=%s", model_id, models_dir)
        self._set_download_controls_enabled(False)

        self._download_thread = QThread(self)
        self._download_worker = ModelDownloadWorker(model_id, models_dir)
        self._download_worker.moveToThread(self._download_thread)
        self._download_thread.started.connect(self._download_worker.run)
        self._download_worker.progress.connect(self._append_log)
        self._download_worker.finished.connect(self._on_download_finished)
        self._download_worker.failed.connect(self._on_download_failed)
        self._download_worker.finished.connect(self._download_thread.quit)
        self._download_worker.failed.connect(self._download_thread.quit)
        self._download_thread.finished.connect(self._download_worker.deleteLater)
        self._download_thread.finished.connect(self._download_thread.deleteLater)
        self._download_thread.finished.connect(self._clear_download_worker_refs)
        self._download_thread.start()

    def _remove_selected(self) -> None:
        item = self._installed_list.currentItem()
        if item is None:
            self._append_log("Select an installed model to remove first.")
            return
        model_id = item.data(Qt.ItemDataRole.UserRole)
        if remove_model(model_id):
            self._append_log(f"Removed model: {model_id}")
            LOGGER.info("Model Center removed model: %s", model_id)
        else:
            self._append_log(f"Model not found: {model_id}")
            LOGGER.warning("Model Center remove requested for missing model: %s", model_id)
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
            LOGGER.exception("Model Center native import failed: path=%s", path_text)
            return
        self._append_log(f"Imported native model: {entry.path}")
        LOGGER.info("Model Center imported native model: %s", entry.path)
        self._refresh_lists()

    def _open_model_guide(self) -> None:
        path = local_model_guide_path()
        if path is None:
            self._append_log("Local model guide is not installed.")
            return
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))):
            self._append_log(f"Could not open model guide: {path}")

    def _choose_models_dir(self) -> None:
        selected = QFileDialog.getExistingDirectory(
            self,
            "Choose models download directory",
            self._models_dir_input.text().strip() or str(resolve_resource_paths().models_dir),
        )
        if selected:
            self._models_dir_input.setText(selected)

    def _selected_models_dir(self) -> Path | None:
        raw_value = self._models_dir_input.text().strip()
        if not raw_value:
            self._append_log("Choose a download directory first.")
            return None
        try:
            return Path(raw_value).expanduser().resolve()
        except Exception as exc:
            QMessageBox.warning(self, "Invalid Directory", str(exc))
            self._append_log(f"Invalid model directory: {exc}")
            return None

    def _set_download_controls_enabled(self, enabled: bool) -> None:
        self._download_button.setEnabled(enabled)
        self._browse_button.setEnabled(enabled)
        self._models_dir_input.setEnabled(enabled)
        self._available_list.setEnabled(enabled)
        self._installed_list.setEnabled(enabled)
        self._remove_button.setEnabled(enabled)
        self._import_button.setEnabled(enabled)

    def _on_download_finished(self, record) -> None:
        self._append_log(f"Installed model: {record.display_name}")
        LOGGER.info(
            "Model Center download finished: model_id=%s display_name=%s path=%s",
            record.model_id,
            record.display_name,
            record.path,
        )
        self._refresh_lists()
        self._set_download_controls_enabled(True)

    def _on_download_failed(self, error: str) -> None:
        self._append_log(f"Download failed: {error}")
        LOGGER.error("Model Center download failed: %s", error)
        self._set_download_controls_enabled(True)
        QMessageBox.warning(self, "Model Download Failed", error)

    def _clear_download_worker_refs(self) -> None:
        self._download_worker = None
        self._download_thread = None

    def reject(self) -> None:
        if self._download_thread is not None:
            self.close()
            return
        super().reject()

    def _append_log(self, message: str) -> None:
        self._log_output.appendPlainText(message)
        if message.startswith("Download failed:"):
            log_path = active_log_file_path("FlowScribeGUI")
            if log_path is not None:
                self._log_output.appendPlainText(f"See log file: {log_path}")

    def _open_logs_dir(self) -> None:
        log_path = active_log_file_path("FlowScribeGUI")
        target = log_path.parent if log_path is not None else flowscribe_log_dir()
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(target))):
            self._append_log(f"Could not open logs directory: {target}")
