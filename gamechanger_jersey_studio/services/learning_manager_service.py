"""Learning Mode manager — organisational knowledge coordinator."""

from __future__ import annotations

from pathlib import Path

from models.learning import LearningRule, LearningRuleStatus
from models.project import ProjectDocument
from services.learning.analytics_service import LearningAnalyticsService
from services.learning.event_service import LearningEventService
from services.learning.knowledge_base_service import KnowledgeBaseService
from services.learning.rule_engine import LearningRuleEngine
from services.learning.rule_service import LearningRuleService
from services.logging_manager import get_logger

logger = get_logger()


class LearningManagerService:
    """Central access point for Learning Mode."""

    def __init__(self) -> None:
        self._kb = KnowledgeBaseService()
        self._kb.load()
        self._events = LearningEventService(self._kb)
        self._rules = LearningRuleService(self._kb, self._events)
        self._engine = LearningRuleEngine(self._kb)
        self._analytics = LearningAnalyticsService(self._kb, self._events)

    @property
    def knowledge_base(self) -> KnowledgeBaseService:
        return self._kb

    @property
    def events(self) -> LearningEventService:
        return self._events

    @property
    def rules(self) -> LearningRuleService:
        return self._rules

    @property
    def engine(self) -> LearningRuleEngine:
        return self._engine

    @property
    def analytics(self) -> LearningAnalyticsService:
        return self._analytics

    def export_knowledge_base(self, target: Path) -> Path:
        return self._kb.export_to(target)

    def import_knowledge_base(self, source: Path, *, merge: bool = True) -> None:
        self._kb.import_from(source, merge=merge)

    def approve_rule(self, rule_id: str) -> LearningRule | None:
        return self._rules.set_status(rule_id, LearningRuleStatus.APPROVED)

    def disable_rule(self, rule_id: str) -> LearningRule | None:
        return self._rules.set_status(rule_id, LearningRuleStatus.DISABLED)

    def check_for_rule_suggestions(self) -> None:
        self._rules.detect_rule_suggestions()

    def evaluate_for_interpretation(
        self,
        document: ProjectDocument,
        suggestions,
        *,
        template_id: str = "",
    ):
        from models.interpretation import InterpretationSuggestion

        recs = self._engine.evaluate(document, suggestions, template_id=template_id)
        boosted = self._engine.apply_confidence_boost(suggestions, recs)
        return boosted, recs
