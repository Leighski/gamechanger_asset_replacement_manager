"""Learning Mode panel — dashboard, rule browser, and inspector."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QSplitter, QTabWidget, QVBoxLayout

from services.projects_manager import ProjectsManager
from ui.widgets.learning_dashboard_panel import LearningDashboardPanel
from ui.widgets.learning_rule_browser_panel import LearningRuleBrowserPanel
from ui.widgets.learning_rule_inspector_panel import LearningRuleInspectorPanel


class LearningPanel(QFrame):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._tabs = QTabWidget()
        self._dashboard = LearningDashboardPanel()
        browser_page = QFrame()
        browser_layout = QVBoxLayout(browser_page)
        browser_layout.setContentsMargins(0, 0, 0, 0)
        splitter = QSplitter(Qt.Orientation.Vertical)
        self._browser = LearningRuleBrowserPanel()
        self._inspector = LearningRuleInspectorPanel()
        splitter.addWidget(self._browser)
        splitter.addWidget(self._inspector)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        browser_layout.addWidget(splitter)
        self._tabs.addTab(self._dashboard, "Dashboard")
        self._tabs.addTab(browser_page, "Rules")
        layout.addWidget(self._tabs)
        self._browser.rule_selected.connect(self._inspector.show_rule)

    def set_services(self, projects: ProjectsManager) -> None:
        self._dashboard.set_services(projects)
        self._browser.set_services(projects)
        self._inspector.set_services(projects)

    def refresh(self) -> None:
        self._dashboard.refresh()
        self._browser.refresh()
        self._inspector.clear()
