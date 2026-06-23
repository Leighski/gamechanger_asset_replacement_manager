"""Modern preferences dialog with tabbed sections."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from gui.preset_dialog import PresetManagerDialog
from gui.theme import Theme
from services.paths import CATALOGUES_PATH, REPORTS_DIR
from services.settings_service import SettingsService


class SettingsDialog(QDialog):
    def __init__(
        self,
        settings: SettingsService,
        *,
        on_aws_saved,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Preferences")
        self.resize(640, 520)
        self._settings = settings
        self._on_aws_saved = on_aws_saved

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        tabs = QTabWidget()

        tabs.addTab(self._build_general_tab(), "General")
        tabs.addTab(self._build_aws_tab(), "AWS")
        tabs.addTab(self._build_catalogues_tab(), "Catalogues")
        tabs.addTab(self._build_presets_tab(), "Path Presets")
        tabs.addTab(self._build_reports_tab(), "Reports")
        tabs.addTab(self._build_iconik_tab(), "Iconik")

        layout.addWidget(tabs)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        ok_btn = buttons.button(QDialogButtonBox.StandardButton.Ok)
        if ok_btn:
            ok_btn.setText("Done")
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

    def _build_general_tab(self) -> QWidget:
        tab = QWidget()
        form = QFormLayout(tab)
        form.setSpacing(14)

        self._safety = QCheckBox("Replace existing S3 objects only (skip if not in S3)")
        self._safety.setChecked(self._settings.safety_replace_existing_only())
        self._safety.stateChanged.connect(
            lambda: self._settings.set_safety_replace_existing_only(self._safety.isChecked())
        )

        self._workers = QSpinBox()
        self._workers.setRange(1, 16)
        self._workers.setValue(self._settings.upload_max_workers())
        self._workers.valueChanged.connect(self._settings.set_upload_max_workers)

        form.addRow("Safety mode:", self._safety)
        form.addRow("Upload threads:", self._workers)
        note = QLabel(
            "Safety mode prevents accidental creation of new S3 assets. "
            "Only objects that already exist in the catalogue prefix can be replaced."
        )
        note.setWordWrap(True)
        note.setProperty("class", "muted")
        form.addRow(note)
        return tab

    def _build_aws_tab(self) -> QWidget:
        tab = QWidget()
        form = QFormLayout(tab)
        aws = self._settings.aws

        self._aws_key = QLineEdit(aws.get("aws_access_key_id", ""))
        self._aws_secret = QLineEdit(aws.get("aws_secret_access_key", ""))
        self._aws_secret.setEchoMode(QLineEdit.EchoMode.Password)
        self._aws_token = QLineEdit(aws.get("aws_session_token", ""))
        self._aws_region = QLineEdit(
            aws.get("aws_region") or str(self._settings.user.get("aws_region", "eu-west-1"))
        )

        save_btn = QPushButton("Save AWS Credentials")
        save_btn.setProperty("class", "primary")
        save_btn.clicked.connect(self._save_aws)

        form.addRow("Access key ID:", self._aws_key)
        form.addRow("Secret access key:", self._aws_secret)
        form.addRow("Session token:", self._aws_token)
        form.addRow("Region:", self._aws_region)
        form.addRow("", save_btn)

        hint = QLabel(
            "Leave keys empty to use the default AWS credential chain "
            "(environment variables, ~/.aws/credentials, or SSO)."
        )
        hint.setWordWrap(True)
        hint.setProperty("class", "muted")
        form.addRow(hint)
        return tab

    def _save_aws(self) -> None:
        self._settings.update_aws(
            aws_access_key_id=self._aws_key.text().strip(),
            aws_secret_access_key=self._aws_secret.text().strip(),
            aws_session_token=self._aws_token.text().strip(),
            aws_region=self._aws_region.text().strip() or "eu-west-1",
        )
        self._on_aws_saved()

    def _build_catalogues_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        self._custom_s3 = QLineEdit(self._settings.custom_s3_path())
        self._custom_s3.setPlaceholderText("s3://bucket/prefix/ (for CUSTOM catalogue)")
        self._custom_s3.editingFinished.connect(
            lambda: self._settings.set_custom_s3_path(self._custom_s3.text().strip())
        )

        layout.addWidget(QLabel("Custom S3 path"))
        layout.addWidget(self._custom_s3)

        path_lbl = QLabel(f"Catalogue mappings file:\n{CATALOGUES_PATH}")
        path_lbl.setWordWrap(True)
        path_lbl.setProperty("class", "muted")
        layout.addWidget(path_lbl)
        layout.addStretch()
        return tab

    def _build_presets_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.addWidget(
            QLabel("Path presets are shared with the Source Files screen.")
        )
        manage = QPushButton("Manage Path Presets…")
        manage.setProperty("class", "primary")
        manage.clicked.connect(self._manage_presets)
        layout.addWidget(manage)
        layout.addStretch()
        return tab

    def _manage_presets(self) -> None:
        dlg = PresetManagerDialog(self._settings.presets, self)
        if dlg.exec():
            self._settings.save_presets(dlg.presets())

    def _build_reports_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        info = QLabel(
            f"Audit reports are written to:\n{REPORTS_DIR}\n\n"
            "• replacement_report.csv\n"
            "• replacement_report.xlsx\n\n"
            "Timestamped copies are also saved after each upload run."
        )
        info.setWordWrap(True)
        layout.addWidget(info)
        layout.addStretch()
        return tab

    def _build_iconik_tab(self) -> QWidget:
        tab = QWidget()
        form = QFormLayout(tab)
        form.setSpacing(14)

        self._iconik_base = QLineEdit(self._settings.iconik_base_url())
        self._iconik_app = QLineEdit(self._settings.iconik_app_id())
        self._iconik_token = QLineEdit(self._settings.iconik_auth_token())
        self._iconik_token.setEchoMode(QLineEdit.EchoMode.Password)
        self._iconik_storage = QLineEdit(self._settings.iconik_storage_id())

        save_btn = QPushButton("Save Iconik Settings")
        save_btn.setProperty("class", "primary")
        save_btn.clicked.connect(self._save_iconik)

        form.addRow("Base URL:", self._iconik_base)
        form.addRow("App ID:", self._iconik_app)
        form.addRow("Auth token:", self._iconik_token)
        form.addRow("Storage ID:", self._iconik_storage)
        form.addRow("", save_btn)

        hint = QLabel(
            "Required for direct ENGP/CFX replacement verification and storage scan."
        )
        hint.setWordWrap(True)
        hint.setProperty("class", "muted")
        form.addRow(hint)
        return tab

    def _save_iconik(self) -> None:
        self._settings.set_iconik_settings(
            base_url=self._iconik_base.text(),
            app_id=self._iconik_app.text(),
            auth_token=self._iconik_token.text(),
            storage_id=self._iconik_storage.text(),
        )
