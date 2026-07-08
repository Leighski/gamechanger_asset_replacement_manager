"""Batch render progress dialog with pause, resume, cancel, and retry."""

from __future__ import annotations

from PySide6.QtCore import Qt, QThread
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from models.production import BatchRenderJob, BatchRenderJobStatus, ProductionQueueItem
from models.psd_render import PSDRenderProgress
from services.projects_manager import ProjectsManager
from ui.theme import Theme
from ui.typography import Typography
from ui.workers.batch_render_worker import BatchRenderWorker


class BatchRenderDialog(QDialog):
    def __init__(
        self,
        projects: ProjectsManager,
        queue_items: list[ProductionQueueItem],
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._projects = projects
        self._items = queue_items
        self._failed_jobs: list[BatchRenderJob] = []
        self.setWindowTitle("Batch Production Render")
        self.resize(560, 480)
        self._build_ui()
        self._start_worker()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(Theme.SPACING_XL, Theme.SPACING_XL, Theme.SPACING_XL, Theme.SPACING_XL)
        self._position = QLabel("Queue position: —")
        self._stage = QLabel("Current stage: —")
        self._elapsed = QLabel("Elapsed: 0 ms")
        self._remaining = QLabel("Estimated remaining: —")
        self._bar = QProgressBar()
        self._bar.setRange(0, max(1, len(self._items)))
        self._jobs = QListWidget()
        for item in self._items:
            self._jobs.addItem(f"Queued — {item.project_name}")
        layout.addWidget(self._position)
        layout.addWidget(self._stage)
        layout.addWidget(self._elapsed)
        layout.addWidget(self._remaining)
        layout.addWidget(self._bar)
        layout.addWidget(self._jobs, stretch=1)

        buttons = QHBoxLayout()
        self._btn_pause = QPushButton("Pause")
        self._btn_resume = QPushButton("Resume")
        self._btn_cancel = QPushButton("Cancel")
        self._btn_retry = QPushButton("Retry Failed")
        self._btn_close = QPushButton("Close")
        self._btn_resume.setEnabled(False)
        self._btn_retry.setEnabled(False)
        self._btn_close.setEnabled(False)
        for btn in (self._btn_pause, self._btn_resume, self._btn_cancel, self._btn_retry, self._btn_close):
            buttons.addWidget(btn)
        layout.addLayout(buttons)

        self._btn_pause.clicked.connect(self._pause)
        self._btn_resume.clicked.connect(self._resume)
        self._btn_cancel.clicked.connect(self._cancel)
        self._btn_retry.clicked.connect(self._retry_failed)
        self._btn_close.clicked.connect(self.accept)

    def _start_worker(self) -> None:
        self._thread = QThread(self)
        self._worker = BatchRenderWorker(self._projects, self._items)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_progress)
        self._worker.job_finished.connect(self._on_job_finished)
        self._worker.batch_finished.connect(self._on_batch_finished)
        self._worker.error.connect(self._on_error)
        self._thread.start()

    def _pause(self) -> None:
        self._projects.psd_renderer_service.pause_batch()
        self._btn_pause.setEnabled(False)
        self._btn_resume.setEnabled(True)

    def _resume(self) -> None:
        self._projects.psd_renderer_service.resume_batch()
        self._btn_pause.setEnabled(True)
        self._btn_resume.setEnabled(False)

    def _cancel(self) -> None:
        self._projects.psd_renderer_service.cancel_batch()

    def _retry_failed(self) -> None:
        for job in self._failed_jobs:
            self._projects.psd_renderer_service.retry_failed(job.job_id)

    def _on_progress(self, job: BatchRenderJob, progress: PSDRenderProgress) -> None:
        completed = self._projects.psd_renderer_service.queue.state.completed_count
        self._bar.setValue(completed)
        self._position.setText(f"Queue position: {job.position} — {job.project_name}")
        if progress.current_stage is not None:
            self._stage.setText(f"Current stage: {progress.current_stage.value}")
        self._elapsed.setText(f"Elapsed: {progress.elapsed_ms:.0f} ms")
        remaining = job.estimated_remaining_ms
        self._remaining.setText(
            f"Estimated remaining: {remaining:.0f} ms" if remaining else "Estimated remaining: —"
        )

    def _on_job_finished(self, job: BatchRenderJob, result) -> None:
        status = "OK" if result.success else "FAILED"
        self._jobs.addItem(f"{status} — {job.project_name} ({job.elapsed_ms:.0f} ms)")
        if not result.success:
            self._failed_jobs.append(job)
            self._btn_retry.setEnabled(True)

    def _on_batch_finished(self, results) -> None:
        self._btn_pause.setEnabled(False)
        self._btn_resume.setEnabled(False)
        self._btn_close.setEnabled(True)
        self._bar.setValue(self._bar.maximum())
        self._thread.quit()

    def _on_error(self, message: str) -> None:
        self._jobs.addItem(f"ERROR — {message}")
        self._btn_close.setEnabled(True)
        self._thread.quit()

    def closeEvent(self, event) -> None:  # noqa: N802
        self._projects.psd_renderer_service.cancel_batch()
        super().closeEvent(event)
