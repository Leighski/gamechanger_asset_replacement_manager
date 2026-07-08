"""Production reports panel."""

from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QFrame, QLabel, QPushButton, QTextEdit, QVBoxLayout

from models.production import ProductionReportType
from services.projects_manager import ProjectsManager
from ui.theme import Theme
from ui.typography import Typography


class ProductionReportsPanel(QFrame):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._projects: ProjectsManager | None = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(Theme.SPACING_LG, Theme.SPACING_LG, Theme.SPACING_LG, Theme.SPACING_LG)
        heading = QLabel("Production Reports")
        heading.setFont(Typography.heading())
        layout.addWidget(heading)

        self._report_type = QComboBox()
        for report_type in ProductionReportType:
            self._report_type.addItem(report_type.value, report_type)
        layout.addWidget(self._report_type)

        generate = QPushButton("Generate Report")
        generate.clicked.connect(self._generate)
        layout.addWidget(generate)

        self._output = QTextEdit()
        self._output.setReadOnly(True)
        layout.addWidget(self._output, stretch=1)

    def set_services(self, projects: ProjectsManager) -> None:
        self._projects = projects

    def _generate(self) -> None:
        if self._projects is None or self._projects.production_manager is None:
            return
        report_type = self._report_type.currentData()
        metrics = self._projects.production_manager.metrics.metrics()
        dashboard = self._projects.production_manager.queue.dashboard_stats()
        report = self._projects.production_manager.reports.generate(
            report_type,
            dashboard=dashboard,
            metrics=metrics,
        )
        path = self._projects.production_manager.reports.save_report(report)
        import json

        self._output.setPlainText(json.dumps(report.model_dump(mode="json"), indent=2))
        self._output.append(f"\n\nSaved to: {path}")
