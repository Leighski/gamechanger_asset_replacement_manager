"""Interpretation Engine models — AI-assisted Design Specification suggestions."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, Field

INTERPRETATION_SCHEMA_VERSION = "1.0"
INTERPRETATION_ENGINE_VERSION = "1.0.0-alpha.7"


class ConfidenceBand(str, Enum):
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class SuggestionStatus(str, Enum):
    PENDING = "Pending"
    ACCEPTED = "Accepted"
    REJECTED = "Rejected"
    MODIFIED = "Modified"


class OperatorDecision(str, Enum):
    ACCEPTED = "Accepted"
    REJECTED = "Rejected"
    MODIFIED = "Modified"


def confidence_band(value: float) -> ConfidenceBand:
    if value >= 95.0:
        return ConfidenceBand.HIGH
    if value >= 80.0:
        return ConfidenceBand.MEDIUM
    return ConfidenceBand.LOW


class InterpretationSuggestion(BaseModel):
    """A single proposed Design Specification update from the Interpretation Engine."""

    suggestion_id: str = Field(default_factory=lambda: uuid4().hex[:12])
    target_field: str
    current_value: str = ""
    proposed_value: str
    confidence: float = Field(ge=0.0, le=100.0)
    confidence_band: ConfidenceBand = ConfidenceBand.LOW
    reasoning: str = ""
    source_measurements: list[str] = Field(default_factory=list)
    ai_provider: str = "offline"
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )
    status: SuggestionStatus = SuggestionStatus.PENDING
    operator_value: str = ""

    def effective_value(self) -> str:
        if self.status == SuggestionStatus.MODIFIED and self.operator_value:
            return self.operator_value
        return self.proposed_value

    def auto_select_eligible(self) -> bool:
        return self.confidence_band != ConfidenceBand.LOW and self.status == SuggestionStatus.PENDING


class InterpretationPerformance(BaseModel):
    prompt_generation_ms: float = 0.0
    ai_response_ms: float = 0.0
    suggestion_processing_ms: float = 0.0
    total_ms: float = 0.0


class OperatorFeedbackRecord(BaseModel):
    """Recorded operator decision for future analytics — no auto-retraining."""

    feedback_id: str = Field(default_factory=lambda: uuid4().hex[:12])
    suggestion_id: str
    interpretation_id: str
    decision: OperatorDecision
    target_field: str
    proposed_value: str
    final_value: str = ""
    confidence: float = 0.0
    ai_provider: str = ""
    operator: str = ""
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )


class InterpretationResult(BaseModel):
    """Interpretation output for one vision analysis — never writes Design Specification directly."""

    interpretation_id: str = Field(default_factory=lambda: uuid4().hex[:16])
    analysis_id: str
    image_id: str = ""
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )
    engine_version: str = INTERPRETATION_ENGINE_VERSION
    ai_provider: str = "offline"
    prompt_text: str = ""
    suggestions: list[InterpretationSuggestion] = Field(default_factory=list)
    performance: InterpretationPerformance | None = None
    offline_mode: bool = False

    def pending_suggestions(self) -> list[InterpretationSuggestion]:
        return [s for s in self.suggestions if s.status == SuggestionStatus.PENDING]


class InterpretationArchive(BaseModel):
    """All interpretation results for a project."""

    schema_version: str = INTERPRETATION_SCHEMA_VERSION
    interpretations: list[InterpretationResult] = Field(default_factory=list)
    feedback: list[OperatorFeedbackRecord] = Field(default_factory=list)

    def for_analysis(self, analysis_id: str) -> list[InterpretationResult]:
        return [item for item in self.interpretations if item.analysis_id == analysis_id]

    def latest_for_analysis(self, analysis_id: str) -> InterpretationResult | None:
        matches = self.for_analysis(analysis_id)
        if not matches:
            return None
        return sorted(matches, key=lambda item: item.created_at)[-1]

    def get(self, interpretation_id: str) -> InterpretationResult | None:
        for item in self.interpretations:
            if item.interpretation_id == interpretation_id:
                return item
        return None
