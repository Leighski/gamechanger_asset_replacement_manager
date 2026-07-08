"""Confidence primitives for the Garment Recognition Contract.

Every detected property carries:
  detected value → mapped Gamechanger value → confidence → needs_review
"""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

from models.interpretation import ConfidenceBand
from models.production import ConfidenceThresholds

T = TypeVar("T")


# Default review gate — aligned with existing ConfidenceThresholds.review_min.
DEFAULT_REVIEW_THRESHOLD = 85.0


class DetectedProperty(BaseModel, Generic[T]):
    """One recognized attribute with explicit detect → map separation.

    ``detected`` describes what exists on the uploaded shirt.
    ``mapped`` is the Gamechanger-supported equivalent written into Design Spec
    (when the property is eligible for projection). Branding properties must
    never carry a mapped Design Spec value.
    """

    detected: T | None = None
    mapped: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=100.0)
    needs_review: bool = False
    notes: str = ""

    def band(self, thresholds: ConfidenceThresholds | None = None) -> ConfidenceBand:
        thresholds = thresholds or ConfidenceThresholds()
        return thresholds.band_for(self.confidence)

    def require_review_if_below(
        self,
        threshold: float = DEFAULT_REVIEW_THRESHOLD,
        *,
        force: bool | None = None,
    ) -> DetectedProperty[T]:
        """Return a copy with ``needs_review`` derived from confidence."""
        if force is not None:
            return self.model_copy(update={"needs_review": force})
        needs = self.detected is not None and self.confidence < threshold
        if self.detected is None and self.mapped is None:
            needs = True
        return self.model_copy(update={"needs_review": needs})

    @property
    def is_empty(self) -> bool:
        return self.detected is None and (self.mapped is None or self.mapped == "")


def detected(
    value: T | None,
    *,
    mapped: str | None = None,
    confidence: float = 0.0,
    needs_review: bool | None = None,
    notes: str = "",
    review_threshold: float = DEFAULT_REVIEW_THRESHOLD,
) -> DetectedProperty[T]:
    """Factory that applies the default review gate unless ``needs_review`` is set."""
    prop = DetectedProperty[T](
        detected=value,
        mapped=mapped,
        confidence=confidence,
        needs_review=False,
        notes=notes,
    )
    if needs_review is not None:
        return prop.model_copy(update={"needs_review": needs_review})
    return prop.require_review_if_below(review_threshold)


class ConfidenceSummaryItem(BaseModel):
    """Flattened confidence row for the Design Detection Summary UI."""

    property_key: str
    section: str
    label: str
    detected_display: str = ""
    mapped_display: str = ""
    confidence: float = Field(ge=0.0, le=100.0)
    needs_review: bool = False
    band: ConfidenceBand = ConfidenceBand.LOW
