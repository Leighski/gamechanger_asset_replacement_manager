"""Batch render worker — background sequential PSD rendering."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal

from models.production import BatchRenderJob, ProductionQueueItem
from models.psd_render import PSDRenderProgress, PSDRenderResult
from services.project_format import read_project_package
from services.projects_manager import ProjectsManager


class BatchRenderWorker(QObject):
    progress = Signal(object, object)  # BatchRenderJob, PSDRenderProgress
    job_finished = Signal(object, object)  # BatchRenderJob, PSDRenderResult
    batch_finished = Signal(list)
    error = Signal(str)

    def __init__(self, projects: ProjectsManager, queue_items: list[ProductionQueueItem]) -> None:
        super().__init__()
        self._projects = projects
        self._items = queue_items

    def run(self) -> None:
        renderer = self._projects.psd_renderer_service
        renderer.queue.clear()
        for item in self._items:
            try:
                document, blobs = read_project_package(item.project_path)
                document.file_path = item.project_path
                renderer.enqueue(document)
            except Exception as exc:
                self.error.emit(f"Failed to load {item.project_name}: {exc}")
                return

        def on_progress(job: BatchRenderJob, progress: PSDRenderProgress | None) -> None:
            if progress is not None:
                self.progress.emit(job, progress)

        def on_job(job: BatchRenderJob, result: PSDRenderResult) -> None:
            self.job_finished.emit(job, result)
            if result.success and self._projects.production_manager is not None:
                self._projects.production_manager.metrics.record_render_time(job.elapsed_ms)

        results = renderer.process_batch(
            progress_callback=on_progress,
            job_callback=on_job,
        )
        self.batch_finished.emit(results)
