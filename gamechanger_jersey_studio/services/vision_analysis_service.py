"""Vision analysis project integration — never modifies Design Specification directly."""

from __future__ import annotations

import json
from typing import Any

from models.project import HistoryEventType, ProjectDocument
from models.reference_image import AnalysisStatus
from models.vision_analysis import AnalysisReviewStatus, VisionAnalysisArchive, VisionAnalysisResult
from services.design_specification_service import DesignSpecificationService
from services.logging_manager import get_logger
from services.project_history_service import ProjectHistoryService
from services.reference_image_service import ReferenceImageService
from services.vision.pipeline import VisionEngine, VisionEngineError

logger = get_logger()

VISION_ANALYSES_NAME = "vision/analyses.json"


class VisionAnalysisService:
    """Run analyses, store results, and apply operator-approved mappings only."""

    def __init__(
        self,
        reference_images: ReferenceImageService,
        design_specification: DesignSpecificationService,
        history_service: ProjectHistoryService | None = None,
        *,
        application_version: str = "",
    ) -> None:
        self._references = reference_images
        self._design = design_specification
        self._history = history_service or ProjectHistoryService()
        self._application_version = application_version
        self._engine = VisionEngine()
        self._archive = VisionAnalysisArchive()

    @property
    def archive(self) -> VisionAnalysisArchive:
        return self._archive

    def reset(self) -> None:
        self._archive = VisionAnalysisArchive()

    def load(self, archive: VisionAnalysisArchive | None) -> None:
        self._archive = archive or VisionAnalysisArchive()

    def ensure_archive(self, document: ProjectDocument) -> VisionAnalysisArchive:
        if document.vision_analyses is None:
            document.vision_analyses = VisionAnalysisArchive()
        self._archive = document.vision_analyses
        return self._archive

    def analyse_image(self, document: ProjectDocument, image_id: str, *, user: str) -> VisionAnalysisResult:
        record = self._references.manifest.get(image_id)
        if record is None:
            raise VisionEngineError(f"Reference image not found: {image_id}")
        image_bytes = self._references.image_bytes(image_id)
        if image_bytes is None:
            raise VisionEngineError("Reference image bytes are unavailable")

        self.ensure_archive(document)
        record.analysis_status = AnalysisStatus.PENDING
        self._sync_reference_status(document)
        self._record_history(
            document,
            HistoryEventType.VISION_ANALYSIS_STARTED,
            user,
            {"image_id": image_id, "filename": record.filename},
        )
        logger.info("Vision analysis started — {} ({})", record.filename, image_id)

        try:
            result = self._engine.analyse_image(
                image_id=image_id,
                image_filename=record.filename,
                image_bytes=image_bytes,
                orientation=record.orientation,
            )
            self._archive.analyses.append(result)
            record.analysis_status = AnalysisStatus.COMPLETE
            self._sync_reference_status(document)
            document.mark_dirty()
            summary = result.confidence_summary
            self._record_history(
                document,
                HistoryEventType.VISION_ANALYSIS_COMPLETED,
                user,
                {
                    "analysis_id": result.analysis_id,
                    "image_id": image_id,
                    "processing_time_ms": result.performance.processing_time_ms if result.performance else 0,
                    "confidence_summary": summary,
                },
            )
            logger.info(
                "Vision analysis completed — {} in {:.1f}ms (confidence {:.1f}%)",
                record.filename,
                result.performance.processing_time_ms if result.performance else 0,
                result.overall_confidence(),
            )
            return result
        except VisionEngineError as exc:
            record.analysis_status = AnalysisStatus.FAILED
            self._sync_reference_status(document)
            self._record_history(
                document,
                HistoryEventType.VISION_ANALYSIS_FAILED,
                user,
                {"image_id": image_id, "error": str(exc)},
            )
            logger.error("Vision analysis failed — {}: {}", record.filename, exc)
            raise

    def reject_analysis(self, document: ProjectDocument, analysis_id: str, *, user: str) -> None:
        analysis = self._get_analysis(document, analysis_id)
        analysis.review_status = AnalysisReviewStatus.REJECTED
        document.mark_dirty()
        self._record_history(
            document,
            HistoryEventType.VISION_ANALYSIS_REJECTED,
            user,
            {"analysis_id": analysis_id},
        )

    def accept_mappings(
        self,
        document: ProjectDocument,
        analysis_id: str,
        mapping_ids: list[str] | None,
        *,
        user: str,
        accept_all: bool = False,
    ) -> list[str]:
        analysis = self._get_analysis(document, analysis_id)
        accepted_fields: list[str] = []
        for mapping in analysis.suggested_mappings:
            if accept_all or (mapping_ids and mapping.mapping_id in mapping_ids):
                self._design.apply_change(
                    document,
                    mapping.design_spec_field,
                    mapping.suggested_value,
                    user=user,
                )
                mapping.accepted = True
                accepted_fields.append(mapping.design_spec_field)
        analysis.review_status = (
            AnalysisReviewStatus.ACCEPTED
            if accept_all or len(accepted_fields) == len(analysis.suggested_mappings)
            else AnalysisReviewStatus.PARTIAL
        )
        document.mark_dirty()
        self._record_history(
            document,
            HistoryEventType.VISION_ANALYSIS_ACCEPTED,
            user,
            {"analysis_id": analysis_id, "fields": accepted_fields},
        )
        return accepted_fields

    def latest_for_image(self, image_id: str) -> VisionAnalysisResult | None:
        return self._archive.latest_for_image(image_id)

    def analyses_for_image(self, image_id: str) -> list[VisionAnalysisResult]:
        return self._archive.for_image(image_id)

    def _get_analysis(self, document: ProjectDocument, analysis_id: str) -> VisionAnalysisResult:
        archive = self.ensure_archive(document)
        analysis = archive.get(analysis_id)
        if analysis is None:
            raise VisionEngineError(f"Analysis not found: {analysis_id}")
        return analysis

    def _sync_reference_status(self, document: ProjectDocument) -> None:
        document.reference_manifest = self._references.manifest

    def _record_history(
        self,
        document: ProjectDocument,
        event: HistoryEventType,
        user: str,
        payload: dict[str, Any],
    ) -> None:
        self._history.record(
            document,
            event,
            application_version=self._application_version,
            user=user,
            details=json.dumps(payload, ensure_ascii=False),
        )
