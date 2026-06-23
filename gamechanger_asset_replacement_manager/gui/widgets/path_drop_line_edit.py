"""Line edit with folder browse and drag-and-drop."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import QHBoxLayout, QLineEdit, QPushButton, QWidget


class PathDropLineEdit(QWidget):
    path_changed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._line = QLineEdit()
        self._line.setPlaceholderText("Select or drop a folder…")
        self._line.setMinimumHeight(40)
        self._line.editingFinished.connect(self._emit_path)

        browse_btn = QPushButton("Browse…")
        browse_btn.setProperty("class", "primary")
        browse_btn.setMinimumHeight(40)
        browse_btn.clicked.connect(self._browse)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._line, stretch=1)
        layout.addWidget(browse_btn)

        self.setAcceptDrops(True)
        self._line.setAcceptDrops(True)
        self._line.dragEnterEvent = self._drag_enter  # type: ignore[method-assign]
        self._line.dropEvent = self._drop  # type: ignore[method-assign]

    def set_path(self, path: str) -> None:
        self._line.setText(path)
        self.path_changed.emit(path)

    def path(self) -> str:
        return self._line.text().strip()

    def _emit_path(self) -> None:
        self.path_changed.emit(self.path())

    def _browse(self) -> None:
        from PySide6.QtWidgets import QFileDialog

        folder = QFileDialog.getExistingDirectory(self, "Select Source Folder", self.path())
        if folder:
            self.set_path(folder)

    def _drag_enter(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def _drop(self, event: QDropEvent) -> None:
        for url in event.mimeData().urls():
            p = Path(url.toLocalFile())
            target = p if p.is_dir() else p.parent
            if target and target.is_dir():
                self.set_path(str(target))
                break
        event.acceptProposedAction()
