"""Production workflow manager — coordinates queue, review, metrics, and reports."""

from __future__ import annotations

from pathlib import Path

from models.production import ConfidenceThresholds
from models.project import ProjectDocument
from services.logging_manager import get_logger
from services.production.audit_service import ProductionAuditService
from services.production.benchmark_service import BenchmarkService
from services.production.batch_validation_service import BatchValidationService
from services.production.bulk_review_service import BulkReviewService
from services.production.comparison_service import ComparisonService
from services.production.confidence_service import ProductionConfidenceService
from services.production.accuracy_service import AccuracyService
from services.production.kb_validation_service import KnowledgeBaseValidationService
from services.production.metrics_service import OperatorMetricsService
from services.production.queue_service import ProductionQueueService
from services.production.readiness_service import ReadinessService
from services.production.replay_service import ReplayService
from services.production.report_service import ProductionReportService
from services.production.stress_test_service import StressTestService
from services.settings_manager import SettingsManager
from services.template_manager_service import TemplateManagerService

logger = get_logger()


class ProductionManagerService:
    """Central access point for GJS-012 production workflow."""

    def __init__(
        self,
        settings: SettingsManager,
        templates: TemplateManagerService,
    ) -> None:
        self._settings = settings
        thresholds = settings.settings.confidence_thresholds
        self._confidence = ProductionConfidenceService(thresholds)
        self._queue = ProductionQueueService(templates, self._confidence)
        self._bulk_review = BulkReviewService(self._queue, self._confidence)
        self._metrics = OperatorMetricsService()
        self._audit = ProductionAuditService()
        self._reports = ProductionReportService(self._queue)
        self._accuracy = AccuracyService()
        self._comparison = ComparisonService()
        self._replay = ReplayService()
        self._benchmarks = BenchmarkService()
        self._batch_validation = BatchValidationService(self._accuracy, self._metrics)
        self._stress = StressTestService()
        self._readiness = ReadinessService()
        self._kb_validation: KnowledgeBaseValidationService | None = None

    @property
    def confidence(self) -> ProductionConfidenceService:
        return self._confidence

    @property
    def queue(self) -> ProductionQueueService:
        return self._queue

    @property
    def bulk_review(self) -> BulkReviewService:
        return self._bulk_review

    @property
    def metrics(self) -> OperatorMetricsService:
        return self._metrics

    @property
    def audit(self) -> ProductionAuditService:
        return self._audit

    @property
    def reports(self) -> ProductionReportService:
        return self._reports

    @property
    def accuracy(self) -> AccuracyService:
        return self._accuracy

    @property
    def comparison(self) -> ComparisonService:
        return self._comparison

    @property
    def replay(self) -> ReplayService:
        return self._replay

    @property
    def benchmarks(self) -> BenchmarkService:
        return self._benchmarks

    @property
    def batch_validation(self) -> BatchValidationService:
        return self._batch_validation

    @property
    def stress(self) -> StressTestService:
        return self._stress

    @property
    def readiness(self) -> ReadinessService:
        return self._readiness

    @property
    def kb_validation(self) -> KnowledgeBaseValidationService | None:
        return self._kb_validation

    def reload_thresholds(self) -> None:
        self._confidence.set_thresholds(self._settings.settings.confidence_thresholds)

    def update_thresholds(self, thresholds: ConfidenceThresholds) -> None:
        self._settings.update(confidence_thresholds=thresholds)
        self._confidence.set_thresholds(thresholds)
        logger.info(
            "Confidence thresholds updated — trusted>={}, review>={}",
            thresholds.trusted_min,
            thresholds.review_min,
        )

    def refresh_queue_from_recent(self) -> None:
        paths = [entry.path for entry in self._settings.settings.recent_projects if entry.path]
        self._queue.refresh_from_paths(paths)

    def refresh_queue_from_paths(self, paths: list[str | Path]) -> None:
        self._queue.refresh_from_paths(paths)

    def set_learning_manager(self, learning) -> None:
        self._reports = ProductionReportService(self._queue, learning)
        self._kb_validation = KnowledgeBaseValidationService(learning.knowledge_base)

    def add_document_to_queue(self, document: ProjectDocument) -> None:
        if document.file_path:
            self._queue.add_project_path(document.file_path)
