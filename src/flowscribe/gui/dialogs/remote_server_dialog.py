"""Dialog for managing remote server profiles."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from flowscribe.execution.remote_config import (
    RemoteServerProfile,
    load_remote_server_profiles,
    remove_remote_server_profile,
    upsert_remote_server_profile,
)


class RemoteServerDialog(QDialog):
    """Create, update, and remove remote server profiles for GUI users."""

    profiles_changed = Signal()

    def __init__(self, parent: QWidget | None, *, selected_target: str | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Remote Servers")
        self.resize(560, 420)
        self._selected_target = selected_target
        self._setup_ui()
        self._reload_profiles(select_name=selected_target)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        selector_group = QGroupBox("Saved Profiles")
        selector_layout = QHBoxLayout(selector_group)
        selector_layout.setSpacing(8)

        self.profile_combo = QComboBox()
        self.profile_combo.currentIndexChanged.connect(self._on_profile_selected)
        selector_layout.addWidget(self.profile_combo, 1)

        new_button = QPushButton("New")
        new_button.clicked.connect(self._clear_form)
        selector_layout.addWidget(new_button)

        refresh_button = QPushButton("Refresh")
        refresh_button.clicked.connect(self._reload_profiles)
        selector_layout.addWidget(refresh_button)

        form_group = QGroupBox("Profile Details")
        form_layout = QGridLayout(form_group)
        form_layout.setHorizontalSpacing(10)
        form_layout.setVerticalSpacing(8)

        self.name_input = QLineEdit()
        self.base_url_input = QLineEdit()
        self.base_url_input.setPlaceholderText("http://127.0.0.1:18769")

        self.token_input = QLineEdit()
        self.token_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.token_input.setPlaceholderText("Optional bearer token")

        self.remote_cookies_path_input = QLineEdit()
        self.remote_cookies_path_input.setPlaceholderText(
            "Optional cookies.txt path on the remote server"
        )

        self.enabled_check = QCheckBox("Enabled")
        self.verify_tls_check = QCheckBox("Verify TLS")
        self.download_artifacts_check = QCheckBox("Download artifacts by default")

        self.timeout_spin = QDoubleSpinBox()
        self.timeout_spin.setRange(1.0, 300.0)
        self.timeout_spin.setDecimals(1)
        self.timeout_spin.setSingleStep(1.0)
        self.timeout_spin.setSuffix(" seconds")

        form_layout.addWidget(QLabel("Profile name"), 0, 0)
        form_layout.addWidget(self.name_input, 0, 1)
        form_layout.addWidget(QLabel("Base URL"), 1, 0)
        form_layout.addWidget(self.base_url_input, 1, 1)
        form_layout.addWidget(QLabel("Token"), 2, 0)
        form_layout.addWidget(self.token_input, 2, 1)
        form_layout.addWidget(QLabel("Remote cookies path"), 3, 0)
        form_layout.addWidget(self.remote_cookies_path_input, 3, 1)
        form_layout.addWidget(QLabel("Timeout"), 4, 0)
        form_layout.addWidget(self.timeout_spin, 4, 1)
        form_layout.addWidget(self.enabled_check, 5, 0, 1, 2)
        form_layout.addWidget(self.verify_tls_check, 6, 0, 1, 2)
        form_layout.addWidget(self.download_artifacts_check, 7, 0, 1, 2)

        note = QLabel(
            "Use profile names in Queue settings, or type a full URL directly when you need a one-off target. "
            "Set a remote cookies path when the server should use its own cookies.txt for login-required URL media."
        )
        note.setWordWrap(True)
        note.setProperty("compactNote", True)

        button_row = QHBoxLayout()
        button_row.addStretch(1)

        save_button = QPushButton("Save")
        save_button.clicked.connect(self._save_profile)
        button_row.addWidget(save_button)

        remove_button = QPushButton("Remove")
        remove_button.clicked.connect(self._remove_profile)
        button_row.addWidget(remove_button)

        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        button_row.addWidget(close_button)

        layout.addWidget(selector_group)
        layout.addWidget(form_group)
        layout.addWidget(note)
        layout.addStretch(1)
        layout.addLayout(button_row)

    def _reload_profiles(self, *_args, select_name: str | None = None) -> None:
        profiles = load_remote_server_profiles()
        target = select_name if select_name is not None else self._selected_target
        current_name = None
        self.profile_combo.blockSignals(True)
        self.profile_combo.clear()
        self.profile_combo.addItem("(New Profile)", None)
        for profile in profiles:
            self.profile_combo.addItem(profile.name, profile.name)
            if current_name is None and target and profile.name == target:
                current_name = profile.name
        self.profile_combo.blockSignals(False)

        if current_name is not None:
            index = self.profile_combo.findData(current_name)
            self.profile_combo.setCurrentIndex(index if index >= 0 else 0)
            return
        if not profiles and target:
            self._clear_form()
            self.base_url_input.setText(target)
            return
        self.profile_combo.setCurrentIndex(0)
        self._on_profile_selected(self.profile_combo.currentIndex())

    def _on_profile_selected(self, index: int) -> None:
        name = self.profile_combo.itemData(index)
        if not name:
            self._clear_form()
            return
        for profile in load_remote_server_profiles():
            if profile.name == name:
                self._load_profile(profile)
                return
        self._clear_form()

    def _load_profile(self, profile: RemoteServerProfile) -> None:
        self.name_input.setText(profile.name)
        self.base_url_input.setText(profile.base_url)
        self.token_input.setText(profile.token or "")
        self.remote_cookies_path_input.setText(profile.remote_cookies_path or "")
        self.enabled_check.setChecked(profile.enabled)
        self.verify_tls_check.setChecked(profile.verify_tls)
        self.timeout_spin.setValue(profile.timeout_seconds)
        self.download_artifacts_check.setChecked(profile.download_artifacts_by_default)

    def _clear_form(self) -> None:
        self.name_input.clear()
        self.base_url_input.clear()
        self.token_input.clear()
        self.remote_cookies_path_input.clear()
        self.enabled_check.setChecked(True)
        self.verify_tls_check.setChecked(True)
        self.timeout_spin.setValue(30.0)
        self.download_artifacts_check.setChecked(True)

    def _save_profile(self) -> None:
        name = self.name_input.text().strip()
        base_url = self.base_url_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Missing Name", "Please enter a profile name.")
            return
        if not base_url:
            QMessageBox.warning(self, "Missing URL", "Please enter the server base URL.")
            return
        profile = RemoteServerProfile(
            name=name,
            base_url=base_url,
            token=self.token_input.text().strip() or None,
            remote_cookies_path=self.remote_cookies_path_input.text().strip() or None,
            enabled=self.enabled_check.isChecked(),
            verify_tls=self.verify_tls_check.isChecked(),
            timeout_seconds=float(self.timeout_spin.value()),
            download_artifacts_by_default=self.download_artifacts_check.isChecked(),
        )
        upsert_remote_server_profile(profile)
        self._selected_target = profile.name
        self._reload_profiles(select_name=profile.name)
        self.profiles_changed.emit()

    def _remove_profile(self) -> None:
        name = self.name_input.text().strip()
        if not name:
            return
        if not remove_remote_server_profile(name):
            return
        self._selected_target = None
        self._reload_profiles()
        self.profiles_changed.emit()
