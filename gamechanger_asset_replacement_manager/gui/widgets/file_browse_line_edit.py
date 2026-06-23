"""Single-file line edit with browse button."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QLineEdit, QPushButton, QWidget


class FileBrowseLineEdit(QWidget):
    path_changed = Signal(str)

    def __init__(
        self,
        *,
        file_filter: str = "Media files (*.mp4 *.mov *.wav)",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._file_filter = file_filter
        self._line = QLineEdit()
        self._line.setPlaceholderText("Optional — Browse to select file…")
        self._line.setMinimumHeight(40)
        self._line.editingFinished.connect(self._emit_path)

        browse_btn = QPushButton("Browse")
        browse_btn.setProperty("class", "primary")
        browse_btn.setMinimumHeight(40)
        browse_btn.clicked.connect(self._browse)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._line, stretch=1)
        layout.addWidget(browse_btn)

    def set_path(self, path: str) -> None:
        self._line.setText(path)
        self.path_changed.emit(path)

    def path(self) -> str:
        return self._line.text().strip()

    def clear_path(self) -> None:
        self._line.clear()
        self.path_changed.emit("")

    def _emit_path(self) -> None:
        self.path_changed.emit(self.path())

    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Replacement File",
            self.path() or "",
            self._file_filter,
        )
        if path:
            self.set_path(path)
