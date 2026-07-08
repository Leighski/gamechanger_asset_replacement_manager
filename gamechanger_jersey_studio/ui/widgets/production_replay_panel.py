"""Production Replay viewer — step through the production chain."""

from __future__ import annotations

import json

from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from models.validation import ProductionReplay
from services.projects_manager import ProjectsManager
from ui.theme import Theme
from ui.typography import Typography


class ProductionReplayPanel(QFrame):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._projects: ProjectsManager | None = None
        self._replay: ProductionReplay | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(Theme.SPACING_LG, Theme.SPACING_LG, Theme.SPACING_LG, Theme.SPACING_LG)

        heading = QLabel("Production Replay")
        heading.setFont(Typography.heading())
        layout.addWidget(heading)

        hint = QLabel("Step through Reference Images → Vision → AI → Learning → Operator → Spec → Template → Render → Export")
        hint.setProperty("muted", True)
        hint.setWordWrap(True)
        layout.addWidget(hint)

        nav = QHBoxLayout()
        self._btn_back = QPushButton("◀ Previous")
        self._btn_forward = QPushButton("Next ▶")
        self._btn_rebuild = QPushButton("Rebuild Chain")
        nav.addWidget(self._btn_back)
        nav.addWidget(self._btn_forward)
        nav.addStretch(1)
        nav.addWidget(self._btn_rebuild)
        layout.addLayout(nav)

        self._step_list = QListWidget()
        layout.addWidget(self._step_list, stretch=1)

        self._detail = QTextEdit()
        self._detail.setReadOnly(True)
        self._detail.setPlaceholderText("Select a step to view details…")
        layout.addWidget(self._detail, stretch=2)

        self._btn_back.clicked.connect(self._step_back)
        self._btn_forward.clicked.connect(self._step_forward)
        self._btn_rebuild.clicked.connect(self.refresh)
        self._step_list.currentRowChanged.connect(self._on_step_selected)

    def set_services(self, projects: ProjectsManager) -> None:
        self._projects = projects

    def refresh(self) -> None:
        self._step_list.clear()
        self._detail.clear()
        if self._projects is None or not self._projects.session.loaded:
            return
        document = self._projects.session.document
        if document is None or self._projects.production_manager is None:
            return
        try:
            self._replay = self._projects.production_manager.replay.build_replay(document)
        except Exception as exc:
            from services.logging_manager import get_logger

            get_logger().warning("Production replay could not be built — {}", exc)
            from models.validation import ProductionReplay

            self._replay = ProductionReplay(
                project_name=document.manifest.project_name,
                project_path=document.file_path,
            )
        for step in self._replay.steps:
            item = QListWidgetItem(f"{step.stage.value} — {step.title}")
            self._step_list.addItem(item)
        if self._replay.steps:
            self._step_list.setCurrentRow(self._replay.current_step)
            self._show_step(self._replay.current_step)

    def _step_back(self) -> None:
        if self._replay is None or self._projects is None:
            return
        self._replay = self._projects.production_manager.replay.step_backward(self._replay)
        self._step_list.setCurrentRow(self._replay.current_step)

    def _step_forward(self) -> None:
        if self._replay is None or self._projects is None:
            return
        self._replay = self._projects.production_manager.replay.step_forward(self._replay)
        self._step_list.setCurrentRow(self._replay.current_step)

    def _on_step_selected(self, row: int) -> None:
        if self._replay is not None:
            self._replay.current_step = row
        self._show_step(row)

    def _show_step(self, row: int) -> None:
        if self._replay is None or row < 0 or row >= len(self._replay.steps):
            return
        step = self._replay.steps[row]
        payload = {
            "stage": step.stage.value,
            "title": step.title,
            "timestamp": step.timestamp,
            "summary": step.summary,
            "details": step.details,
        }
        self._detail.setPlainText(json.dumps(payload, indent=2, ensure_ascii=False))
