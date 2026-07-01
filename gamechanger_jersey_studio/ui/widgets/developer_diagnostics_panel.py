"""Developer diagnostics — integration state for Vision → Review → Preview."""

from __future__ import annotations

from PySide6.QtWidgets import QFrame, QFormLayout, QLabel

from ui.theme import Theme
from ui.typography import Typography


class DeveloperDiagnosticsPanel(QFrame):
    """Read-only integration status for development builds."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("panel")
        self.setStyleSheet(
            f"QFrame#panel {{ border: 1px dashed {Theme.WARNING}; border-radius: {Theme.RADIUS_SM}px; }}"
        )
        layout = QFormLayout(self)
        layout.setContentsMargins(Theme.SPACING_SM, Theme.SPACING_SM, Theme.SPACING_SM, Theme.SPACING_SM)

        heading = QLabel("Developer Diagnostics")
        heading.setFont(Typography.caption())
        heading.setStyleSheet(f"color: {Theme.WARNING};")
        layout.addRow(heading)

        self._project = QLabel("—")
        self._reference = QLabel("—")
        self._vision = QLabel("No")
        self._ai = QLabel("No")
        self._spec = QLabel("No")
        self._renderer = QLabel("No")

        for label in (
            self._project,
            self._reference,
            self._vision,
            self._ai,
            self._spec,
            self._renderer,
        ):
            label.setFont(Typography.caption())

        layout.addRow("Current project:", self._project)
        layout.addRow("Selected reference:", self._reference)
        layout.addRow("VisionAnalysisResult loaded:", self._vision)
        layout.addRow("AI Interpretation ready:", self._ai)
        layout.addRow("Design Specification loaded:", self._spec)
        layout.addRow("Renderer ready:", self._renderer)

    def update_state(
        self,
        *,
        project_name: str,
        reference_image: str,
        vision_loaded: bool,
        ai_ready: bool,
        spec_loaded: bool,
        renderer_ready: bool,
    ) -> None:
        self._project.setText(project_name or "—")
        self._reference.setText(reference_image or "—")
        self._vision.setText("Yes" if vision_loaded else "No")
        self._ai.setText("Yes" if ai_ready else "No")
        self._spec.setText("Yes" if spec_loaded else "No")
        self._renderer.setText("Yes" if renderer_ready else "No")
