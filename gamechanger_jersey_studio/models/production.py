"""Production workflow models — queue, batch rendering, metrics, and audit."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, Field

from models.interpretation import ConfidenceBand
from models.psd_render import PSDRenderLog, PSDRenderResult

PRODUCTION_SCHEMA_VERSION = "1.0"


class ConfidenceThresholds(BaseModel):
    """Configurable confidence band boundaries (Settings)."""

    trusted_min: float = Field(default=95.0, ge=0.0, le=100.0)
    review_min: float = Field(default=85.0, ge=0.0, le=100.0)

    def band_for(self, value: float) -> ConfidenceBand:
        if value >= self.trusted_min:
            return ConfidenceBand.HIGH
        if value >= self.review_min:
            return ConfidenceBand.MEDIUM
        return ConfidenceBand.LOW


CONFIDENCE_BAND_LABELS: dict[ConfidenceBand, str] = {
    ConfidenceBand.HIGH: "Trusted",
    ConfidenceBand.MEDIUM: "Review",
    ConfidenceBand.LOW: "Manual Review Required",
}


class ProductionQueueStatus(str, Enum):
    PENDING_REVIEW = "Pending Review"
    APPROVED = "Approved"
    REJECTED = "Rejected"
    READY_TO_RENDER = "Ready to Render"
    RENDERING = "Rendering"
    COMPLETED = "Completed"
    FAILED = "Failed"


class ProductionQueueItem(BaseModel):
    """One pending interpretation in the production queue."""

    item_id: str = Field(default_factory=lambda: uuid4().hex[:12])
    project_path: str
    project_name: str = ""
    club: str = ""
    season: str = ""
    competition: str = ""
    interpretation_id: str
    analysis_id: str = ""
    confidence: float = 0.0
    confidence_band: ConfidenceBand = ConfidenceBand.LOW
    status: ProductionQueueStatus = ProductionQueueStatus.PENDING_REVIEW
    template_id: str = ""
    operator: str = ""
    last_modified: str = ""
    pending_suggestion_count: int = 0
    suggestion_ids: list[str] = Field(default_factory=list)


class BatchRenderJobStatus(str, Enum):
    QUEUED = "Queued"
    RUNNING = "Running"
    PAUSED = "Paused"
    CANCELLED = "Cancelled"
    COMPLETED = "Completed"
    FAILED = "Failed"


class BatchRenderJob(BaseModel):
    """Single project in a batch render run."""

    job_id: str = Field(default_factory=lambda: uuid4().hex[:12])
    project_path: str
    project_name: str = ""
    status: BatchRenderJobStatus = BatchRenderJobStatus.QUEUED
    position: int = 0
    elapsed_ms: float = 0.0
    estimated_remaining_ms: float = 0.0
    psd_path: str = ""
    png_path: str = ""
    error: str = ""
    render_log: PSDRenderLog | None = None
    retry_count: int = 0


class BatchRenderState(BaseModel):
    """Overall batch render session state."""

    active: bool = False
    paused: bool = False
    cancelled: bool = False
    current_job_id: str = ""
    jobs: list[BatchRenderJob] = Field(default_factory=list)
    started_at: str = ""
    completed_count: int = 0
    failed_count: int = 0
    average_render_ms: float = 0.0


class SuggestionDiff(BaseModel):
    """Before/after values for a single suggested field change."""

    suggestion_id: str
    field_name: str
    current_value: str
    proposed_value: str
    confidence: float = 0.0
    confidence_band: ConfidenceBand = ConfidenceBand.LOW
    band_label: str = ""


class OperatorMetrics(BaseModel):
    """Process-improvement metrics — never alters AI behaviour."""

    projects_reviewed: int = 0
    suggestions_accepted: int = 0
    suggestions_rejected: int = 0
    suggestions_modified: int = 0
    average_review_time_ms: float = 0.0
    acceptance_rate: float = 0.0
    modification_rate: float = 0.0
    manual_override_count: int = 0
    renders_completed: int = 0
    average_render_time_ms: float = 0.0


class ProductionDashboardStats(BaseModel):
    """Aggregate production dashboard counters."""

    awaiting_review: int = 0
    ready_to_render: int = 0
    rendering: int = 0
    completed: int = 0
    failed: int = 0
    average_confidence: float = 0.0
    average_render_time_ms: float = 0.0


class AuditChainLink(BaseModel):
    """One link in the chain of custody for a rendered artwork."""

    link_type: str
    identifier: str
    version: str = ""
    timestamp: str = ""
    details: str = ""


class ProductionAuditRecord(BaseModel):
    """Complete chain of custody for one production output."""

    audit_id: str = Field(default_factory=lambda: uuid4().hex[:16])
    project_path: str
    project_name: str = ""
    render_psd_path: str = ""
    render_png_path: str = ""
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )
    chain: list[AuditChainLink] = Field(default_factory=list)


class ProductionReportType(str, Enum):
    DAILY_PRODUCTION = "Daily Production Report"
    CONFIDENCE_SUMMARY = "Confidence Summary"
    OPERATOR_ACTIVITY = "Operator Activity"
    RENDER_PERFORMANCE = "Render Performance"
    FAILURE_REPORT = "Failure Report"
    LEARNING_SUMMARY = "Learning Summary"
    TOP_RULES = "Top Rules"
    RULE_EFFECTIVENESS = "Rule Effectiveness"
    LEARNING_GROWTH = "Learning Growth"
    BATCH_VALIDATION = "Batch Validation"
    RELEASE_READINESS = "Release Readiness"
    KB_VALIDATION = "Knowledge Base Validation"


class ProductionReport(BaseModel):
    """Generated production report payload."""

    report_type: ProductionReportType
    generated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )
    title: str = ""
    summary: dict[str, object] = Field(default_factory=dict)
    sections: list[dict[str, object]] = Field(default_factory=list)
