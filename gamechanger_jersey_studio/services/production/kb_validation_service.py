"""Knowledge Base validation analytics — advisory insights only."""

from __future__ import annotations

from models.learning import LearningRule, LearningRuleStatus
from models.validation import KnowledgeBaseValidationReport, RuleValidationInsight
from services.learning.knowledge_base_service import KnowledgeBaseService


class KnowledgeBaseValidationService:
    """Analyse rule effectiveness — never modifies rules automatically."""

    def __init__(self, knowledge_base: KnowledgeBaseService) -> None:
        self._kb = knowledge_base

    def analyse(self) -> KnowledgeBaseValidationReport:
        kb = self._kb.knowledge
        rules = kb.rules
        usage_by_rule = {r.rule_id: r.usage_count for r in rules}
        triggered_ids = {u.rule_id for u in kb.usage_history}

        effective = sorted(
            [r for r in rules if r.status == LearningRuleStatus.APPROVED and r.usage_count > 0],
            key=lambda r: r.accepted_count / max(r.usage_count, 1),
            reverse=True,
        )
        least = sorted(
            [r for r in rules if r.status == LearningRuleStatus.APPROVED and r.usage_count > 0],
            key=lambda r: r.accepted_count / max(r.usage_count, 1),
        )

        never_triggered = [
            r.rule_id for r in rules if r.status == LearningRuleStatus.APPROVED and r.rule_id not in triggered_ids
        ]

        overridden = [
            r for r in rules
            if r.usage_count > 0 and r.modified_count > r.accepted_count
        ]

        merges = self._suggest_merges(rules)
        retirements = self._suggest_retirements(rules, never_triggered)

        return KnowledgeBaseValidationReport(
            most_effective_rules=[
                RuleValidationInsight(
                    rule_id=r.rule_id,
                    title=r.title,
                    insight_type="most_effective",
                    message=f"Acceptance rate {self._acceptance_rate(r):.1f}% over {r.usage_count} uses",
                    metric_value=self._acceptance_rate(r),
                )
                for r in effective[:5]
            ],
            least_effective_rules=[
                RuleValidationInsight(
                    rule_id=r.rule_id,
                    title=r.title,
                    insight_type="least_effective",
                    message=f"Acceptance rate {self._acceptance_rate(r):.1f}% over {r.usage_count} uses",
                    metric_value=self._acceptance_rate(r),
                )
                for r in least[:5]
            ],
            never_triggered_rules=never_triggered,
            frequently_overridden_rules=[
                RuleValidationInsight(
                    rule_id=r.rule_id,
                    title=r.title,
                    insight_type="frequently_overridden",
                    message=f"Modified {r.modified_count} times vs {r.accepted_count} accepted",
                    metric_value=float(r.modified_count),
                )
                for r in overridden[:5]
            ],
            suggested_merges=merges,
            suggested_retirements=retirements,
        )

    def _acceptance_rate(self, rule: LearningRule) -> float:
        total = rule.accepted_count + rule.ignored_count + rule.modified_count
        if not total:
            return 0.0
        return round(rule.accepted_count / total * 100.0, 2)

    def _suggest_merges(self, rules: list[LearningRule]) -> list[str]:
        suggestions: list[str] = []
        by_field: dict[str, list[LearningRule]] = {}
        for rule in rules:
            if rule.status != LearningRuleStatus.APPROVED:
                continue
            key = f"{rule.triggers.field_name}:{rule.triggers.club}:{rule.action.recommended_value}"
            by_field.setdefault(key, []).append(rule)
        for key, group in by_field.items():
            if len(group) > 1:
                titles = ", ".join(r.title for r in group)
                suggestions.append(f"Consider merging rules for '{key}': {titles}")
        return suggestions

    def _suggest_retirements(self, rules: list[LearningRule], never_triggered: list[str]) -> list[str]:
        retirements: list[str] = []
        for rule_id in never_triggered:
            rule = next((r for r in rules if r.rule_id == rule_id), None)
            if rule and rule.usage_count == 0:
                retirements.append(f"Rule '{rule.title}' ({rule_id}) has never been triggered")
        for rule in rules:
            if rule.status == LearningRuleStatus.APPROVED and rule.usage_count > 5:
                rate = self._acceptance_rate(rule)
                if rate < 20.0:
                    retirements.append(
                        f"Rule '{rule.title}' has low acceptance ({rate}%) — consider retirement"
                    )
        return retirements
