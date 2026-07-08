"""Bulk review operations across production queue items."""

from __future__ import annotations

from dataclasses import dataclass, field

from models.production import ProductionQueueItem, SuggestionDiff
from models.production import CONFIDENCE_BAND_LABELS
from services.interpretation_service import InterpretationService
from services.logging_manager import get_logger
from services.production.confidence_service import ProductionConfidenceService
from services.production.queue_service import ProductionQueueService
from services.project_format import read_project_package, write_project_package

logger = get_logger()


@dataclass
class BulkReviewResult:
    accepted: int = 0
    rejected: int = 0
    failed: int = 0
    errors: list[str] = field(default_factory=list)


class BulkReviewService:
    """Accept/reject suggestions across multiple projects."""

    def __init__(
        self,
        queue: ProductionQueueService,
        confidence: ProductionConfidenceService,
    ) -> None:
        self._queue = queue
        self._confidence = confidence

    def build_diffs(self, item: ProductionQueueItem) -> list[SuggestionDiff]:
        from models.interpretation import SuggestionStatus

        path = item.project_path
        try:
            document, _ = read_project_package(path)
        except Exception:
            return []
        archive = document.interpretation_results
        if archive is None:
            return []
        interpretation = archive.get(item.interpretation_id)
        if interpretation is None:
            return []
        diffs: list[SuggestionDiff] = []
        for suggestion in interpretation.suggestions:
            if suggestion.status != SuggestionStatus.PENDING:
                continue
            if suggestion.suggestion_id not in item.suggestion_ids:
                continue
            band = self._confidence.band_for(suggestion.confidence)
            diffs.append(
                SuggestionDiff(
                    suggestion_id=suggestion.suggestion_id,
                    field_name=suggestion.target_field,
                    current_value=suggestion.current_value,
                    proposed_value=suggestion.proposed_value,
                    confidence=suggestion.confidence,
                    confidence_band=band,
                    band_label=self._confidence.band_label(band),
                )
            )
        return diffs

    def accept_all_trusted(
        self,
        interpretation_service: InterpretationService,
        *,
        user: str = "Operator",
    ) -> BulkReviewResult:
        result = BulkReviewResult()
        for item in self._queue.items:
            trusted_ids = self._trusted_ids_for_item(item)
            if not trusted_ids:
                continue
            count = self._accept_ids(interpretation_service, item, trusted_ids, user=user)
            if count >= 0:
                result.accepted += count
            else:
                result.failed += 1
        logger.info("Bulk accept trusted — {} accepted", result.accepted)
        return result

    def reject_all_low_confidence(
        self,
        interpretation_service: InterpretationService,
        *,
        user: str = "Operator",
    ) -> BulkReviewResult:
        result = BulkReviewResult()
        for item in self._queue.items:
            low_ids = self._low_ids_for_item(item)
            for suggestion_id in low_ids:
                try:
                    document, _ = read_project_package(item.project_path)
                    interpretation_service.load(document.interpretation_results)
                    interpretation_service.reject_suggestion(
                        document,
                        item.interpretation_id,
                        suggestion_id,
                        user=user,
                    )
                    write_project_package(document, item.project_path)
                    result.rejected += 1
                except Exception as exc:
                    result.failed += 1
                    result.errors.append(str(exc))
        logger.info("Bulk reject low confidence — {} rejected", result.rejected)
        return result

    def accept_selected(
        self,
        interpretation_service: InterpretationService,
        items: list[ProductionQueueItem],
        suggestion_ids: list[str],
        *,
        user: str = "Operator",
    ) -> BulkReviewResult:
        result = BulkReviewResult()
        for item in items:
            ids = [sid for sid in suggestion_ids if sid in item.suggestion_ids]
            if not ids:
                continue
            count = self._accept_ids(interpretation_service, item, ids, user=user)
            if count >= 0:
                result.accepted += count
            else:
                result.failed += 1
        return result

    def reject_selected(
        self,
        interpretation_service: InterpretationService,
        items: list[ProductionQueueItem],
        suggestion_ids: list[str],
        *,
        user: str = "Operator",
    ) -> BulkReviewResult:
        result = BulkReviewResult()
        for item in items:
            ids = [sid for sid in suggestion_ids if sid in item.suggestion_ids]
            for suggestion_id in ids:
                try:
                    document, _ = read_project_package(item.project_path)
                    interpretation_service.load(document.interpretation_results)
                    interpretation_service.reject_suggestion(
                        document,
                        item.interpretation_id,
                        suggestion_id,
                        user=user,
                    )
                    write_project_package(document, item.project_path)
                    result.rejected += 1
                except Exception as exc:
                    result.failed += 1
                    result.errors.append(str(exc))
        return result

    def _trusted_ids_for_item(self, item: ProductionQueueItem) -> list[str]:
        try:
            document, _ = read_project_package(item.project_path)
        except Exception:
            return []
        archive = document.interpretation_results
        if archive is None:
            return []
        interpretation = archive.get(item.interpretation_id)
        if interpretation is None:
            return []
        return self._confidence.trusted_suggestion_ids(interpretation.pending_suggestions())

    def _low_ids_for_item(self, item: ProductionQueueItem) -> list[str]:
        try:
            document, _ = read_project_package(item.project_path)
        except Exception:
            return []
        archive = document.interpretation_results
        if archive is None:
            return []
        interpretation = archive.get(item.interpretation_id)
        if interpretation is None:
            return []
        return self._confidence.low_confidence_suggestion_ids(interpretation.pending_suggestions())

    def _accept_ids(
        self,
        interpretation_service: InterpretationService,
        item: ProductionQueueItem,
        suggestion_ids: list[str],
        *,
        user: str,
    ) -> int:
        try:
            document, blobs = read_project_package(item.project_path)
            interpretation_service.load(document.interpretation_results)
            accepted = interpretation_service.accept_suggestions(
                document,
                item.interpretation_id,
                suggestion_ids,
                user=user,
            )
            write_project_package(document, item.project_path, reference_blobs=blobs)
            self._queue.mark_ready_to_render(item.item_id)
            return len(accepted)
        except Exception as exc:
            logger.error("Bulk accept failed — {}: {}", item.project_path, exc)
            return -1
