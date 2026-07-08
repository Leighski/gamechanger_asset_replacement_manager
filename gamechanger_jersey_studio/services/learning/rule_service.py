"""Learning Rule management — CRUD and pattern-based rule suggestions."""

from __future__ import annotations

from datetime import datetime, timezone

from models.learning import (
    RULE_SUGGESTION_THRESHOLD,
    KnowledgeBase,
    LearningRule,
    LearningRuleCategory,
    LearningRuleStatus,
    RecommendedAction,
    RuleSuggestionPrompt,
    TriggerConditions,
)
from services.learning.event_service import LearningEventService
from services.learning.knowledge_base_service import KnowledgeBaseService
from services.logging_manager import get_logger

logger = get_logger()


class LearningRuleService:
    """Manage learning rules in the Knowledge Base."""

    def __init__(
        self,
        knowledge_base: KnowledgeBaseService,
        events: LearningEventService,
    ) -> None:
        self._kb = knowledge_base
        self._events = events

    @property
    def rules(self) -> list[LearningRule]:
        return list(self._kb.knowledge.rules)

    def get(self, rule_id: str) -> LearningRule | None:
        return self._kb.knowledge.get_rule(rule_id)

    def create(self, rule: LearningRule) -> LearningRule:
        self._kb.knowledge.rules.append(rule)
        self._kb.save()
        logger.info("Learning rule created — {} ({})", rule.title, rule.rule_id)
        return rule

    def update(self, rule: LearningRule) -> LearningRule:
        self._kb.knowledge.rules = [
            rule if item.rule_id == rule.rule_id else item for item in self._kb.knowledge.rules
        ]
        self._kb.save()
        return rule

    def delete(self, rule_id: str) -> bool:
        before = len(self._kb.knowledge.rules)
        self._kb.knowledge.rules = [r for r in self._kb.knowledge.rules if r.rule_id != rule_id]
        if len(self._kb.knowledge.rules) < before:
            self._kb.save()
            return True
        return False

    def duplicate(self, rule_id: str, *, created_by: str = "Operator") -> LearningRule | None:
        source = self.get(rule_id)
        if source is None:
            return None
        copy = source.model_copy(
            update={
                "title": f"{source.title} (copy)",
                "status": LearningRuleStatus.DRAFT,
                "usage_count": 0,
                "accepted_count": 0,
                "ignored_count": 0,
                "modified_count": 0,
                "created_by": created_by,
                "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            }
        )
        copy.rule_id = f"LR_{copy.rule_id[-8:]}_COPY"[:16]
        return self.create(copy)

    def set_status(self, rule_id: str, status: LearningRuleStatus) -> LearningRule | None:
        rule = self.get(rule_id)
        if rule is None:
            return None
        return self.update(rule.model_copy(update={"status": status}))

    def search(self, query: str = "", *, category: LearningRuleCategory | None = None) -> list[LearningRule]:
        results = self._kb.knowledge.rules
        if category is not None:
            results = [r for r in results if r.category == category]
        if query:
            q = query.lower()
            results = [
                r
                for r in results
                if q in r.title.lower()
                or q in r.description.lower()
                or q in r.triggers.club.lower()
            ]
        return results

    def detect_rule_suggestions(self) -> list[RuleSuggestionPrompt]:
        prompts: list[RuleSuggestionPrompt] = []
        seen: set[str] = set()
        for key, count in self._events.frequent_corrections(limit=20):
            if count < RULE_SUGGESTION_THRESHOLD:
                continue
            if key in seen:
                continue
            seen.add(key)
            parts = key.split(":", 2)
            if len(parts) < 3:
                continue
            club, field, values = parts[0], parts[1], parts[2]
            if "→" not in values:
                continue
            original, final = values.split("→", 1)
            similar = self._events.similar_events(
                club=club,
                target_field=field,
                original_ai_value=original,
                final_operator_value=final,
            )
            proposed = LearningRule(
                title=f"{club} {field.replace('_', ' ')} correction",
                description=f"Operator consistently changes {field} from {original} to {final}",
                category=self._category_for_field(field),
                triggers=TriggerConditions(
                    field_name=field,
                    club=club,
                    original_value=original,
                ),
                action=RecommendedAction(
                    target_field=field,
                    recommended_value=final,
                    advisory_note=f"Based on {count} similar corrections",
                    confidence_boost=5.0,
                ),
                confidence=min(95.0, 70.0 + count * 2),
                created_by="Learning Mode",
                status=LearningRuleStatus.DRAFT,
            )
            prompts.append(
                RuleSuggestionPrompt(
                    title=f"Recurring correction: {club}",
                    message=(
                        f"This {field.replace('_', ' ')} correction has occurred on "
                        f"{count} {club} jerseys. Would you like to create a reusable Learning Rule?"
                    ),
                    occurrence_count=count,
                    sample_event_ids=[e.event_id for e in similar[:5]],
                    proposed_rule=proposed,
                )
            )
        self._kb.knowledge.pending_prompts = [
            p for p in self._kb.knowledge.pending_prompts if not p.dismissed
        ] + prompts
        self._kb.save()
        return prompts

    def dismiss_prompt(self, prompt_id: str, *, remind_later: bool = False) -> None:
        for prompt in self._kb.knowledge.pending_prompts:
            if prompt.prompt_id == prompt_id:
                prompt.dismissed = not remind_later
                if remind_later:
                    prompt.remind_after = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self._kb.save()

    @staticmethod
    def _category_for_field(field: str) -> LearningRuleCategory:
        mapping = {
            "collar_style": LearningRuleCategory.COLLAR,
            "sleeve_style": LearningRuleCategory.SLEEVE,
            "trim_style": LearningRuleCategory.TRIM,
            "pattern": LearningRuleCategory.PATTERN,
            "primary_colour": LearningRuleCategory.COLOUR,
            "secondary_colour": LearningRuleCategory.COLOUR,
            "output_profile": LearningRuleCategory.OUTPUT_PROFILE,
        }
        return mapping.get(field, LearningRuleCategory.CLUB)
