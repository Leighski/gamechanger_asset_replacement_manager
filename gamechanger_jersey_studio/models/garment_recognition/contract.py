"""Garment Recognition Contract — single structured model for an uploaded shirt.

Pipeline:
  Upload Image → Garment Recognition → **This Contract** → Designer Review
  → Design Specification → Renderer → Production Artwork

Recognition modules populate this contract. They must never talk to the renderer.
The Design Specification remains the only interface between recognition and rendering.
Branding detections stay on this contract as exclusion regions and are never projected.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from pydantic import BaseModel, Field

from models.garment_recognition.confidence import (
    DEFAULT_REVIEW_THRESHOLD,
    ConfidenceSummaryItem,
    DetectedProperty,
)
from models.garment_recognition.enums import RecognitionModuleId, RecognitionStatus
from models.garment_recognition.sections import (
    BrandingSection,
    CollarSection,
    ColourSection,
    GarmentSection,
    PanelSection,
    PatternSection,
    SegmentationSection,
    SleeveSection,
    StripeSection,
)
from models.interpretation import ConfidenceBand
from models.production import ConfidenceThresholds

GARMENT_RECOGNITION_SCHEMA_VERSION = "1.0"
GARMENT_RECOGNITION_CONTRACT_VERSION = "1.0.0"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class GarmentRecognitionContract(BaseModel):
    """Everything the application knows about an uploaded football shirt.

    Every future recognition engine must populate this model.
    Every designer-facing detection summary reads from this model.
    Projection into ``DesignSpecification`` is the only path to rendering.
    """

    schema_version: str = GARMENT_RECOGNITION_SCHEMA_VERSION
    contract_version: str = GARMENT_RECOGNITION_CONTRACT_VERSION
    contract_id: str = Field(default_factory=lambda: uuid4().hex[:16])
    source_image_id: str = ""
    source_image_path: str = ""
    created_at: str = Field(default_factory=_now)
    updated_at: str = Field(default_factory=_now)
    status: RecognitionStatus = RecognitionStatus.EMPTY
    review_threshold: float = Field(
        default=DEFAULT_REVIEW_THRESHOLD,
        ge=0.0,
        le=100.0,
        description="Properties at or above this confidence do not need designer review.",
    )
    modules_completed: list[RecognitionModuleId] = Field(default_factory=list)

    garment: GarmentSection = Field(default_factory=GarmentSection)
    segmentation: SegmentationSection = Field(default_factory=SegmentationSection)
    collar: CollarSection = Field(default_factory=CollarSection)
    sleeves: SleeveSection = Field(default_factory=SleeveSection)
    colours: ColourSection = Field(default_factory=ColourSection)
    panels: PanelSection = Field(default_factory=PanelSection)
    patterns: PatternSection = Field(default_factory=PatternSection)
    stripes: StripeSection = Field(default_factory=StripeSection)
    branding: BrandingSection = Field(default_factory=BrandingSection)

    operator_notes: str = ""

    def touch(self) -> None:
        self.updated_at = _now()

    def mark_module_complete(self, module_id: RecognitionModuleId) -> None:
        if module_id not in self.modules_completed:
            self.modules_completed.append(module_id)
        if self.status == RecognitionStatus.EMPTY:
            self.status = RecognitionStatus.PARTIAL
        self.touch()

    def refresh_review_flags(self, threshold: float | None = None) -> None:
        """Recompute ``needs_review`` on all detected properties from confidence."""
        gate = self.review_threshold if threshold is None else threshold
        self.review_threshold = gate

        def _refresh(prop: DetectedProperty) -> DetectedProperty:
            return prop.require_review_if_below(gate)

        self.garment.garment_type = _refresh(self.garment.garment_type)
        self.garment.view = _refresh(self.garment.view)
        self.garment.template_id = _refresh(self.garment.template_id)

        self.collar.detected_style = _refresh(self.collar.detected_style)
        self.collar.mapped_collar_id = _refresh(self.collar.mapped_collar_id)
        self.collar.colour = _refresh(self.collar.colour)

        self.sleeves.construction = _refresh(self.sleeves.construction)
        self.sleeves.colour = _refresh(self.sleeves.colour)
        self.sleeves.trim_colour = _refresh(self.sleeves.trim_colour)
        self.sleeves.mapped_sleeve_id = _refresh(self.sleeves.mapped_sleeve_id)

        self.colours.primary = _refresh(self.colours.primary)
        self.colours.secondary = _refresh(self.colours.secondary)
        self.colours.accent = _refresh(self.colours.accent)
        self.colours.trim = _refresh(self.colours.trim)

        self.patterns.family = _refresh(self.patterns.family)
        self.patterns.mapped_pattern_id = _refresh(self.patterns.mapped_pattern_id)
        self.patterns.scale = _refresh(self.patterns.scale)
        self.patterns.rotation = _refresh(self.patterns.rotation)
        self.patterns.direction = _refresh(self.patterns.direction)
        self.patterns.opacity = _refresh(self.patterns.opacity)

        self.stripes.present = _refresh(self.stripes.present)
        self.stripes.orientation = _refresh(self.stripes.orientation)
        self.stripes.count = _refresh(self.stripes.count)
        self.stripes.width = _refresh(self.stripes.width)
        self.stripes.gap = _refresh(self.stripes.gap)
        self.stripes.symmetry = _refresh(self.stripes.symmetry)
        self.stripes.colour = _refresh(self.stripes.colour)
        self.stripes.termination = _refresh(self.stripes.termination)
        self.stripes.centre_aligned = _refresh(self.stripes.centre_aligned)

        for panel in self.panels.panels:
            panel.present = _refresh(panel.present)
            panel.colour = _refresh(panel.colour)

        for region in self.segmentation.regions:
            region.present = _refresh(region.present)
            region.needs_review = region.confidence < gate or region.present.needs_review
        if self.segmentation.regions:
            self.segmentation.overall_confidence = round(
                sum(r.confidence for r in self.segmentation.regions) / len(self.segmentation.regions),
                1,
            )
            self.segmentation.needs_review = any(r.needs_review for r in self.segmentation.regions)

        for exclusion in self.branding.exclusions:
            exclusion.needs_review = exclusion.confidence < gate

        self.touch()

    def properties_needing_review(self) -> list[ConfidenceSummaryItem]:
        return [item for item in self.detection_summary() if item.needs_review]

    def detection_summary(
        self,
        thresholds: ConfidenceThresholds | None = None,
    ) -> list[ConfidenceSummaryItem]:
        """Flat Design Detection Summary for the designer review UI."""
        thresholds = thresholds or ConfidenceThresholds(
            trusted_min=95.0,
            review_min=self.review_threshold,
        )
        items: list[ConfidenceSummaryItem] = []

        def _add(
            key: str,
            section: str,
            label: str,
            prop: DetectedProperty,
            *,
            mapped_override: str | None = None,
        ) -> None:
            detected_display = "" if prop.detected is None else str(getattr(prop.detected, "value", prop.detected))
            mapped_display = mapped_override if mapped_override is not None else (prop.mapped or "")
            items.append(
                ConfidenceSummaryItem(
                    property_key=key,
                    section=section,
                    label=label,
                    detected_display=detected_display,
                    mapped_display=mapped_display,
                    confidence=prop.confidence,
                    needs_review=prop.needs_review,
                    band=prop.band(thresholds),
                )
            )

        _add("garment.type", "garment", "Garment type", self.garment.garment_type)
        _add("garment.template", "garment", "Gamechanger template", self.garment.template_id)

        for region in self.segmentation.regions:
            items.append(
                ConfidenceSummaryItem(
                    property_key=f"segmentation.{region.region_id.value}",
                    section="segmentation",
                    label=region.region_id.value.replace("_", " ").title(),
                    detected_display="present" if region.present.detected else "absent",
                    mapped_display="construction",
                    confidence=region.confidence,
                    needs_review=region.needs_review,
                    band=thresholds.band_for(region.confidence),
                )
            )

        _add("collar.style", "collar", "Detected collar", self.collar.detected_style)
        _add(
            "collar.mapped",
            "collar",
            "Mapped Gamechanger collar",
            self.collar.mapped_collar_id,
        )
        _add("collar.colour", "collar", "Collar colour", self.collar.colour)

        _add("sleeves.construction", "sleeves", "Sleeve construction", self.sleeves.construction)
        _add("sleeves.mapped", "sleeves", "Mapped sleeve", self.sleeves.mapped_sleeve_id)
        _add("sleeves.colour", "sleeves", "Sleeve colour", self.sleeves.colour)
        _add("sleeves.trim", "sleeves", "Sleeve trim", self.sleeves.trim_colour)

        _add("colours.primary", "colours", "Primary colour", self.colours.primary)
        _add("colours.secondary", "colours", "Secondary colour", self.colours.secondary)
        _add("colours.accent", "colours", "Accent colour", self.colours.accent)
        _add("colours.trim", "colours", "Trim colour", self.colours.trim)

        _add("patterns.family", "patterns", "Pattern family", self.patterns.family)
        _add("patterns.mapped", "patterns", "Mapped pattern", self.patterns.mapped_pattern_id)
        _add("patterns.scale", "patterns", "Pattern scale", self.patterns.scale)
        _add("patterns.rotation", "patterns", "Pattern rotation", self.patterns.rotation)

        _add("stripes.present", "stripes", "Stripes present", self.stripes.present)
        _add("stripes.orientation", "stripes", "Stripe orientation", self.stripes.orientation)
        _add("stripes.count", "stripes", "Stripe count", self.stripes.count)
        _add("stripes.width", "stripes", "Stripe width", self.stripes.width)
        _add("stripes.gap", "stripes", "Gap width", self.stripes.gap)
        _add("stripes.symmetry", "stripes", "Stripe symmetry", self.stripes.symmetry)
        _add("stripes.colour", "stripes", "Stripe colour", self.stripes.colour)
        _add("stripes.termination", "stripes", "Stripe termination", self.stripes.termination)

        for panel in self.panels.panels:
            role = panel.role.value
            _add(f"panels.{role}.present", "panels", f"{role} present", panel.present)
            _add(f"panels.{role}.colour", "panels", f"{role} colour", panel.colour)

        for index, exclusion in enumerate(self.branding.exclusions):
            items.append(
                ConfidenceSummaryItem(
                    property_key=f"branding.{exclusion.kind.value}.{index}",
                    section="branding",
                    label=f"Exclude {exclusion.kind.value}",
                    detected_display="exclusion",
                    mapped_display="(never projected)",
                    confidence=exclusion.confidence,
                    needs_review=exclusion.needs_review,
                    band=thresholds.band_for(exclusion.confidence),
                )
            )

        return items

    def overall_confidence(self) -> float:
        summary = self.detection_summary()
        if not summary:
            return 0.0
        return round(sum(item.confidence for item in summary) / len(summary), 1)

    def review_required(self) -> bool:
        return any(item.needs_review for item in self.detection_summary())

    def high_confidence_count(self, thresholds: ConfidenceThresholds | None = None) -> tuple[int, int]:
        summary = self.detection_summary(thresholds)
        trusted = sum(1 for item in summary if item.band == ConfidenceBand.HIGH)
        return trusted, len(summary)
