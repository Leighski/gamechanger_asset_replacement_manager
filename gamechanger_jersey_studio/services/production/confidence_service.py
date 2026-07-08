"""Production confidence evaluation with configurable thresholds."""

from __future__ import annotations

from models.interpretation import ConfidenceBand, InterpretationSuggestion
from models.production import CONFIDENCE_BAND_LABELS, ConfidenceThresholds


class ProductionConfidenceService:
    """Evaluate suggestion confidence using configurable Settings thresholds."""

    def __init__(self, thresholds: ConfidenceThresholds | None = None) -> None:
        self._thresholds = thresholds or ConfidenceThresholds()

    @property
    def thresholds(self) -> ConfidenceThresholds:
        return self._thresholds

    def set_thresholds(self, thresholds: ConfidenceThresholds) -> None:
        self._thresholds = thresholds

    def band_for(self, value: float) -> ConfidenceBand:
        return self._thresholds.band_for(value)

    def band_label(self, band: ConfidenceBand) -> str:
        return CONFIDENCE_BAND_LABELS.get(band, band.value)

    def evaluate(self, suggestion: InterpretationSuggestion) -> InterpretationSuggestion:
        band = self.band_for(suggestion.confidence)
        return suggestion.model_copy(update={"confidence_band": band})

    def evaluate_all(self, suggestions: list[InterpretationSuggestion]) -> list[InterpretationSuggestion]:
        return [self.evaluate(item) for item in suggestions]

    def is_trusted(self, suggestion: InterpretationSuggestion) -> bool:
        return self.band_for(suggestion.confidence) == ConfidenceBand.HIGH

    def is_low_confidence(self, suggestion: InterpretationSuggestion) -> bool:
        return self.band_for(suggestion.confidence) == ConfidenceBand.LOW

    def trusted_suggestion_ids(self, suggestions: list[InterpretationSuggestion]) -> list[str]:
        from models.interpretation import SuggestionStatus

        return [
            item.suggestion_id
            for item in suggestions
            if item.status == SuggestionStatus.PENDING and self.is_trusted(item)
        ]

    def low_confidence_suggestion_ids(self, suggestions: list[InterpretationSuggestion]) -> list[str]:
        from models.interpretation import SuggestionStatus

        return [
            item.suggestion_id
            for item in suggestions
            if item.status == SuggestionStatus.PENDING and self.is_low_confidence(item)
        ]

    def average_confidence(self, suggestions: list[InterpretationSuggestion]) -> float:
        if not suggestions:
            return 0.0
        return round(sum(item.confidence for item in suggestions) / len(suggestions), 2)
