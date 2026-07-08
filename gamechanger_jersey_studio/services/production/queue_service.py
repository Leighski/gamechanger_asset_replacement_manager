"""Production Queue — aggregate pending interpretations across projects."""

from __future__ import annotations

import json
from pathlib import Path

from models.interpretation import InterpretationArchive, InterpretationResult, SuggestionStatus
from models.production import ProductionDashboardStats, ProductionQueueItem, ProductionQueueStatus
from models.project import ProjectDocument
from services.logging_manager import get_logger
from services.production.confidence_service import ProductionConfidenceService
from services.project_format import read_project_package
from services.template_manager_service import TemplateManagerService

logger = get_logger()


class ProductionQueueService:
    """Manage the cross-project production suggestion queue."""

    def __init__(
        self,
        templates: TemplateManagerService,
        confidence: ProductionConfidenceService,
    ) -> None:
        self._templates = templates
        self._confidence = confidence
        self._items: list[ProductionQueueItem] = []
        self._status_overrides: dict[str, ProductionQueueStatus] = {}

    @property
    def items(self) -> list[ProductionQueueItem]:
        return list(self._items)

    def clear(self) -> None:
        self._items.clear()
        self._status_overrides.clear()

    def refresh_from_paths(self, project_paths: list[str | Path]) -> list[ProductionQueueItem]:
        self._items.clear()
        for path in project_paths:
            item = self._load_queue_items_from_path(path)
            self._items.extend(item)
        self._apply_status_overrides()
        logger.info("Production queue refreshed — {} item(s)", len(self._items))
        return self._items

    def add_project_path(self, path: str | Path) -> list[ProductionQueueItem]:
        new_items = self._load_queue_items_from_path(path)
        existing_ids = {item.item_id for item in self._items}
        for item in new_items:
            if item.item_id not in existing_ids:
                self._items.append(item)
        self._apply_status_overrides()
        return new_items

    def filter_items(
        self,
        *,
        confidence_band: str | None = None,
        season: str | None = None,
        competition: str | None = None,
        status: ProductionQueueStatus | None = None,
        template_id: str | None = None,
    ) -> list[ProductionQueueItem]:
        results = self._items
        if confidence_band:
            results = [item for item in results if item.confidence_band.value == confidence_band]
        if season:
            results = [item for item in results if season.lower() in item.season.lower()]
        if competition:
            results = [item for item in results if competition.lower() in item.competition.lower()]
        if status:
            results = [item for item in results if item.status == status]
        if template_id:
            results = [item for item in results if item.template_id == template_id]
        return results

    def set_status(self, item_id: str, status: ProductionQueueStatus) -> None:
        self._status_overrides[item_id] = status
        for item in self._items:
            if item.item_id == item_id:
                item.status = status
                break

    def mark_ready_to_render(self, item_id: str) -> None:
        self.set_status(item_id, ProductionQueueStatus.READY_TO_RENDER)

    def dashboard_stats(self, batch_rendering: int = 0) -> ProductionDashboardStats:
        awaiting = sum(
            1 for item in self._items if item.status == ProductionQueueStatus.PENDING_REVIEW
        )
        ready = sum(
            1 for item in self._items if item.status == ProductionQueueStatus.READY_TO_RENDER
        )
        completed = sum(1 for item in self._items if item.status == ProductionQueueStatus.COMPLETED)
        failed = sum(1 for item in self._items if item.status == ProductionQueueStatus.FAILED)
        confidences = [item.confidence for item in self._items if item.confidence > 0]
        avg_conf = round(sum(confidences) / len(confidences), 2) if confidences else 0.0
        return ProductionDashboardStats(
            awaiting_review=awaiting,
            ready_to_render=ready,
            rendering=batch_rendering,
            completed=completed,
            failed=failed,
            average_confidence=avg_conf,
        )

    def export_queue_json(self) -> str:
        return json.dumps([item.model_dump(mode="json") for item in self._items], indent=2)

    def _load_queue_items_from_path(self, path: str | Path) -> list[ProductionQueueItem]:
        source = Path(path).expanduser().resolve()
        if not source.is_file():
            return []
        try:
            document, _ = read_project_package(source)
        except Exception as exc:
            logger.warning("Cannot load project for queue — {}: {}", source, exc)
            return []
        return self._items_from_document(document, str(source))

    def _items_from_document(self, document: ProjectDocument, project_path: str) -> list[ProductionQueueItem]:
        archive = document.interpretation_results or InterpretationArchive()
        template_id = self._templates.active_template_id(document)
        items: list[ProductionQueueItem] = []
        for interpretation in archive.interpretations:
            pending = [s for s in interpretation.suggestions if s.status == SuggestionStatus.PENDING]
            if not pending:
                continue
            evaluated = self._confidence.evaluate_all(pending)
            min_conf = min(s.confidence for s in evaluated)
            min_band = self._confidence.band_for(min_conf)
            items.append(
                ProductionQueueItem(
                    item_id=f"{project_path}:{interpretation.interpretation_id}",
                    project_path=project_path,
                    project_name=document.manifest.project_name,
                    club=document.manifest.club_name,
                    season=document.manifest.season,
                    competition=document.manifest.competition,
                    interpretation_id=interpretation.interpretation_id,
                    analysis_id=interpretation.analysis_id,
                    confidence=min_conf,
                    confidence_band=min_band,
                    status=ProductionQueueStatus.PENDING_REVIEW,
                    template_id=template_id,
                    operator=document.manifest.author or "",
                    last_modified=document.manifest.modified_at,
                    pending_suggestion_count=len(pending),
                    suggestion_ids=[s.suggestion_id for s in pending],
                )
            )
        return items

    def _apply_status_overrides(self) -> None:
        for item in self._items:
            if item.item_id in self._status_overrides:
                item.status = self._status_overrides[item.item_id]
