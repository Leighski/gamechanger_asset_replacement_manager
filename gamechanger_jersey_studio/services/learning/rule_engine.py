"""Learning Rule Engine — evaluate approved rules and produce advisory recommendations."""

from __future__ import annotations

from datetime import datetime, timezone

from models.interpretation import InterpretationSuggestion
from models.learning import LearningRecommendation, LearningRule, RuleUsageRecord
from models.project import ProjectDocument
from services.learning.knowledge_base_service import KnowledgeBaseService
from services.logging_manager import get_logger

logger = get_logger()


class LearningRuleEngine:
    """Evaluate approved rules — advisory only, never overwrites AI suggestions."""

    def __init__(self, knowledge_base: KnowledgeBaseService) -> None:
        self._kb = knowledge_base

    def evaluate(
        self,
        document: ProjectDocument,
        suggestions: list[InterpretationSuggestion],
        *,
        template_id: str = "",
    ) -> list[LearningRecommendation]:
        recommendations: list[LearningRecommendation] = []
        for rule in self._kb.knowledge.approved_rules():
            for suggestion in suggestions:
                if not self._matches(rule, document, suggestion, template_id):
                    continue
                rec = LearningRecommendation(
                    rule_id=rule.rule_id,
                    title=rule.title,
                    message=f"Learning Recommendation: {rule.description or rule.title}",
                    target_field=suggestion.target_field,
                    recommended_value=rule.action.recommended_value or suggestion.proposed_value,
                    advisory_note=rule.action.advisory_note,
                    confidence_boost=rule.action.confidence_boost,
                    catalogue_component=rule.action.catalogue_component,
                )
                recommendations.append(rec)
                self._record_usage(rule, document, accepted=False, ignored=False)
        if recommendations:
            logger.info("Learning recommendations — {} for {}", len(recommendations), document.manifest.project_name)
        return recommendations

    def apply_confidence_boost(
        self,
        suggestions: list[InterpretationSuggestion],
        recommendations: list[LearningRecommendation],
    ) -> list[InterpretationSuggestion]:
        """Increase confidence on matching suggestions — advisory boost only."""
        boosted: list[InterpretationSuggestion] = []
        rec_by_field = {r.target_field: r for r in recommendations}
        for suggestion in suggestions:
            rec = rec_by_field.get(suggestion.target_field)
            if rec and rec.confidence_boost > 0:
                new_conf = min(100.0, suggestion.confidence + rec.confidence_boost)
                boosted.append(suggestion.model_copy(update={"confidence": new_conf}))
            else:
                boosted.append(suggestion)
        return boosted

    def record_recommendation_accepted(self, rule_id: str, document: ProjectDocument, operator: str) -> None:
        self._record_usage(self._kb.knowledge.get_rule(rule_id), document, accepted=True, operator=operator)

    def record_recommendation_ignored(self, rule_id: str, document: ProjectDocument, operator: str) -> None:
        rule = self._kb.knowledge.get_rule(rule_id)
        if rule is not None:
            rule.ignored_count += 1
            self._kb.knowledge.rules = [
                rule if r.rule_id == rule_id else r for r in self._kb.knowledge.rules
            ]
        self._record_usage(rule, document, ignored=True, operator=operator)
        self._kb.save()

    def _matches(
        self,
        rule: LearningRule,
        document: ProjectDocument,
        suggestion: InterpretationSuggestion,
        template_id: str,
    ) -> bool:
        t = rule.triggers
        manifest = document.manifest
        if t.field_name and t.field_name != suggestion.target_field:
            return False
        if t.club and t.club.lower() != manifest.club_name.lower():
            return False
        if t.competition and t.competition.lower() not in manifest.competition.lower():
            return False
        if t.season and t.season != manifest.season:
            return False
        if t.kit_type and t.kit_type != manifest.kit_type.value:
            return False
        if t.template_id and template_id and t.template_id != template_id:
            return False
        if t.original_value and t.original_value != suggestion.proposed_value:
            return False
        if document.design_spec:
            spec = document.design_spec
            if t.manufacturer and t.manufacturer.lower() not in (spec.manufacturer or "").lower():
                return False
            if t.pattern and t.pattern != spec.pattern:
                return False
        return True

    def _record_usage(
        self,
        rule: LearningRule | None,
        document: ProjectDocument,
        *,
        accepted: bool = False,
        ignored: bool = False,
        modified: bool = False,
        operator: str = "",
    ) -> None:
        if rule is None:
            return
        rule.usage_count += 1
        rule.last_used = datetime.now(timezone.utc).isoformat(timespec="seconds")
        if accepted:
            rule.accepted_count += 1
        if ignored:
            rule.ignored_count += 1
        if modified:
            rule.modified_count += 1
        self._kb.knowledge.rules = [
            rule if r.rule_id == rule.rule_id else r for r in self._kb.knowledge.rules
        ]
        self._kb.knowledge.usage_history.append(
            RuleUsageRecord(
                rule_id=rule.rule_id,
                project_path=document.file_path or "",
                project_name=document.manifest.project_name,
                operator=operator,
                accepted=accepted,
                ignored=ignored,
                modified=modified,
            )
        )
        self._kb.save()
