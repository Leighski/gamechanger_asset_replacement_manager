"""RC1 Validation panel — review, workspace, replay, and benchmarks."""

from __future__ import annotations

from PySide6.QtWidgets import QFrame, QTabWidget, QVBoxLayout

from models.project import ProjectDocument
from services.projects_manager import ProjectsManager
from ui.widgets.production_replay_panel import ProductionReplayPanel
from ui.widgets.validation_benchmark_panel import ValidationBenchmarkPanel
from ui.widgets.validation_workspace_panel import ValidationWorkspacePanel
from ui.widgets.vision_analysis_review import VisionAnalysisReviewPanel


class ValidationPanel(QFrame):
    """Validation workspace for RC1 production benchmarking."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._tabs = QTabWidget()
        self._review = VisionAnalysisReviewPanel(parent)
        self._workspace = ValidationWorkspacePanel()
        self._replay = ProductionReplayPanel()
        self._benchmarks = ValidationBenchmarkPanel()
        self._tabs.addTab(self._review, "Review")
        self._tabs.addTab(self._workspace, "Workspace")
        self._tabs.addTab(self._replay, "Replay")
        self._tabs.addTab(self._benchmarks, "Benchmarks")
        layout.addWidget(self._tabs)

    @property
    def review_panel(self) -> VisionAnalysisReviewPanel:
        return self._review

    def set_services(self, projects: ProjectsManager) -> None:
        self._workspace.set_services(projects)
        self._replay.set_services(projects)
        self._benchmarks.set_services(projects)

    def set_review_services(self, vision, reference, interpretation, design) -> None:
        self._review.set_services(vision, reference, interpretation, design)

    def set_project(self, document: ProjectDocument | None) -> None:
        self._review.set_project(document)

    def run_analysis(self, image_id: str) -> None:
        self._review.run_analysis(image_id)

    def refresh(self, *, select_image_id: str | None = None) -> None:
        self._review.refresh(select_image_id=select_image_id)
        self._workspace.refresh()
        self._replay.refresh()
        self._benchmarks.refresh()
