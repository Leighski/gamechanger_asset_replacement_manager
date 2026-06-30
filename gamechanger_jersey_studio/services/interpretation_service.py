"""Interpretation Engine project integration — never modifies Design Specification directly."""

from __future__ import annotations

import json
import time
from typing import Any

from models.interpretation import (
    INTERPRETATION_ENGINE_VERSION,
    InterpretationArchive,
    InterpretationPerformance,
    InterpretationResult,
    InterpretationSuggestion,
    OperatorDecision,
    SuggestionStatus,
)
from models.project import HistoryEventType, ProjectDocument
from models.vision_analysis import VisionAnalysisResult
from services.ai_settings_manager import AISettingsManager
from services.design_catalogue_service import DesignCatalogues, load_catalogues
from services.design_specification_service import DesignSpecificationService
from services.interpretation.confidence_evaluation import ConfidenceEvaluationService
from services.interpretation.design_suggestion import DesignSuggestionService
from services.interpretation.prompt_builder import PromptBuilder
from services.interpretation.providers.registry import ProviderRegistry
from services.interpretation.rule_engine import RuleEngine
from services.interpretation.suggestion_history import SuggestionHistoryService
from services.logging_manager import get_logger
from services.project_history_service import ProjectHistoryService

logger = get_logger()

INTERPRETATION_RESULTS_NAME = "interpretation/results.json"


class InterpretationError(RuntimeError):
    """Raised when interpretation cannot complete."""


