"""Learning Rule Browser — search, filter, enable, disable, export."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from models.learning import LearningRuleCategory, LearningRuleStatus
from services.projects_manager import ProjectsManager
from ui.theme import Theme
from ui.typography import Typography


class LearningRuleBrowserPanel(QFrame):
    rule_selected = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._learning = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(Theme.SPACING_LG, Theme.SPACING_LG, Theme.SPACING_LG, Theme.SPACING_LG)
        heading = QLabel("Rule Browser")
        heading.setFont(Typography.heading())
        layout.addWidget(heading)

        filters = QHBoxLayout()
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search rules…")
        self._category = QComboBox()
        self._category.addItem("All categories", "")
        for cat in LearningRuleCategory:
            self._category.addItem(cat.value, cat)
        filters.addWidget(self._search)
        filters.addWidget(self._category)
        layout.addLayout(filters)

        actions = QHBoxLayout()
        for label, slot in (
            ("Enable", self._enable_selected),
            ("Disable", self._disable_selected),
            ("Duplicate", self._duplicate_selected),
            ("Delete", self._delete_selected),
            ("Export KB", self._export_kb),
            ("Import KB", self._import_kb),
        ):
            btn = QPushButton(label)
            btn.clicked.connect(slot)
            actions.addWidget(btn)
        actions.addStretch(1)
        layout.addLayout(actions)

        self._table = QTableWidget(0, 6)
        self._table.setHorizontalHeaderLabels(
            ["Title", "Category", "Status", "Confidence", "Usage", "Created By"]
        )
        self._table.itemSelectionChanged.connect(self._on_select)
        layout.addWidget(self._table, stretch=1)

        self._search.textChanged.connect(self.refresh)
        self._category.currentIndexChanged.connect(self.refresh)

    def set_services(self, projects: ProjectsManager) -> None:
        self._learning = projects.learning_manager

    def refresh(self) -> None:
        if self._learning is None:
            return
        query = self._search.text().strip()
        cat = self._category.currentData()
        rules = self._learning.rules.search(query, category=cat if cat else None)
        self._table.setRowCount(len(rules))
        for row, rule in enumerate(rules):
            values = [
                rule.title,
                rule.category.value,
                rule.status.value,
                f"{rule.confidence:.0f}%",
                str(rule.usage_count),
                rule.created_by or "—",
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, rule.rule_id)
                self._table.setItem(row, col, item)

    def _selected_id(self) -> str | None:
        items = self._table.selectedItems()
        if not items:
            return None
        return items[0].data(Qt.ItemDataRole.UserRole)

    def _on_select(self) -> None:
        rule_id = self._selected_id()
        if rule_id:
            self.rule_selected.emit(rule_id)

    def _enable_selected(self) -> None:
        rule_id = self._selected_id()
        if rule_id and self._learning:
            self._learning.approve_rule(rule_id)
            self.refresh()

    def _disable_selected(self) -> None:
        rule_id = self._selected_id()
        if rule_id and self._learning:
            self._learning.disable_rule(rule_id)
            self.refresh()

    def _duplicate_selected(self) -> None:
        rule_id = self._selected_id()
        if rule_id and self._learning:
            self._learning.rules.duplicate(rule_id)
            self.refresh()

    def _delete_selected(self) -> None:
        rule_id = self._selected_id()
        if rule_id and self._learning:
            self._learning.rules.delete(rule_id)
            self.refresh()

    def _export_kb(self) -> None:
        if not self._learning:
            return
        from core.paths import REPORTS_DIR

        path = REPORTS_DIR / "gamechanger_knowledge_base_export.json"
        self._learning.export_knowledge_base(path)
        QMessageBox.information(self, "Export", f"Knowledge Base exported to:\n{path}")

    def _import_kb(self) -> None:
        if not self._learning:
            return
        from core.paths import KNOWLEDGE_BASE_PATH

        self._learning.import_knowledge_base(KNOWLEDGE_BASE_PATH, merge=True)
        self.refresh()
        QMessageBox.information(self, "Import", "Knowledge Base merged from default path.")
