"""New Project wizard."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.version import APP_VERSION, BUILD_LABEL
from models.project import DEFAULT_BUILD_PROFILE, KitType, NewProjectRequest
from services.project_validator import validate_new_project_request
from ui.theme import Theme


class NewProjectWizard(QDialog):
    def __init__(self, default_output_folder: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("New Project")
        self.setModal(True)
        self.resize(560, 620)
        self._result_request: NewProjectRequest | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 20)
        layout.setSpacing(16)

        title = QLabel("New Project")
        title.setProperty("title", True)
        subtitle = QLabel("Create a new Gamechanger Jersey Studio project (.gjs)")
        subtitle.setProperty("muted", True)

        form_host = QWidget()
        form = QFormLayout(form_host)
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._project_name = QLineEdit()
        self._club_name = QLineEdit()
        self._competition = QLineEdit()
        self._season = QLineEdit()
        self._kit_type = QComboBox()
        for kit in KitType:
            self._kit_type.addItem(kit.value, kit)
        self._build_profile = QLineEdit(DEFAULT_BUILD_PROFILE)
        self._output_folder = QLineEdit(default_output_folder)
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse_output)
        folder_row = QHBoxLayout()
        folder_row.addWidget(self._output_folder, stretch=1)
        folder_row.addWidget(browse)
        self._notes = QPlainTextEdit()
        self._notes.setMaximumHeight(90)
        self._author = QLineEdit()
        self._created = QLineEdit(datetime.now(timezone.utc).strftime("%d %B %Y"))
        self._created.setReadOnly(True)
        self._version = QLineEdit(f"{APP_VERSION} ({BUILD_LABEL})")
        self._version.setReadOnly(True)

        form.addRow("Project Name *", self._project_name)
        form.addRow("Club Name *", self._club_name)
        form.addRow("Competition *", self._competition)
        form.addRow("Season *", self._season)
        form.addRow("Kit Type *", self._kit_type)
        form.addRow("Build Profile *", self._build_profile)
        form.addRow("Output Folder *", folder_row)
        form.addRow("Project Notes", self._notes)
        form.addRow("Author *", self._author)
        form.addRow("Creation Date", self._created)
        form.addRow("Application Version", self._version)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Create Project")
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(form_host, stretch=1)
        layout.addWidget(buttons)

    def request(self) -> NewProjectRequest | None:
        return self._result_request

    def _browse_output(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select Output Folder", self._output_folder.text())
        if folder:
            self._output_folder.setText(folder)

    def _accept(self) -> None:
        kit = self._kit_type.currentData()
        request = NewProjectRequest(
            project_name=self._project_name.text(),
            club_name=self._club_name.text(),
            competition=self._competition.text(),
            season=self._season.text(),
            kit_type=kit,
            build_profile=self._build_profile.text(),
            output_folder=self._output_folder.text(),
            project_notes=self._notes.toPlainText(),
            author=self._author.text(),
        )
        errors = validate_new_project_request(request)
        if errors:
            QMessageBox.warning(self, "Validation", "\n".join(errors))
            return
        self._result_request = request
        self.accept()
