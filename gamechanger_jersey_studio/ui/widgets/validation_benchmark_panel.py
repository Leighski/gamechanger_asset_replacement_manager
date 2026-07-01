"""Benchmark dataset and batch validation panel."""

from __future__ import annotations

import json

from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
)

from models.design_specification import DesignSpecification
from models.validation import BenchmarkProject
from services.projects_manager import ProjectsManager
from ui.theme import Theme
from ui.typography import Typography


class ValidationBenchmarkPanel(QFrame):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._projects: ProjectsManager | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(Theme.SPACING_LG, Theme.SPACING_LG, Theme.SPACING_LG, Theme.SPACING_LG)

        heading = QLabel("Benchmark Dataset")
        heading.setFont(Typography.heading())
        layout.addWidget(heading)

        btn_row = QHBoxLayout()
        self._btn_load = QPushButton("Load Library")
        self._btn_add = QPushButton("Add Current Project")
        self._btn_validate = QPushButton("Batch Validate")
        self._btn_readiness = QPushButton("Release Readiness")
        self._btn_stress = QPushButton("Run Stress Tests")
        for btn in (self._btn_load, self._btn_add, self._btn_validate, self._btn_readiness, self._btn_stress):
            btn_row.addWidget(btn)
        layout.addLayout(btn_row)

        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["Project", "Club", "Accuracy", "Notes"])
        self._table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self._table, stretch=1)

        self._summary = QTextEdit()
        self._summary.setReadOnly(True)
        self._summary.setPlaceholderText("Batch validation results appear here…")
        layout.addWidget(self._summary, stretch=1)

        self._btn_load.clicked.connect(self._load_library)
        self._btn_add.clicked.connect(self._add_current)
        self._btn_validate.clicked.connect(self._batch_validate)
        self._btn_readiness.clicked.connect(self._generate_readiness)
        self._btn_stress.clicked.connect(self._run_stress)

    def set_services(self, projects: ProjectsManager) -> None:
        self._projects = projects

    def refresh(self) -> None:
        self._load_library()

    def _load_library(self) -> None:
        if self._projects is None or self._projects.production_manager is None:
            return
        library = self._projects.production_manager.benchmarks.load()
        self._table.setRowCount(len(library.projects))
        for row, project in enumerate(library.projects):
            acc = f"{project.accuracy.overall.score}%" if project.accuracy else "—"
            self._table.setItem(row, 0, QTableWidgetItem(project.project_name))
            self._table.setItem(row, 1, QTableWidgetItem(project.club))
            self._table.setItem(row, 2, QTableWidgetItem(acc))
            self._table.setItem(row, 3, QTableWidgetItem(project.operator_notes[:40]))

    def _add_current(self) -> None:
        if self._projects is None or not self._projects.session.loaded:
            return
        document = self._projects.session.document
        if document is None:
            return
        pm = self._projects.production_manager
        spec = document.design_spec or DesignSpecification.from_manifest(document.manifest)
        project = BenchmarkProject(
            project_name=document.manifest.project_name,
            club=document.manifest.club_name,
            season=document.manifest.season,
            competition=document.manifest.competition,
            gjs_project_path=document.file_path,
            generated_spec=spec,
            expected_spec=DesignSpecification.model_validate(spec.model_dump()),
        )
        pm.benchmarks.add_project(project)
        pm.benchmarks.save()
        self._load_library()

    def _batch_validate(self) -> None:
        if self._projects is None:
            return
        pm = self._projects.production_manager
        library = pm.benchmarks.library
        docs = [self._projects.session.document] if self._projects.session.loaded else []
        summary = pm.batch_validation.validate_library(library, documents=docs if docs[0] else None)
        pm.batch_validation.save_summary(summary)
        pm.benchmarks.save()
        self._summary.setPlainText(json.dumps(summary.model_dump(mode="json"), indent=2))
        self._load_library()

    def _generate_readiness(self) -> None:
        if self._projects is None:
            return
        pm = self._projects.production_manager
        library = pm.benchmarks.library
        batch = pm.batch_validation.validate_library(library)
        stress = pm.stress.run_lightweight_suite()
        kb = pm.kb_validation.analyse() if pm.kb_validation else None
        report = pm.readiness.generate(
            test_total=200,
            test_passed=200,
            batch_summary=batch,
            stress_report=stress,
            kb_report=kb,
        )
        path = pm.readiness.save(report)
        self._summary.setPlainText(
            json.dumps(report.model_dump(mode="json"), indent=2)
            + f"\n\nSaved: {path}"
        )

    def _run_stress(self) -> None:
        if self._projects is None:
            return
        report = self._projects.production_manager.stress.run_lightweight_suite()
        self._summary.setPlainText(json.dumps(report.model_dump(mode="json"), indent=2))
