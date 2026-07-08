"""Learning analytics — rule effectiveness and dashboard statistics."""

from __future__ import annotations

from models.learning import LearningDashboardStats, LearningRuleStatus, RuleAnalytics
from services.learning.knowledge_base_service import KnowledgeBaseService
from services.learning.event_service import LearningEventService


class LearningAnalyticsService:
    """Compute learning dashboard and per-rule analytics."""

    def __init__(
        self,
        knowledge_base: KnowledgeBaseService,
        events: LearningEventService,
    ) -> None:
        self._kb = knowledge_base
        self._events = events

    def dashboard_stats(self) -> LearningDashboardStats:
        kb = self._kb.knowledge
        active = sum(1 for r in kb.rules if r.status == LearningRuleStatus.APPROVED)
        drafts = sum(1 for r in kb.rules if r.status == LearningRuleStatus.DRAFT)
        most_used = max(kb.rules, key=lambda r: r.usage_count, default=None)
        frequent = self._events.frequent_corrections(limit=1)
        field_counts: dict[str, int] = {}
        for event in kb.events:
            field_counts[event.target_field] = field_counts.get(event.target_field, 0) + 1
        best_field = max(field_counts, key=field_counts.get, default="") if field_counts else ""
        return LearningDashboardStats(
            total_events=len(kb.events),
            active_rules=active,
            draft_rules=drafts,
            most_used_rule=most_used.title if most_used else "",
            most_frequent_correction=frequent[0][0] if frequent else "",
            most_improved_field=best_field,
            recent_activity_count=min(10, len(kb.events)),
        )

    def rule_analytics(self, rule_id: str) -> RuleAnalytics | None:
        rule = self._kb.knowledge.get_rule(rule_id)
        if rule is None:
            return None
        total = rule.accepted_count + rule.ignored_count + rule.modified_count
        acceptance = round(rule.accepted_count / total * 100.0, 2) if total else 0.0
        modification = round(rule.modified_count / total * 100.0, 2) if total else 0.0
        return RuleAnalytics(
            rule_id=rule.rule_id,
            title=rule.title,
            usage_count=rule.usage_count,
            acceptance_rate=acceptance,
            ignored_count=rule.ignored_count,
            modification_rate=modification,
            confidence_improvement=rule.action.confidence_boost,
        )

    def all_rule_analytics(self) -> list[RuleAnalytics]:
        return [a for r in self._kb.knowledge.rules if (a := self.rule_analytics(r.rule_id))]

    def learning_growth(self) -> dict[str, int]:
        return {
            "events": len(self._kb.knowledge.events),
            "rules": len(self._kb.knowledge.rules),
            "approved_rules": sum(
                1 for r in self._kb.knowledge.rules if r.status == LearningRuleStatus.APPROVED
            ),
            "usage_records": len(self._kb.knowledge.usage_history),
        }
