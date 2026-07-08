"""Design suggestion parsing and normalisation."""

from __future__ import annotations

from typing import Any

from models.design_specification import DesignSpecification
from models.interpretation import InterpretationSuggestion
from services.interpretation.confidence_evaluation import ConfidenceEvaluationService


class DesignSuggestionService:
    """Parse provider output into InterpretationSuggestion objects."""

    def __init__(self, confidence: ConfidenceEvaluationService | None = None) -> None:
        self._confidence = confidence or ConfidenceEvaluationService()

    def from_provider_payload(
        self,
        raw_suggestions: list[dict[str, Any]],
        *,
        spec: DesignSpecification,
        ai_provider: str,
    ) -> list[InterpretationSuggestion]:
        parsed: list[InterpretationSuggestion] = []
        for item in raw_suggestions:
            field = str(item.get("target_field", "")).strip()
            if not field:
                continue
            proposed = str(item.get("proposed_value", "")).strip()
            if not proposed:
                continue
            current = str(item.get("current_value", spec.get_field(field) or ""))
            confidence = float(item.get("confidence", 0.0))
            sources = item.get("source_measurements", [])
            if not isinstance(sources, list):
                sources = [str(sources)]
            suggestion = InterpretationSuggestion(
                target_field=field,
                current_value=current,
                proposed_value=proposed,
                confidence=confidence,
                reasoning=str(item.get("reasoning", "")),
                source_measurements=[str(source) for source in sources],
                ai_provider=ai_provider,
            )
            parsed.append(self._confidence.evaluate(suggestion))
        return parsed
