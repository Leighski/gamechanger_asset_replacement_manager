"""Benchmark dataset management for RC1 validation."""

from __future__ import annotations

import json
from pathlib import Path

from core.paths import BENCHMARK_DIR, BENCHMARK_LIBRARY_PATH
from models.validation import BenchmarkLibrary, BenchmarkProject
from services.logging_manager import get_logger

logger = get_logger()


class BenchmarkService:
    """Load, save, and manage RC1 benchmark projects."""

    def __init__(self, library_path: Path | None = None) -> None:
        self._path = library_path or BENCHMARK_LIBRARY_PATH
        self._library = BenchmarkLibrary()

    @property
    def library(self) -> BenchmarkLibrary:
        return self._library

    def load(self) -> BenchmarkLibrary:
        BENCHMARK_DIR.mkdir(parents=True, exist_ok=True)
        if not self._path.is_file():
            self._library = BenchmarkLibrary()
            return self._library
        raw = json.loads(self._path.read_text(encoding="utf-8"))
        self._library = BenchmarkLibrary.model_validate(raw)
        logger.info("Benchmark library loaded — {} projects", len(self._library.projects))
        return self._library

    def save(self, path: Path | None = None) -> Path:
        BENCHMARK_DIR.mkdir(parents=True, exist_ok=True)
        target = path or self._path
        target.write_text(
            json.dumps(self._library.model_dump(mode="json"), indent=2),
            encoding="utf-8",
        )
        logger.info("Benchmark library saved — {}", target.name)
        return target

    def add_project(self, project: BenchmarkProject) -> BenchmarkProject:
        existing = {p.benchmark_id for p in self._library.projects}
        if project.benchmark_id in existing:
            self._library.projects = [
                p if p.benchmark_id != project.benchmark_id else project
                for p in self._library.projects
            ]
        else:
            self._library.projects.append(project)
        return project

    def get_project(self, benchmark_id: str) -> BenchmarkProject | None:
        for project in self._library.projects:
            if project.benchmark_id == benchmark_id:
                return project
        return None

    def remove_project(self, benchmark_id: str) -> bool:
        before = len(self._library.projects)
        self._library.projects = [p for p in self._library.projects if p.benchmark_id != benchmark_id]
        return len(self._library.projects) < before

    def import_library(self, path: Path) -> BenchmarkLibrary:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        imported = BenchmarkLibrary.model_validate(raw)
        by_id = {p.benchmark_id: p for p in self._library.projects}
        for project in imported.projects:
            by_id[project.benchmark_id] = project
        self._library.projects = list(by_id.values())
        return self._library

    def export_library(self, path: Path) -> Path:
        path = Path(path)
        path.write_text(
            json.dumps(self._library.model_dump(mode="json"), indent=2),
            encoding="utf-8",
        )
        return path
