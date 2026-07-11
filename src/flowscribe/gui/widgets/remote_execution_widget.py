"""Reusable remote execution settings widget for GUI dialogs and queue defaults."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from flowscribe.execution.remote_config import load_remote_server_profiles
from flowscribe.gui.remote_targets import inspect_remote_target


class RemoteExecutionWidget(QWidget):
    """Shared remote execution form with inline resolution and validation feedback."""

    settings_changed = Signal(dict)

    def __init__(self, parent: QWidget | None = None, *, show_manage_button: bool = True) -> None:
        super().__init__(parent)
        self._loading = False
        self._show_manage_button = show_manage_button
        self._setup_ui()
        self._wire_signals()
        self.refresh_remote_server_targets()
        self._sync_remote_controls()
        self._update_resolution_hint()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(8)

        self.execution_mode_combo = QComboBox()
        self.execution_mode_combo.addItem("Local", "local")
        self.execution_mode_combo.addItem("Remote", "remote")

        self.server_target_combo = QComboBox()
        self.server_target_combo.setEditable(True)

        self.remote_token_input = QLineEdit()
        self.remote_token_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.remote_token_input.setPlaceholderText("Optional override token")

        self.remote_poll_seconds_spin = QDoubleSpinBox()
        self.remote_poll_seconds_spin.setRange(0.1, 60.0)
        self.remote_poll_seconds_spin.setDecimals(1)
        self.remote_poll_seconds_spin.setSingleStep(0.5)
        self.remote_poll_seconds_spin.setSuffix(" seconds")

        self.download_artifacts_check = QCheckBox("Download artifacts after remote completion")

        grid.addWidget(QLabel("Execution mode"), 0, 0)
        grid.addWidget(self.execution_mode_combo, 0, 1)
        grid.addWidget(QLabel("Server profile or URL"), 1, 0)
        grid.addWidget(self.server_target_combo, 1, 1)
        grid.addWidget(QLabel("Token override"), 2, 0)
        grid.addWidget(self.remote_token_input, 2, 1)
        grid.addWidget(QLabel("Poll interval"), 3, 0)
        grid.addWidget(self.remote_poll_seconds_spin, 3, 1)
        grid.addWidget(self.download_artifacts_check, 4, 0, 1, 2)
        layout.addLayout(grid)

        hint_row = QHBoxLayout()
        hint_row.setContentsMargins(0, 0, 0, 0)
        self.resolved_target_label = QLabel()
        self.resolved_target_label.setWordWrap(True)
        self.resolved_target_label.setProperty("compactNote", True)
        hint_row.addWidget(self.resolved_target_label, 1)
        if self._show_manage_button:
            self.manage_remote_servers_button = QPushButton("Manage Remote Servers...")
            hint_row.addWidget(self.manage_remote_servers_button)
        else:
            self.manage_remote_servers_button = None
        layout.addLayout(hint_row)

    def _wire_signals(self) -> None:
        self.execution_mode_combo.currentIndexChanged.connect(self._sync_remote_controls)
        self.execution_mode_combo.currentIndexChanged.connect(self._emit_settings_changed)
        self.execution_mode_combo.currentIndexChanged.connect(self._update_resolution_hint)
        self.server_target_combo.currentTextChanged.connect(self._emit_settings_changed)
        self.server_target_combo.currentTextChanged.connect(self._update_resolution_hint)
        self.remote_token_input.textChanged.connect(self._emit_settings_changed)
        self.remote_poll_seconds_spin.valueChanged.connect(self._emit_settings_changed)
        self.download_artifacts_check.toggled.connect(self._emit_settings_changed)
        if self.manage_remote_servers_button is not None:
            self.manage_remote_servers_button.clicked.connect(self._open_remote_server_manager)

    def load_settings(self, settings: dict[str, Any]) -> None:
        self._loading = True
        mode = settings.get("execution_mode", "local")
        index = self.execution_mode_combo.findData(mode)
        self.execution_mode_combo.setCurrentIndex(index if index >= 0 else 0)
        self.refresh_remote_server_targets(settings.get("server_target"))
        self.remote_token_input.setText(settings.get("remote_token", "") or "")
        self.remote_poll_seconds_spin.setValue(float(settings.get("remote_poll_seconds", 1.0)))
        self.download_artifacts_check.setChecked(settings.get("download_artifacts", True))
        self._loading = False
        self._sync_remote_controls()
        self._update_resolution_hint()

    def settings(self) -> dict[str, Any]:
        return {
            "execution_mode": self.execution_mode_combo.currentData() or "local",
            "server_target": self.server_target_combo.currentText().strip() or None,
            "remote_token": self.remote_token_input.text().strip() or None,
            "remote_poll_seconds": float(self.remote_poll_seconds_spin.value()),
            "download_artifacts": self.download_artifacts_check.isChecked(),
        }

    def refresh_remote_server_targets(self, current_target: str | None = None) -> None:
        current = current_target
        if current is None:
            current = self.server_target_combo.currentText().strip()
        self.server_target_combo.blockSignals(True)
        self.server_target_combo.clear()
        for profile in load_remote_server_profiles():
            self.server_target_combo.addItem(profile.name)
        self.server_target_combo.setCurrentText(current or "")
        self.server_target_combo.blockSignals(False)
        self._update_resolution_hint()

    def validate_settings(self, *, parent: QWidget | None = None, title: str = "Remote Execution") -> bool:
        if (self.execution_mode_combo.currentData() or "local") != "remote":
            return True
        inspection = inspect_remote_target(self.server_target_combo.currentText())
        if inspection.valid:
            return True
        QMessageBox.warning(parent or self, title, inspection.error or inspection.message)
        return False

    def _sync_remote_controls(self) -> None:
        remote_enabled = (self.execution_mode_combo.currentData() or "local") == "remote"
        self.server_target_combo.setEnabled(remote_enabled)
        self.remote_token_input.setEnabled(remote_enabled)
        self.remote_poll_seconds_spin.setEnabled(remote_enabled)
        self.download_artifacts_check.setEnabled(remote_enabled)
        self.resolved_target_label.setEnabled(remote_enabled)
        if self.manage_remote_servers_button is not None:
            self.manage_remote_servers_button.setEnabled(remote_enabled)

    def _update_resolution_hint(self) -> None:
        if (self.execution_mode_combo.currentData() or "local") != "remote":
            self.resolved_target_label.setText("Local execution selected.")
            self.resolved_target_label.setStyleSheet("color: gray;")
            return
        inspection = inspect_remote_target(self.server_target_combo.currentText())
        self.resolved_target_label.setText(inspection.message)
        self.resolved_target_label.setStyleSheet("color: gray;" if inspection.valid else "color: #B91C1C;")

    def _open_remote_server_manager(self) -> None:
        from flowscribe.gui.dialogs.remote_server_dialog import RemoteServerDialog

        dialog = RemoteServerDialog(
            self,
            selected_target=self.server_target_combo.currentText().strip() or None,
        )
        dialog.profiles_changed.connect(self.refresh_remote_server_targets)
        dialog.exec()
        self.refresh_remote_server_targets()

    def _emit_settings_changed(self, *_args) -> None:
        if self._loading:
            return
        self.settings_changed.emit(self.settings())
