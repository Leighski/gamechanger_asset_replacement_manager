"""Sortable, filterable data table with status icons."""

from __future__ import annotations

from PySide6.QtCore import Qt, QSortFilterProxyModel
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from gui.theme import Theme

ICON_OK = "✓"
ICON_WARN = "⚠"
ICON_ERR = "✕"
ICON_SKIP = "○"


class DataTable(QWidget):
    """Table with search filter, column sort, and alternating rows."""

    def __init__(
        self,
        columns: list[str],
        *,
        mono_columns: set[int] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._mono_cols = mono_columns or set()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Search"))
        self._search = QLineEdit()
        self._search.setPlaceholderText("Filter rows…")
        self._search.textChanged.connect(self._apply_filter)
        filter_row.addWidget(self._search, stretch=1)
        layout.addLayout(filter_row)

        self._model = QStandardItemModel(0, len(columns))
        self._model.setHorizontalHeaderLabels(columns)

        self._proxy = QSortFilterProxyModel()
        self._proxy.setSourceModel(self._model)
        self._proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._proxy.setSortCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

        self._view = QTableView()
        self._view.setModel(self._proxy)
        self._view.setSortingEnabled(True)
        self._view.setAlternatingRowColors(True)
        self._view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._view.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self._view.verticalHeader().setVisible(False)
        self._view.horizontalHeader().setStretchLastSection(True)
        self._view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self._view.setShowGrid(False)
        self._view.setMinimumHeight(280)
        layout.addWidget(self._view)

    def _apply_filter(self, text: str) -> None:
        self._proxy.setFilterFixedString(text)

    def clear(self) -> None:
        self._search.blockSignals(True)
        self._search.clear()
        self._search.blockSignals(False)
        self._proxy.setFilterFixedString("")
        self._model.removeRows(0, self._model.rowCount())

    def row_count(self) -> int:
        return self._model.rowCount()

    def set_row(self, row: int, values: list[str], *, status_icon: str | None = None) -> None:
        for col, value in enumerate(values):
            item = QStandardItem(value)
            item.setEditable(False)
            if col in self._mono_cols:
                item.setFont(self._view.font())
            if status_icon and col == 0:
                item.setText(f"{status_icon}  {value}")
            self._model.setItem(row, col, item)

    def append_row(self, values: list[str], *, status_icon: str | None = None) -> int:
        row = self._model.rowCount()
        self._model.insertRow(row)
        self.set_row(row, values, status_icon=status_icon)
        self._view.resizeColumnsToContents()
        return row

    def resize_columns(self) -> None:
        self._view.resizeColumnsToContents()
