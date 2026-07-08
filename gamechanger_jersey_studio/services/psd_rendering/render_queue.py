"""PSD Render Queue — sequential multi-project rendering with pause/cancel."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from threading import Lock

from models.production import BatchRenderJob, BatchRenderJobStatus, BatchRenderState
from models.project import ProjectDocument


@dataclass
class PSDRenderQueue:
    """Queue PSD render jobs — sequential processing with cooperative control."""

    _pending: deque[BatchRenderJob] = field(default_factory=deque)
    _lock: Lock = field(default_factory=Lock)
    _state: BatchRenderState = field(default_factory=BatchRenderState)
    _documents: dict[str, ProjectDocument] = field(default_factory=dict)

    def enqueue(self, document: ProjectDocument) -> BatchRenderJob:
        with self._lock:
            job = BatchRenderJob(
                project_path=document.file_path or "",
                project_name=document.manifest.project_name,
                position=len(self._pending) + 1,
            )
            self._pending.append(job)
            self._documents[job.job_id] = document
            return job

    def enqueue_job(self, job: BatchRenderJob, document: ProjectDocument) -> None:
        with self._lock:
            job.position = len(self._pending) + 1
            self._pending.append(job)
            self._documents[job.job_id] = document

    def dequeue(self) -> BatchRenderJob | None:
        with self._lock:
            if self._state.paused or self._state.cancelled:
                return None
            if not self._pending:
                return None
            job = self._pending.popleft()
            job.status = BatchRenderJobStatus.RUNNING
            self._state.current_job_id = job.job_id
            return job

    def document_for(self, job_id: str) -> ProjectDocument | None:
        with self._lock:
            return self._documents.get(job_id)

    def complete_job(self, job: BatchRenderJob) -> None:
        with self._lock:
            job.status = BatchRenderJobStatus.COMPLETED
            self._state.completed_count += 1
            self._state.current_job_id = ""
            self._update_average(job.elapsed_ms)

    def fail_job(self, job: BatchRenderJob, error: str) -> None:
        with self._lock:
            job.status = BatchRenderJobStatus.FAILED
            job.error = error
            self._state.failed_count += 1
            self._state.current_job_id = ""

    def retry_job(self, job_id: str) -> BatchRenderJob | None:
        with self._lock:
            for job in list(self._pending):
                if job.job_id == job_id:
                    return job
            for job in self._state.jobs:
                if job.job_id == job_id and job.status == BatchRenderJobStatus.FAILED:
                    retry = job.model_copy(
                        update={
                            "status": BatchRenderJobStatus.QUEUED,
                            "error": "",
                            "retry_count": job.retry_count + 1,
                        }
                    )
                    document = self._documents.get(job_id)
                    if document is not None:
                        self._pending.append(retry)
                        self._documents[retry.job_id] = document
                    return retry
        return None

    def pause(self) -> None:
        with self._lock:
            self._state.paused = True

    def resume(self) -> None:
        with self._lock:
            self._state.paused = False

    def cancel(self) -> None:
        with self._lock:
            self._state.cancelled = True
            self._state.paused = False
            self._pending.clear()

    def clear(self) -> None:
        with self._lock:
            self._pending.clear()
            self._documents.clear()
            self._state = BatchRenderState()

    def start_batch(self) -> None:
        with self._lock:
            self._state.active = True
            self._state.paused = False
            self._state.cancelled = False
            self._state.jobs = list(self._pending)

    def end_batch(self) -> None:
        with self._lock:
            self._state.active = False
            self._state.current_job_id = ""

    @property
    def state(self) -> BatchRenderState:
        with self._lock:
            return self._state.model_copy(deep=True)

    @property
    def size(self) -> int:
        with self._lock:
            return len(self._pending)

    @property
    def active(self) -> bool:
        with self._lock:
            return self._state.active

    def set_active(self, value: bool) -> None:
        with self._lock:
            self._state.active = value

    def is_cancelled(self) -> bool:
        with self._lock:
            return self._state.cancelled

    def is_paused(self) -> bool:
        with self._lock:
            return self._state.paused

    def estimate_remaining_ms(self) -> float:
        with self._lock:
            if self._state.average_render_ms <= 0:
                return 0.0
            return self._state.average_render_ms * len(self._pending)

    def _update_average(self, elapsed_ms: float) -> None:
        count = self._state.completed_count
        if count <= 1:
            self._state.average_render_ms = elapsed_ms
        else:
            prev = self._state.average_render_ms
            self._state.average_render_ms = round(
                prev + (elapsed_ms - prev) / count, 2
            )