class InterpretationService:
    """Consume VisionAnalysisResult and produce operator-reviewed Design Specification suggestions."""

    def __init__(
        self,
        design_specification: DesignSpecificationService,
        history_service: ProjectHistoryService | None = None,
        *,
        catalogues: DesignCatalogues | None = None,
        ai_settings: AISettingsManager | None = None,
        application_version: str = "",
    ) -> None:
        self._design = design_specification
        self._history = history_service or ProjectHistoryService()
        self._catalogues = catalogues or load_catalogues()
        self._ai_settings = ai_settings or AISettingsManager()
        self._ai_settings.load()
        self._application_version = application_version
        self._archive = InterpretationArchive()
        self._prompt_builder = PromptBuilder()
        self._rule_engine = RuleEngine()
        self._suggestion_service = DesignSuggestionService()
        self._confidence = ConfidenceEvaluationService()
        self._feedback = SuggestionHistoryService()
        self._providers = ProviderRegistry(self._ai_settings.settings)

    @property
    def archive(self) -> InterpretationArchive:
        return self._archive

    @property
    def is_offline_mode(self) -> bool:
        return self._providers.is_offline_mode()

    def reset(self) -> None:
        self._archive = InterpretationArchive()

    def load(self, archive: InterpretationArchive | None) -> None:
        self._archive = archive or InterpretationArchive()

    def ensure_archive(self, document: ProjectDocument) -> InterpretationArchive:
        if document.interpretation_results is None:
            document.interpretation_results = InterpretationArchive()
        self._archive = document.interpretation_results
        return self._archive

    def interpret_analysis(
        self,
        document: ProjectDocument,
        analysis: VisionAnalysisResult,
        *,
        user: str,
    ) -> InterpretationResult:
        self.ensure_archive(document)
        spec = self._design.ensure_spec(document)
        started = time.perf_counter()

        prompt_started = time.perf_counter()
        prompt = self._prompt_builder.build(
            analysis,
            spec,
            document.manifest,
            self._catalogues,
        )
        prompt_ms = (time.perf_counter() - prompt_started) * 1000.0

        provider = self._providers.get_provider()
        offline = self._providers.is_offline_mode()
        logger.info(
            "AI interpretation request — analysis {} provider {}",
            analysis.analysis_id,
            provider.provider_name,
        )

        try:
            ai_started = time.perf_counter()
            response = provider.interpret(prompt)
            ai_ms = (time.perf_counter() - ai_started) * 1000.0

            process_started = time.perf_counter()
            suggestions = self._suggestion_service.from_provider_payload(
                response.suggestions,
                spec=spec,
                ai_provider=response.provider_name,
            )
            process_ms = (time.perf_counter() - process_started) * 1000.0
            total_ms = (time.perf_counter() - started) * 1000.0

            result = InterpretationResult(
                analysis_id=analysis.analysis_id,
                image_id=analysis.image_id,
                engine_version=INTERPRETATION_ENGINE_VERSION,
                ai_provider=response.provider_name,
                prompt_text=prompt,
                suggestions=suggestions,
                offline_mode=offline,
                performance=InterpretationPerformance(
                    prompt_generation_ms=round(prompt_ms, 2),
                    ai_response_ms=round(ai_ms, 2),
                    suggestion_processing_ms=round(process_ms, 2),
                    total_ms=round(total_ms, 2),
                ),
            )
            self._archive.interpretations.append(result)
            document.mark_dirty()

            self._record_history(
                document,
                HistoryEventType.AI_SUGGESTIONS_GENERATED,
                user,
                {
                    "interpretation_id": result.interpretation_id,
                    "analysis_id": analysis.analysis_id,
                    "provider": response.provider_name,
                    "suggestion_count": len(suggestions),
                    "offline_mode": offline,
                    "response_time_ms": ai_ms,
                },
            )
            logger.info(
                "AI suggestions generated — {} suggestions in {:.1f}ms (provider={})",
                len(suggestions),
                total_ms,
                response.provider_name,
            )
            return result
        except Exception as exc:
            self._record_history(
                document,
                HistoryEventType.AI_SUGGESTIONS_FAILED,
                user,
                {"analysis_id": analysis.analysis_id, "error": str(exc)},
            )
            logger.error("AI interpretation failed — {}", exc)
            raise InterpretationError(str(exc)) from exc

    def accept_suggestions(
        self,
        document: ProjectDocument,
        interpretation_id: str,
        suggestion_ids: list[str] | None,
        *,
        user: str,
        accept_all: bool = False,
        edited_values: dict[str, str] | None = None,
    ) -> list[str]:
        interpretation = self._get_interpretation(document, interpretation_id)
        edited_values = edited_values or {}
        accepted_fields: list[str] = []
        spec = self._design.ensure_spec(document)

        for suggestion in interpretation.suggestions:
            if suggestion.status != SuggestionStatus.PENDING:
                continue
            if not accept_all and suggestion_ids and suggestion.suggestion_id not in suggestion_ids:
                continue
            if not accept_all and not suggestion_ids:
                continue

            value = edited_values.get(suggestion.suggestion_id, suggestion.proposed_value)
            modified = value != suggestion.proposed_value
            valid, message = self._rule_engine.validate_proposed_change(
                spec, suggestion.target_field, value, self._catalogues
            )
            if not valid:
                raise InterpretationError(
                    f"Cannot apply {suggestion.target_field}: {message}"
                )

            self._design.apply_change(document, suggestion.target_field, value, user=user)
            spec = self._design.ensure_spec(document)

            decision = OperatorDecision.MODIFIED if modified else OperatorDecision.ACCEPTED
            status = SuggestionStatus.MODIFIED if modified else SuggestionStatus.ACCEPTED
            updated = self._feedback.mark_suggestion_status(
                suggestion,
                status,
                operator_value=value if modified else "",
            )
            self._replace_suggestion(interpretation, updated)
            self._feedback.record_decision(
                self._archive,
                interpretation_id,
                updated,
                decision,
                operator=user,
                final_value=value,
            )
            self._record_history(
                document,
                HistoryEventType.SUGGESTION_ACCEPTED if not modified else HistoryEventType.SUGGESTION_MODIFIED,
                user,
                {
                    "interpretation_id": interpretation_id,
                    "suggestion_id": suggestion.suggestion_id,
                    "field": suggestion.target_field,
                    "value": value,
                    "provider": suggestion.ai_provider,
                    "confidence": suggestion.confidence,
                },
            )
            accepted_fields.append(suggestion.target_field)

        document.mark_dirty()
        logger.info(
            "Suggestions accepted — {} field(s), rejected count {}",
            len(accepted_fields),
            self._feedback.rejected_count(self._archive),
        )
        return accepted_fields

    def reject_suggestion(
        self,
        document: ProjectDocument,
        interpretation_id: str,
        suggestion_id: str,
        *,
        user: str,
    ) -> None:
        interpretation = self._get_interpretation(document, interpretation_id)
        suggestion = self._get_suggestion(interpretation, suggestion_id)
        updated = self._feedback.mark_suggestion_status(suggestion, SuggestionStatus.REJECTED)
        self._replace_suggestion(interpretation, updated)
        self._feedback.record_decision(
            self._archive,
            interpretation_id,
            updated,
            OperatorDecision.REJECTED,
            operator=user,
        )
        document.mark_dirty()
        self._record_history(
            document,
            HistoryEventType.SUGGESTION_REJECTED,
            user,
            {
                "interpretation_id": interpretation_id,
                "suggestion_id": suggestion_id,
                "field": suggestion.target_field,
                "provider": suggestion.ai_provider,
                "confidence": suggestion.confidence,
            },
        )

    def reject_all(
        self,
        document: ProjectDocument,
        interpretation_id: str,
        *,
        user: str,
    ) -> int:
        interpretation = self._get_interpretation(document, interpretation_id)
        count = 0
        for suggestion in interpretation.suggestions:
            if suggestion.status != SuggestionStatus.PENDING:
                continue
            self.reject_suggestion(document, interpretation_id, suggestion.suggestion_id, user=user)
            count += 1
        return count

    def latest_for_analysis(self, analysis_id: str) -> InterpretationResult | None:
        return self._archive.latest_for_analysis(analysis_id)

    def default_selected_ids(self, interpretation: InterpretationResult) -> list[str]:
        return self._confidence.default_selected(interpretation.pending_suggestions())

    def _get_interpretation(self, document: ProjectDocument, interpretation_id: str) -> InterpretationResult:
        archive = self.ensure_archive(document)
        result = archive.get(interpretation_id)
        if result is None:
            raise InterpretationError(f"Interpretation not found: {interpretation_id}")
        return result

    def _get_suggestion(
        self, interpretation: InterpretationResult, suggestion_id: str
    ) -> InterpretationSuggestion:
        for suggestion in interpretation.suggestions:
            if suggestion.suggestion_id == suggestion_id:
                return suggestion
        raise InterpretationError(f"Suggestion not found: {suggestion_id}")

    def _replace_suggestion(
        self,
        interpretation: InterpretationResult,
        updated: InterpretationSuggestion,
    ) -> None:
        interpretation.suggestions = [
            updated if item.suggestion_id == updated.suggestion_id else item
            for item in interpretation.suggestions
        ]

    def _record_history(
        self,
        document: ProjectDocument,
        event: HistoryEventType,
        user: str,
        payload: dict[str, Any],
    ) -> None:
        self._history.record(
            document,
            event,
            application_version=self._application_version,
            user=user,
            details=json.dumps(payload, ensure_ascii=False),
        )
