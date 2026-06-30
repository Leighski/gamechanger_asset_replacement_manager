"""Suggestion history — record operator feedback for future analytics."""

from __future__ import annotations

from models.interpretation import (
    InterpretationArchive,
    InterpretationSuggestion,
    OperatorDecision,
    OperatorFeedbackRecord,
    SuggestionStatus,
)


class SuggestionHistoryService:
    """Persist operator decisions without auto-retraining."""

    def record_decision(
        self,
        archive: InterpretationArchive,
        interpretation_id: str,
        suggestion: InterpretationSuggestion,
        decision: OperatorDecision,
        *,
        operator: str,
        final_value: str = "",
    ) -> OperatorFeedbackRecord:
        record = OperatorFeedbackRecord(
            suggestion_id=suggestion.suggestion_id,
            interpretation_id=interpretation_id,
            decision=decision,
            target_field=suggestion.target_field,
            proposed_value=suggestion.proposed_value,
            final_value=final_value or suggestion.effective_value(),
            confidence=suggestion.confidence,
            ai_provider=suggestion.ai_provider,
            operator=operator,
        )
        archive.feedback.append(record)
        return record

    def accepted_count(self, archive: InterpretationArchive) -> int:
        return sum(1 for item in archive.feedback if item.decision == OperatorDecision.ACCEPTED)

    def rejected_count(self, archive: InterpretationArchive) -> int:
        return sum(1 for item in archive.feedback if item.decision == OperatorDecision.REJECTED)

    def modified_count(self, archive: InterpretationArchive) -> int:
        return sum(1 for item in archive.feedback if item.decision == OperatorDecision.MODIFIED)

    def mark_suggestion_status(
        self,
        suggestion: InterpretationSuggestion,
        status: SuggestionStatus,
        *,
        operator_value: str = "",
    ) -> InterpretationSuggestion:
        update: dict = {"status": status}
        if operator_value:
            update["operator_value"] = operator_value
        return suggestion.model_copy(update=update)
