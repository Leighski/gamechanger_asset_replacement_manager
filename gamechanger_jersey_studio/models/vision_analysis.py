"""Vision Engine analysis results — separate from Design Specification."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, Field

from models.reference_image import AnalysisStatus

VISION_ANALYSIS_SCHEMA_VERSION = "1.0"
VISION_ENGINE_VERSION = "1.0.0-alpha.6"


class AnalysisReviewStatus(str, Enum):
    PENDING = "Pending Review"
    ACCEPTED = "Accepted"
    REJECTED = "Rejected"
    PARTIAL = "Partially Accepted"


class ConfidentFloat(BaseModel):
    value: float
    confidence: float = Field(ge=0.0, le=100.0)


class ConfidentInt(BaseModel):
    value: int
    confidence: float = Field(ge=0.0, le=100.0)


class ColourChannels(BaseModel):
    rgb: tuple[int, int, int]
    hsv: tuple[float, float, float]
    lab: tuple[float, float, float]
    hex_value: str


class ColourMeasurement(BaseModel):
    name: str
    channels: ColourChannels
    confidence: float = Field(ge=0.0, le=100.0)
    catalogue_match: str = ""


class RegionPolygon(BaseModel):
    name: str
    points: list[tuple[int, int]]
    confidence: float = Field(ge=0.0, le=100.0)


class ShirtDetectionResult(BaseModel):
    bounding_box: tuple[int, int, int, int]
    outline_points: list[tuple[int, int]]
    confidence: float = Field(ge=0.0, le=100.0)
    requires_review: bool = False


class ShapeMeasurements(BaseModel):
    collar_position_y: ConfidentFloat
    sleeve_length_ratio: ConfidentFloat
    neck_opening_width_ratio: ConfidentFloat
    shoulder_width_ratio: ConfidentFloat
    body_height_ratio: ConfidentFloat


class PatternMeasurements(BaseModel):
    coverage_percent: ConfidentFloat
    density: ConfidentFloat
    orientation_degrees: ConfidentFloat
    frequency: ConfidentFloat


class SuggestedMapping(BaseModel):
    mapping_id: str = Field(default_factory=lambda: uuid4().hex[:12])
    design_spec_field: str
    suggested_value: str
    confidence: float = Field(ge=0.0, le=100.0)
    source_measurement: str = ""
    accepted: bool = False


class PerformanceMetrics(BaseModel):
    processing_time_ms: float
    image_width: int
    image_height: int
    memory_usage_mb: float
    cpu_time_ms: float
    gpu_usage: str = "Not available"


class VisionAnalysisResult(BaseModel):
    """Dedicated analysis result — never written directly to Design Specification."""

    analysis_id: str = Field(default_factory=lambda: uuid4().hex[:16])
    image_id: str
    image_filename: str = ""
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )
    engine_version: str = VISION_ENGINE_VERSION
    status: AnalysisStatus = AnalysisStatus.PENDING
    review_status: AnalysisReviewStatus = AnalysisReviewStatus.PENDING

    shirt_detection: ShirtDetectionResult | None = None
    colours: list[ColourMeasurement] = Field(default_factory=list)
    regions: list[RegionPolygon] = Field(default_factory=list)
    shapes: ShapeMeasurements | None = None
    patterns: PatternMeasurements | None = None
    warnings: list[str] = Field(default_factory=list)
    suggested_mappings: list[SuggestedMapping] = Field(default_factory=list)
    performance: PerformanceMetrics | None = None
    confidence_summary: dict[str, float] = Field(default_factory=dict)

    def overall_confidence(self) -> float:
        if not self.confidence_summary:
            return 0.0
        return round(sum(self.confidence_summary.values()) / len(self.confidence_summary), 1)


class VisionAnalysisArchive(BaseModel):
    """All vision analyses for a project — multiple per image allowed."""

    schema_version: str = VISION_ANALYSIS_SCHEMA_VERSION
    analyses: list[VisionAnalysisResult] = Field(default_factory=list)

    def for_image(self, image_id: str) -> list[VisionAnalysisResult]:
        return [analysis for analysis in self.analyses if analysis.image_id == image_id]

    def latest_for_image(self, image_id: str) -> VisionAnalysisResult | None:
        matches = self.for_image(image_id)
        if not matches:
            return None
        return sorted(matches, key=lambda item: item.created_at)[-1]

    def get(self, analysis_id: str) -> VisionAnalysisResult | None:
        for analysis in self.analyses:
            if analysis.analysis_id == analysis_id:
                return analysis
        return None
