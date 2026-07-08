"""Production settings — configurable confidence thresholds."""

from __future__ import annotations

from PySide6.QtWidgets import QDoubleSpinBox, QFormLayout, QFrame, QLabel, QPushButton, QVBoxLayout

from models.production import ConfidenceThresholds
from services.production_manager_service import ProductionManagerService
from services.projects_manager import ProjectsManager
from ui.theme import Theme
from ui.typography import Typography


class ProductionSettingsPanel(QFrame):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._production: ProductionManagerService | None = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(Theme.SPACING_LG, Theme.SPACING_LG, Theme.SPACING_LG, Theme.SPACING_LG)

        heading = QLabel("Confidence Configuration")
        heading.setFont(Typography.heading())
        layout.addWidget(heading)

        hint = QLabel(
            "Trusted: suggestions auto-eligible for bulk accept.\n"
            "Review: operator should verify before accepting.\n"
            "Manual Review Required: never auto-selected."
        )
        hint.setProperty("muted", True)
        hint.setWordWrap(True)
        layout.addWidget(hint)

        form = QFormLayout()
        self._trusted = QDoubleSpinBox()
        self._trusted.setRange(0, 100)
        self._trusted.setValue(95.0)
        self._review = QDoubleSpinBox()
        self._review.setRange(0, 100)
        self._review.setValue(85.0)
        form.addRow("Trusted minimum (%)", self._trusted)
        form.addRow("Review minimum (%)", self._review)
        layout.addLayout(form)

        save = QPushButton("Save Thresholds")
        save.clicked.connect(self._save)
        layout.addWidget(save)
        layout.addStretch(1)

    def set_services(self, projects: ProjectsManager) -> None:
        self._production = projects.production_manager
        self.refresh()

    def refresh(self) -> None:
        if self._production is None:
            return
        thresholds = self._production.confidence.thresholds
        self._trusted.setValue(thresholds.trusted_min)
        self._review.setValue(thresholds.review_min)

    def _save(self) -> None:
        if self._production is None:
            return
        thresholds = ConfidenceThresholds(
            trusted_min=self._trusted.value(),
            review_min=self._review.value(),
        )
        self._production.update_thresholds(thresholds)
