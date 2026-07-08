"""RC1 production validation models — benchmarking, accuracy, replay, readiness."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, Field

from models.design_specification import DesignSpecification

RC1_VALIDATION_VERSION = "1.0.0-rc.1"


class AccuracyCategory(str, Enum):
    OVERALL = "Overall"
    COLOUR = "Colour"
    PATTERN = "Pattern"
    COLLAR = "Collar"
    TRIM = "Trim"
    SLEEVE = "Sleeve"
    TEMPLATE = "Template"


class CategoryScore(BaseModel):
    """Accuracy score for one validation category."""

    category: AccuracyCategory
    score: float = Field(ge=0.0, le=100.0)
    confidence: float = Field(default=0.0, ge=0.0, le=100.0)
    matched_fields: int = 0
    total_fields: int = 0
    details: list[str] = Field(default_factory=list)


class AccuracyReport(BaseModel):
    """Complete accuracy assessment for one benchmark project."""

    project_name: str = ""
    overall: CategoryScore
    categories: list[CategoryScore] = Field(default_factory=list)
    missing_catalogue_components: list[str] = Field(default_factory=list)
    generated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )


class ValidationAssetBundle(BaseModel):
    """Paths to assets loaded in the Validation Workspace."""

    reference_images: list[str] = Field(default_factory=list)
    original_psd_path: str = ""
    studio_psd_path: str = ""
    png_preview_path: str = ""
    expected_png_path: str = ""


class PixelComparisonResult(BaseModel):
    """Result of visual pixel comparison between two images."""

    width: int = 0
    height: int = 0
    matching_pixels: int = 0
    total_pixels: int = 0
    difference_percent: float = 0.0
    accuracy_percent: float = 0.0
    diff_overlay_path: str = ""


class LayerVisibilityState(BaseModel):
    layer_name: str
    visible_before: bool = True
    visible_after: bool = True


class VisualComparisonResult(BaseModel):
    """Visual comparison summary for the Validation Workspace."""

    before_path: str = ""
    after_path: str = ""
    pixel: PixelComparisonResult | None = None
    layer_states: list[LayerVisibilityState] = Field(default_factory=list)
    slider_position: float = Field(default=0.5, ge=0.0, le=1.0)


class BenchmarkProject(BaseModel):
    """One jersey in the RC1 benchmark dataset."""

    benchmark_id: str = Field(default_factory=lambda: f"BM_{uuid4().hex[:8].upper()}")
    project_name: str
    club: str = ""
    season: str = ""
    competition: str = ""
    gjs_project_path: str = ""
    expected_psd_path: str = ""
    generated_psd_path: str = ""
    expected_spec: DesignSpecification | None = None
    generated_spec: DesignSpecification | None = None
    operator_notes: str = ""
    accuracy: AccuracyReport | None = None
    assets: ValidationAssetBundle = Field(default_factory=ValidationAssetBundle)


class BenchmarkLibrary(BaseModel):
    """Collection of benchmark projects for batch validation."""

    schema_version: str = "1.0"
    version: str = RC1_VALIDATION_VERSION
    name: str = "Gamechanger RC1 Benchmark"
    updated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )
    projects: list[BenchmarkProject] = Field(default_factory=list)


class ReplayStageType(str, Enum):
    REFERENCE_IMAGES = "Reference Images"
    VISION_ANALYSIS = "Vision Analysis"
    AI_INTERPRETATION = "AI Interpretation"
    LEARNING_RECOMMENDATIONS = "Learning Recommendations"
    OPERATOR_DECISIONS = "Operator Decisions"
    DESIGN_SPECIFICATION = "Design Specification"
    TEMPLATE_SELECTION = "Template Selection"
    PSD_RENDERING = "PSD Rendering"
    FINAL_EXPORT = "Final Export"


class ProductionReplayStep(BaseModel):
    """One step in the production replay chain."""

    step_index: int = 0
    stage: ReplayStageType
    title: str = ""
    timestamp: str = ""
    summary: str = ""
    details: dict[str, object] = Field(default_factory=dict)


class ProductionReplay(BaseModel):
    """Complete production chain for replay viewer."""

    project_name: str = ""
    project_path: str = ""
    steps: list[ProductionReplayStep] = Field(default_factory=list)
    current_step: int = 0


class BatchValidationSummary(BaseModel):
    """Aggregate results from batch benchmark validation."""

    library_name: str = ""
    project_count: int = 0
    mean_accuracy: float = 0.0
    median_accuracy: float = 0.0
    ai_acceptance_rate: float = 0.0
    learning_rule_effectiveness: float = 0.0
    average_review_time_ms: float = 0.0
    average_render_time_ms: float = 0.0
    most_corrected_fields: list[str] = Field(default_factory=list)
    missing_catalogue_components: list[str] = Field(default_factory=list)
    per_project: list[AccuracyReport] = Field(default_factory=list)
    generated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )


class RuleValidationInsight(BaseModel):
    """Knowledge Base analytics insight — never auto-modifies rules."""

    rule_id: str
    title: str = ""
    insight_type: str
    message: str = ""
    metric_value: float = 0.0


class KnowledgeBaseValidationReport(BaseModel):
    """RC1 Knowledge Base analytics — advisory only."""

    most_effective_rules: list[RuleValidationInsight] = Field(default_factory=list)
    least_effective_rules: list[RuleValidationInsight] = Field(default_factory=list)
    never_triggered_rules: list[str] = Field(default_factory=list)
    frequently_overridden_rules: list[RuleValidationInsight] = Field(default_factory=list)
    suggested_merges: list[str] = Field(default_factory=list)
    suggested_retirements: list[str] = Field(default_factory=list)


class StressTestScenario(str, Enum):
    CONSECUTIVE_RENDERS = "100 Consecutive Renders"
    LARGE_PSD = "Large PSD"
    LARGE_CATALOGUE = "Large Component Library"
    TEMPLATE_SWITCHES = "Multiple Template Switches"
    LARGE_KNOWLEDGE_BASE = "Large Knowledge Base"


class StressTestResult(BaseModel):
    """One stress test scenario result."""

    scenario: StressTestScenario
    iterations: int = 0
    success_count: int = 0
    failure_count: int = 0
    peak_memory_mb: float = 0.0
    average_duration_ms: float = 0.0
    consistent: bool = True
    notes: str = ""


class StressTestReport(BaseModel):
    """Aggregate stress test results."""

    scenarios: list[StressTestResult] = Field(default_factory=list)
    all_consistent: bool = True
    generated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )


class ReleaseRecommendation(str, Enum):
    READY = "Ready for RC1"
    CONDITIONAL = "Conditional — address outstanding issues"
    NOT_READY = "Not ready — significant issues remain"


class ReleaseReadinessReport(BaseModel):
    """RC1 release readiness assessment."""

    version: str = RC1_VALIDATION_VERSION
    test_summary: dict[str, object] = Field(default_factory=dict)
    performance_summary: dict[str, object] = Field(default_factory=dict)
    accuracy_summary: dict[str, object] = Field(default_factory=dict)
    stability_summary: dict[str, object] = Field(default_factory=dict)
    outstanding_issues: list[str] = Field(default_factory=list)
    recommendation: ReleaseRecommendation = ReleaseRecommendation.CONDITIONAL
    generated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )
