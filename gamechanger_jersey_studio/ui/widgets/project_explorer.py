"""Centre project explorer panel."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QVBoxLayout

from ui.theme import Theme


class ProjectExplorer(QFrame):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("panel")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(16)

        heading = QLabel("Project Explorer")
        heading.setStyleSheet(f"font-size: 16px; font-weight: 600; color: {Theme.TEXT};")

        self._message = QLabel("No project loaded.")
        self._message.setProperty("muted", True)
        self._message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._message.setStyleSheet("font-size: 15px; padding: 48px 0;")

        self._import_btn = QPushButton("Import Reference Images")
        self._import_btn.setEnabled(False)
        self._import_btn.setFixedWidth(220)

        btn_row = QVBoxLayout()
        btn_row.addWidget(self._import_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(heading)
        layout.addStretch(1)
        layout.addWidget(self._message)
        layout.addLayout(btn_row)
        layout.addStretch(2)

    def set_project_loaded(self, loaded: bool, name: str = "") -> None:
        if loaded and name:
            self._message.setText(f"Project loaded: {name}")
        else:
            self._message.setText("No project loaded.")
