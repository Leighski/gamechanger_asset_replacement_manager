"""Confidence evaluation for interpretation suggestions."""

from __future__ import annotations

from models.interpretation import ConfidenceBand, InterpretationSuggestion, confidence_band


class ConfidenceEvaluationService:
    """Assign confidence bands and auto-selection eligibility."""

    def evaluate(self, suggestion: InterpretationSuggestion) -> InterpretationSuggestion:
        band = confidence_band(suggestion.confidence)
        return suggestion.model_copy(update={"confidence_band": band})

    def evaluate_all(self, suggestions: list[InterpretationSuggestion]) -> list[InterpretationSuggestion]:
        return [self.evaluate(item) for item in suggestions]

    def default_selected(self, suggestions: list[InterpretationSuggestion]) -> list[str]:
        """Low-confidence suggestions must never be auto-selected."""
        return [item.suggestion_id for item in suggestions if item.auto_select_eligible()]

    def band_colour(self, band: ConfidenceBand) -> str:
        return {
            ConfidenceBand.HIGH: "#2ECC71",
            ConfidenceBand.MEDIUM: "#F39C12",
            ConfidenceBand.LOW: "#E74C3C",
        }[band]
