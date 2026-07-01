"""Learning Rule Inspector — rule detail and analytics."""

from __future__ import annotations

from PySide6.QtWidgets import QFrame, QLabel, QTextEdit, QVBoxLayout

from services.projects_manager import ProjectsManager
from ui.theme import Theme
from ui.typography import Typography


class LearningRuleInspectorPanel(QFrame):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._learning = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(Theme.SPACING_LG, Theme.SPACING_LG, Theme.SPACING_LG, Theme.SPACING_LG)
        self._heading = QLabel("Rule Inspector")
        self._heading.setFont(Typography.heading())
        layout.addWidget(self._heading)
        self._detail = QTextEdit()
        self._detail.setReadOnly(True)
        layout.addWidget(self._detail, stretch=1)

    def set_services(self, projects: ProjectsManager) -> None:
        self._learning = projects.learning_manager

    def show_rule(self, rule_id: str) -> None:
        if self._learning is None:
            return
        rule = self._learning.rules.get(rule_id)
        if rule is None:
            self._detail.setPlainText("Rule not found.")
            return
        analytics = self._learning.analytics.rule_analytics(rule_id)
        lines = [
            f"# {rule.title}",
            f"ID: {rule.rule_id}",
            f"Status: {rule.status.value}",
            f"Category: {rule.category.value}",
            f"Confidence: {rule.confidence:.0f}%",
            "",
            "## Description",
            rule.description or "—",
            "",
            "## Trigger Conditions",
            f"Field: {rule.triggers.field_name or '—'}",
            f"Club: {rule.triggers.club or '—'}",
            f"Manufacturer: {rule.triggers.manufacturer or '—'}",
            f"Original value: {rule.triggers.original_value or '—'}",
            "",
            "## Recommended Action",
            f"Target: {rule.action.target_field}",
            f"Value: {rule.action.recommended_value or '—'}",
            f"Catalogue: {rule.action.catalogue_component or '—'}",
            f"Note: {rule.action.advisory_note or '—'}",
            f"Confidence boost: +{rule.action.confidence_boost:.0f}%",
            "",
            "## Operator Notes",
            rule.operator_notes or "—",
        ]
        if analytics:
            lines.extend(
                [
                    "",
                    "## Performance Statistics",
                    f"Usage count: {analytics.usage_count}",
                    f"Acceptance rate: {analytics.acceptance_rate:.1f}%",
                    f"Ignored: {analytics.ignored_count}",
                    f"Modification rate: {analytics.modification_rate:.1f}%",
                ]
            )
        self._detail.setPlainText("\n".join(lines))

    def clear(self) -> None:
        self._detail.setPlainText("Select a rule to inspect.")
