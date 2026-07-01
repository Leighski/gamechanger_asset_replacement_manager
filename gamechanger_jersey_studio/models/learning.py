"""Learning Mode models — organisational knowledge, not machine learning."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, Field

LEARNING_SCHEMA_VERSION = "1.0"
KNOWLEDGE_BASE_VERSION = "1.0.0"
LEARNING_MODE_VERSION = "1.0.0-alpha.13"

RULE_SUGGESTION_THRESHOLD = 3


class LearningRuleCategory(str, Enum):
    CLUB = "Club-specific"
    MANUFACTURER = "Manufacturer-specific"
    COMPETITION = "Competition-specific"
    TEMPLATE = "Template-specific"
    PATTERN = "Pattern-specific"
    COLLAR = "Collar-specific"
    SLEEVE = "Sleeve-specific"
    TRIM = "Trim-specific"
    COLOUR = "Colour-specific"
    OUTPUT_PROFILE = "Output Profile-specific"


class LearningRuleStatus(str, Enum):
    DRAFT = "Draft"
    APPROVED = "Approved"
    DISABLED = "Disabled"


class RuleSuggestionAction(str, Enum):
    CREATE = "Create Rule"
    IGNORE = "Ignore"
    REMIND_LATER = "Remind Later"


class TriggerConditions(BaseModel):
    """Conditions that must match for a rule to apply."""

    field_name: str = ""
    club: str = ""
    manufacturer: str = ""
    competition: str = ""
    season: str = ""
    kit_type: str = ""
    template_id: str = ""
    pattern: str = ""
    original_value: str = ""


class RecommendedAction(BaseModel):
    """Advisory action — never applied automatically."""

    target_field: str
    recommended_value: str = ""
    catalogue_component: str = ""
    advisory_note: str = ""
    confidence_boost: float = Field(default=0.0, ge=0.0, le=25.0)


class LearningRule(BaseModel):
    """Reusable organisational knowledge rule."""

    rule_id: str = Field(default_factory=lambda: f"LR_{uuid4().hex[:8].upper()}")
    title: str
    description: str = ""
    category: LearningRuleCategory = LearningRuleCategory.CLUB
    triggers: TriggerConditions = Field(default_factory=TriggerConditions)
    action: RecommendedAction
    confidence: float = Field(default=80.0, ge=0.0, le=100.0)
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )
    last_used: str = ""
    usage_count: int = 0
    created_by: str = ""
    status: LearningRuleStatus = LearningRuleStatus.DRAFT
    operator_notes: str = ""
    accepted_count: int = 0
    ignored_count: int = 0
    modified_count: int = 0


class LearningEvent(BaseModel):
    """Recorded manual correction before accept — operator expertise capture."""

    event_id: str = Field(default_factory=lambda: uuid4().hex[:16])
    project_path: str = ""
    project_name: str = ""
    club: str = ""
    competition: str = ""
    season: str = ""
    manufacturer: str = ""
    kit_type: str = ""
    target_field: str
    original_ai_value: str
    final_operator_value: str
    confidence: float = 0.0
    vision_measurements: list[str] = Field(default_factory=list)
    template_id: str = ""
    operator: str = ""
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )
    interpretation_id: str = ""
    suggestion_id: str = ""


class LearningRecommendation(BaseModel):
    """Advisory recommendation from an approved rule — shown alongside AI suggestions."""

    recommendation_id: str = Field(default_factory=lambda: uuid4().hex[:12])
    rule_id: str
    title: str
    message: str
    target_field: str
    recommended_value: str = ""
    advisory_note: str = ""
    confidence_boost: float = 0.0
    catalogue_component: str = ""


class RuleSuggestionPrompt(BaseModel):
    """Prompt operator to create a rule from recurring corrections."""

    prompt_id: str = Field(default_factory=lambda: uuid4().hex[:12])
    title: str
    message: str
    occurrence_count: int = 0
    sample_event_ids: list[str] = Field(default_factory=list)
    proposed_rule: LearningRule | None = None
    dismissed: bool = False
    remind_after: str = ""


class RuleUsageRecord(BaseModel):
    """Single application of a learning rule."""

    usage_id: str = Field(default_factory=lambda: uuid4().hex[:12])
    rule_id: str
    project_path: str = ""
    project_name: str = ""
    operator: str = ""
    accepted: bool = False
    ignored: bool = False
    modified: bool = False
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )


class LearningProjectRecord(BaseModel):
    """Per-project learning audit summary."""

    rules_applied: list[str] = Field(default_factory=list)
    recommendations_accepted: list[str] = Field(default_factory=list)
    recommendations_ignored: list[str] = Field(default_factory=list)


class KnowledgeBase(BaseModel):
    """Gamechanger Knowledge Base — versioned organisational rule repository."""

    schema_version: str = LEARNING_SCHEMA_VERSION
    version: str = KNOWLEDGE_BASE_VERSION
    updated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )
    rules: list[LearningRule] = Field(default_factory=list)
    events: list[LearningEvent] = Field(default_factory=list)
    usage_history: list[RuleUsageRecord] = Field(default_factory=list)
    pending_prompts: list[RuleSuggestionPrompt] = Field(default_factory=list)

    def get_rule(self, rule_id: str) -> LearningRule | None:
        for rule in self.rules:
            if rule.rule_id == rule_id:
                return rule
        return None

    def approved_rules(self) -> list[LearningRule]:
        return [r for r in self.rules if r.status == LearningRuleStatus.APPROVED]


class LearningDashboardStats(BaseModel):
    total_events: int = 0
    active_rules: int = 0
    draft_rules: int = 0
    most_used_rule: str = ""
    most_frequent_correction: str = ""
    most_improved_field: str = ""
    recent_activity_count: int = 0


class RuleAnalytics(BaseModel):
    rule_id: str
    title: str = ""
    usage_count: int = 0
    acceptance_rate: float = 0.0
    ignored_count: int = 0
    modification_rate: float = 0.0
    confidence_improvement: float = 0.0
    average_time_saved_ms: float = 0.0
