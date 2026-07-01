"""Production dashboard — aggregate workflow status."""

from __future__ import annotations

from PySide6.QtWidgets import QFrame, QGridLayout, QLabel, QVBoxLayout

from services.production_manager_service import ProductionManagerService
from services.projects_manager import ProjectsManager
from ui.theme import Theme
from ui.typography import Typography


class _StatCard(QFrame):
    def __init__(self, title: str, value: str = "—", parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("panelElevated")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(Theme.SPACING_MD, Theme.SPACING_MD, Theme.SPACING_MD, Theme.SPACING_MD)
        self._title = QLabel(title)
        self._title.setFont(Typography.caption())
        self._title.setStyleSheet(f"color: {Theme.TEXT_MUTED};")
        self._value = QLabel(value)
        self._value.setFont(Typography.heading())
        layout.addWidget(self._title)
        layout.addWidget(self._value)

    def set_value(self, value: str) -> None:
        self._value.setText(value)


class ProductionDashboardPanel(QFrame):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._production: ProductionManagerService | None = None
        self._psd_renderer = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(Theme.SPACING_LG, Theme.SPACING_LG, Theme.SPACING_LG, Theme.SPACING_LG)
        heading = QLabel("Production Dashboard")
        heading.setFont(Typography.heading())
        layout.addWidget(heading)

        grid = QGridLayout()
        grid.setSpacing(Theme.SPACING_MD)
        self._card_awaiting = _StatCard("Awaiting Review", "0")
        self._card_ready = _StatCard("Ready to Render", "0")
        self._card_rendering = _StatCard("Rendering", "0")
        self._card_completed = _StatCard("Completed", "0")
        self._card_failed = _StatCard("Failed", "0")
        self._card_confidence = _StatCard("Avg Confidence", "—")
        self._card_render_time = _StatCard("Avg Render Time", "—")
        cards = [
            self._card_awaiting,
            self._card_ready,
            self._card_rendering,
            self._card_completed,
            self._card_failed,
            self._card_confidence,
            self._card_render_time,
        ]
        for index, card in enumerate(cards):
            grid.addWidget(card, index // 3, index % 3)
        layout.addLayout(grid)
        layout.addStretch(1)

    def set_services(self, projects: ProjectsManager) -> None:
        self._production = projects.production_manager
        self._psd_renderer = projects.psd_renderer_service

    def refresh(self) -> None:
        if self._production is None:
            return
        rendering = 0
        if self._psd_renderer is not None and self._psd_renderer.queue.active:
            rendering = 1 if self._psd_renderer.queue.state.current_job_id else 0
        stats = self._production.queue.dashboard_stats(batch_rendering=rendering)
        metrics = self._production.metrics.metrics()
        self._card_awaiting.set_value(str(stats.awaiting_review))
        self._card_ready.set_value(str(stats.ready_to_render))
        self._card_rendering.set_value(str(stats.rendering))
        self._card_completed.set_value(str(stats.completed))
        self._card_failed.set_value(str(stats.failed))
        self._card_confidence.set_value(f"{stats.average_confidence:.0f}%")
        avg_render = metrics.average_render_time_ms or stats.average_render_time_ms
        self._card_render_time.set_value(f"{avg_render:.0f} ms" if avg_render else "—")
