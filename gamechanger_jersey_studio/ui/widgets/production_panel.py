"""Production panel — queue, dashboard, reports, and settings tabs."""

from __future__ import annotations

from PySide6.QtWidgets import QFrame, QTabWidget, QVBoxLayout

from services.projects_manager import ProjectsManager
from ui.widgets.production_dashboard_panel import ProductionDashboardPanel
from ui.widgets.production_queue_panel import ProductionQueuePanel
from ui.widgets.production_reports_panel import ProductionReportsPanel
from ui.widgets.production_settings_panel import ProductionSettingsPanel


class ProductionPanel(QFrame):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._tabs = QTabWidget()
        self._queue = ProductionQueuePanel()
        self._dashboard = ProductionDashboardPanel()
        self._reports = ProductionReportsPanel()
        self._settings = ProductionSettingsPanel()
        self._tabs.addTab(self._queue, "Queue")
        self._tabs.addTab(self._dashboard, "Dashboard")
        self._tabs.addTab(self._reports, "Reports")
        self._tabs.addTab(self._settings, "Settings")
        layout.addWidget(self._tabs)

    @property
    def queue_panel(self) -> ProductionQueuePanel:
        return self._queue

    def set_services(self, projects: ProjectsManager) -> None:
        self._queue.set_services(projects)
        self._dashboard.set_services(projects)
        self._reports.set_services(projects)
        self._settings.set_services(projects)

    def show_settings_tab(self) -> None:
        self._tabs.setCurrentIndex(3)

    def show_queue_tab(self) -> None:
        self._tabs.setCurrentIndex(0)

    def refresh(self) -> None:
        self._queue.refresh()
        self._dashboard.refresh()
        self._settings.refresh()
