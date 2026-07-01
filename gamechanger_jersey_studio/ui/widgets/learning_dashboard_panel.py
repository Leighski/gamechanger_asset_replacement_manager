"""Learning Dashboard — aggregate learning mode statistics."""

from __future__ import annotations

from PySide6.QtWidgets import QFrame, QGridLayout, QLabel, QVBoxLayout

from services.projects_manager import ProjectsManager
from ui.theme import Theme
from ui.typography import Typography


class _StatCard(QFrame):
    def __init__(self, title: str, value: str = "—", parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("panelElevated")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(Theme.SPACING_MD, Theme.SPACING_MD, Theme.SPACING_MD, Theme.SPACING_MD)
        title_label = QLabel(title)
        title_label.setFont(Typography.caption())
        title_label.setStyleSheet(f"color: {Theme.TEXT_MUTED};")
        self._value = QLabel(value)
        self._value.setFont(Typography.heading())
        layout.addWidget(title_label)
        layout.addWidget(self._value)

    def set_value(self, value: str) -> None:
        self._value.setText(value)


class LearningDashboardPanel(QFrame):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._learning = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(Theme.SPACING_LG, Theme.SPACING_LG, Theme.SPACING_LG, Theme.SPACING_LG)
        heading = QLabel("Learning Dashboard")
        heading.setFont(Typography.heading())
        layout.addWidget(heading)
        hint = QLabel("Organisational knowledge — observes corrections, never changes specs automatically.")
        hint.setProperty("muted", True)
        hint.setWordWrap(True)
        layout.addWidget(hint)
        grid = QGridLayout()
        self._events = _StatCard("Learning Events", "0")
        self._active = _StatCard("Active Rules", "0")
        self._drafts = _StatCard("Draft Rules", "0")
        self._most_used = _StatCard("Most Used Rule", "—")
        self._frequent = _StatCard("Frequent Correction", "—")
        self._improved = _StatCard("Most Improved Field", "—")
        for i, card in enumerate(
            [self._events, self._active, self._drafts, self._most_used, self._frequent, self._improved]
        ):
            grid.addWidget(card, i // 3, i % 3)
        layout.addLayout(grid)
        layout.addStretch(1)

    def set_services(self, projects: ProjectsManager) -> None:
        self._learning = projects.learning_manager

    def refresh(self) -> None:
        if self._learning is None:
            return
        stats = self._learning.analytics.dashboard_stats()
        self._events.set_value(str(stats.total_events))
        self._active.set_value(str(stats.active_rules))
        self._drafts.set_value(str(stats.draft_rules))
        self._most_used.set_value(stats.most_used_rule or "—")
        self._frequent.set_value(
            stats.most_frequent_correction.split(":")[0] if stats.most_frequent_correction else "—"
        )
        self._improved.set_value(stats.most_improved_field or "—")
