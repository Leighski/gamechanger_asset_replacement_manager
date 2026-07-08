"""Learning Event capture — record operator manual corrections."""

from __future__ import annotations

from models.learning import KnowledgeBase, LearningEvent
from models.project import KitType, ProjectDocument
from services.logging_manager import get_logger
from services.learning.knowledge_base_service import KnowledgeBaseService

logger = get_logger()

MAX_EVENTS = 5000


class LearningEventService:
    """Capture and query learning events from operator corrections."""

    def __init__(self, knowledge_base: KnowledgeBaseService) -> None:
        self._kb = knowledge_base

    @property
    def events(self) -> list[LearningEvent]:
        return list(self._kb.knowledge.events)

    def record_correction(
        self,
        document: ProjectDocument,
        *,
        target_field: str,
        original_ai_value: str,
        final_operator_value: str,
        confidence: float,
        operator: str,
        interpretation_id: str = "",
        suggestion_id: str = "",
        vision_measurements: list[str] | None = None,
        template_id: str = "",
    ) -> LearningEvent:
        manifest = document.manifest
        kit = manifest.kit_type.value if isinstance(manifest.kit_type, KitType) else str(manifest.kit_type)
        event = LearningEvent(
            project_path=document.file_path or "",
            project_name=manifest.project_name,
            club=manifest.club_name,
            competition=manifest.competition,
            season=manifest.season,
            manufacturer=document.design_spec.manufacturer if document.design_spec else "",
            kit_type=kit,
            target_field=target_field,
            original_ai_value=original_ai_value,
            final_operator_value=final_operator_value,
            confidence=confidence,
            vision_measurements=vision_measurements or [],
            template_id=template_id,
            operator=operator,
            interpretation_id=interpretation_id,
            suggestion_id=suggestion_id,
        )
        kb = self._kb.knowledge
        kb.events.append(event)
        if len(kb.events) > MAX_EVENTS:
            kb.events = kb.events[-MAX_EVENTS:]
        self._kb.save()
        logger.info(
            "Learning event recorded — {} {} → {}",
            event.club,
            target_field,
            final_operator_value,
        )
        return event

    def similar_events(
        self,
        *,
        club: str,
        target_field: str,
        original_ai_value: str,
        final_operator_value: str,
    ) -> list[LearningEvent]:
        return [
            e
            for e in self._kb.knowledge.events
            if e.club.lower() == club.lower()
            and e.target_field == target_field
            and e.original_ai_value == original_ai_value
            and e.final_operator_value == final_operator_value
        ]

    def frequent_corrections(self, limit: int = 10) -> list[tuple[str, int]]:
        counts: dict[str, int] = {}
        for event in self._kb.knowledge.events:
            key = f"{event.club}:{event.target_field}:{event.original_ai_value}→{event.final_operator_value}"
            counts[key] = counts.get(key, 0) + 1
        ranked = sorted(counts.items(), key=lambda item: item[1], reverse=True)
        return ranked[:limit]
