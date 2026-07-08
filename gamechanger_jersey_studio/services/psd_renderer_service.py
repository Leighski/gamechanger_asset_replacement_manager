"""PSD Renderer Service — project integration, history, and batch queue."""

from __future__ import annotations

import time
from typing import Callable

from models.design_specification import DesignSpecification
from models.production import BatchRenderJob, BatchRenderJobStatus
from models.project import HistoryEventType, ProjectDocument
from models.psd_render import PSDRenderProgress, PSDRenderResult
from services.catalogue_manager_service import CatalogueManagerService
from services.logging_manager import get_logger
from services.production.audit_service import ProductionAuditService
from services.project_history_service import ProjectHistoryService
from services.psd_rendering.psd_render_service import PSDRenderService
from services.psd_rendering.render_queue import PSDRenderQueue
from services.template_manager_service import TemplateManagerService

logger = get_logger()


class PSDRendererService:
    """Orchestrate production PSD rendering for open projects."""

    def __init__(
        self,
        templates: TemplateManagerService,
        catalogue: CatalogueManagerService,
        history: ProjectHistoryService,
        *,
        application_version: str = "",
        audit: ProductionAuditService | None = None,
    ) -> None:
        self._templates = templates
        self._renderer = PSDRenderService(templates.manager, catalogue)
        self._history = history
        self._application_version = application_version
        self._audit = audit or ProductionAuditService(history)
        self._queue = PSDRenderQueue()

    @property
    def queue(self) -> PSDRenderQueue:
        return self._queue

    @property
    def engine(self) -> PSDRenderService:
        return self._renderer

    @property
    def audit(self) -> ProductionAuditService:
        return self._audit

    def enqueue(self, document: ProjectDocument) -> BatchRenderJob:
        return self._queue.enqueue(document)

    def render_document(
        self,
        document: ProjectDocument,
        *,
        user: str = "Operator",
        progress_callback=None,
        cancel_check: Callable[[], bool] | None = None,
    ) -> PSDRenderResult:
        self._history.record(
            document,
            HistoryEventType.RENDER_STARTED,
            application_version=self._application_version,
            user=user,
            details=document.manifest.project_name,
        )
        logger.info("Render started — project={}", document.manifest.project_name)

        spec = document.design_spec or DesignSpecification.from_manifest(document.manifest)
        mappings = self._templates.published_mappings(document)
        if mappings is None:
            result = PSDRenderResult(success=False, error="No published template mappings for project")
            self._history.record(
                document,
                HistoryEventType.RENDER_FAILED,
                application_version=self._application_version,
                user=user,
                details=result.error,
            )
            return result

        result = self._renderer.render(
            spec,
            mappings,
            project_name=document.manifest.project_name,
            output_folder=document.manifest.output_folder,
            progress_callback=progress_callback,
            cancel_check=cancel_check,
        )

        if result.success:
            self._history.record(
                document,
                HistoryEventType.RENDER_COMPLETED,
                application_version=self._application_version,
                user=user,
                details=f"{result.log.total_ms:.1f}ms",
            )
            self._history.record(
                document,
                HistoryEventType.PSD_SAVED,
                application_version=self._application_version,
                user=user,
                details=result.psd_path,
            )
            self._history.record(
                document,
                HistoryEventType.PNG_GENERATED,
                application_version=self._application_version,
                user=user,
                details=result.png_path,
            )
            audit_record = self._audit.build_chain(
                document,
                render_psd_path=result.psd_path,
                render_png_path=result.png_path,
                template_id=mappings.template_id,
                template_version=mappings.template_version,
                render_log_path=result.log_path,
            )
            self._audit.record_audit(
                document,
                audit_record,
                user=user,
                application_version=self._application_version,
            )
            logger.info("Render completed — {}", result.psd_path)
        else:
            self._history.record(
                document,
                HistoryEventType.RENDER_FAILED,
                application_version=self._application_version,
                user=user,
                details=result.error,
            )
            logger.error("Render failed — {}", result.error)
        return result

    def process_batch(
        self,
        *,
        user: str = "Operator",
        progress_callback: Callable[[BatchRenderJob, PSDRenderProgress | None], None] | None = None,
        job_callback: Callable[[BatchRenderJob, PSDRenderResult], None] | None = None,
    ) -> list[PSDRenderResult]:
        results: list[PSDRenderResult] = []
        self._queue.start_batch()
        self._history_batch_event(None, HistoryEventType.BATCH_RENDER_STARTED, user, "")
        try:
            while not self._queue.is_cancelled():
                while self._queue.is_paused() and not self._queue.is_cancelled():
                    time.sleep(0.05)
                job = self._queue.dequeue()
                if job is None:
                    if self._queue.size == 0:
                        break
                    time.sleep(0.05)
                    continue
                document = self._queue.document_for(job.job_id)
                if document is None:
                    self._queue.fail_job(job, "Project document not found")
                    continue
                started = time.perf_counter()

                def on_progress(progress: PSDRenderProgress) -> None:
                    if progress_callback:
                        progress_callback(job, progress)

                result = self.render_document(
                    document,
                    user=user,
                    progress_callback=on_progress,
                    cancel_check=self._queue.is_cancelled,
                )
                job.elapsed_ms = round((time.perf_counter() - started) * 1000.0, 2)
                job.estimated_remaining_ms = self._queue.estimate_remaining_ms()
                if result.success:
                    job.psd_path = result.psd_path
                    job.png_path = result.png_path
                    job.render_log = result.log
                    self._queue.complete_job(job)
                else:
                    self._queue.fail_job(job, result.error or "Render failed")
                if job_callback:
                    job_callback(job, result)
                results.append(result)
        finally:
            self._queue.end_batch()
            if self._queue.is_cancelled():
                self._history_batch_event(None, HistoryEventType.BATCH_RENDER_CANCELLED, user, "")
            else:
                self._history_batch_event(None, HistoryEventType.BATCH_RENDER_COMPLETED, user, "")
        return results

    def pause_batch(self) -> None:
        self._queue.pause()

    def resume_batch(self) -> None:
        self._queue.resume()

    def cancel_batch(self) -> None:
        self._queue.cancel()

    def retry_failed(self, job_id: str) -> BatchRenderJob | None:
        return self._queue.retry_job(job_id)

    def process_queue(self, *, user: str = "Operator", progress_callback=None) -> list[PSDRenderResult]:
        return self.process_batch(
            user=user,
            progress_callback=(
                lambda job, progress: progress_callback(progress) if progress_callback and progress else None
            ),
        )

    def _history_batch_event(
        self,
        document: ProjectDocument | None,
        event: HistoryEventType,
        user: str,
        details: str,
    ) -> None:
        if document is not None:
            self._history.record(
                document,
                event,
                application_version=self._application_version,
                user=user,
                details=details,
            )
