"""Recent projects panel."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from models.settings import RecentProjectEntry
from ui.theme import Theme


class RecentProjectsPanel(QFrame):
    open_requested = Signal(str)
    remove_requested = Signal(str)
    duplicate_requested = Signal(str)
    archive_requested = Signal(str)

    _COLUMNS = ("Project Name", "Club", "Season", "Last Opened", "Thumbnail")

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        title = QLabel("Recent Projects")
        title.setProperty("title", True)
        subtitle = QLabel("Open a recent project or create a new one from the File menu.")
        subtitle.setProperty("muted", True)

        self._table = QTableWidget(0, len(self._COLUMNS))
        self._table.setHorizontalHeaderLabels(list(self._COLUMNS))
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        self._table.setShowGrid(False)
        self._table.setStyleSheet(
            f"""
            QTableWidget {{
                background: {Theme.PANEL};
                border: 1px solid {Theme.BORDER_SUBTLE};
                border-radius: 6px;
            }}
            QHeaderView::section {{
                background: {Theme.PANEL_ELEVATED};
                color: {Theme.TEXT_MUTED};
                border: none;
                padding: 8px;
            }}
            """
        )

        actions = QHBoxLayout()
        self._open_btn = QPushButton("Open")
        self._remove_btn = QPushButton("Remove From Recent")
        self._reveal_btn = QPushButton("Reveal in Finder")
        self._duplicate_btn = QPushButton("Duplicate")
        self._archive_btn = QPushButton("Archive")
        for btn in (
            self._open_btn,
            self._remove_btn,
            self._reveal_btn,
            self._duplicate_btn,
            self._archive_btn,
        ):
            actions.addWidget(btn)
        actions.addStretch(1)

        self._open_btn.clicked.connect(self._emit_open)
        self._remove_btn.clicked.connect(self._emit_remove)
        self._reveal_btn.clicked.connect(self._emit_reveal)
        self._duplicate_btn.clicked.connect(self._emit_duplicate)
        self._archive_btn.clicked.connect(self._emit_archive)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(self._table, stretch=1)
        layout.addLayout(actions)

    def set_entries(self, entries: list[RecentProjectEntry]) -> None:
        self._table.setRowCount(len(entries))
        for row, entry in enumerate(entries):
            values = (
                entry.name or Path(entry.path).stem,
                entry.club or "—",
                entry.season or "—",
                entry.last_opened or "—",
                "◻",
            )
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, entry.path)
                if col == 4:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self._table.setItem(row, col, item)
        self._table.resizeColumnsToContents()

    def _selected_path(self) -> str | None:
        row = self._table.currentRow()
        if row < 0:
            return None
        item = self._table.item(row, 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _emit_open(self) -> None:
        path = self._selected_path()
        if path:
            self.open_requested.emit(path)

    def _emit_remove(self) -> None:
        path = self._selected_path()
        if path:
            self.remove_requested.emit(path)

    def _emit_duplicate(self) -> None:
        path = self._selected_path()
        if path:
            self.duplicate_requested.emit(path)

    def _emit_archive(self) -> None:
        path = self._selected_path()
        if path:
            self.archive_requested.emit(path)

    def _emit_reveal(self) -> None:
        path = self._selected_path()
        if not path:
            return
        target = Path(path)
        folder = target.parent if target.is_file() else target
        if sys.platform == "darwin":
            subprocess.run(["open", str(folder)], check=False)
        elif sys.platform.startswith("win"):
            subprocess.run(["explorer", str(folder)], check=False)
        else:
            subprocess.run(["xdg-open", str(folder)], check=False)
