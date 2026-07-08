"""Section models for the Garment Recognition Contract."""

from __future__ import annotations

from pydantic import BaseModel, Field

from models.garment_recognition.confidence import DetectedProperty
from models.garment_recognition.enums import (
    BrandingRegionKind,
    DetectedCollarStyle,
    DetectedSleeveConstruction,
    GarmentType,
    PanelRole,
    PatternFamily,
    SegmentationRegionId,
    StripeOrientation,
    StripeSymmetry,
    StripeTermination,
)


class BoundingBox(BaseModel):
    """Normalised image-space bounding box (0–1) or absolute pixels when ``absolute``."""

    x: float = 0.0
    y: float = 0.0
    width: float = 0.0
    height: float = 0.0
    absolute: bool = False

    @classmethod
    def from_absolute(
        cls,
        x0: int,
        y0: int,
        x1: int,
        y1: int,
        *,
        image_size: tuple[int, int] | None = None,
    ) -> BoundingBox:
        width = max(0, x1 - x0)
        height = max(0, y1 - y0)
        if image_size is None:
            return cls(x=float(x0), y=float(y0), width=float(width), height=float(height), absolute=True)
        iw, ih = max(1, image_size[0]), max(1, image_size[1])
        return cls(
            x=x0 / iw,
            y=y0 / ih,
            width=width / iw,
            height=height / ih,
            absolute=False,
        )

    def to_absolute_xyxy(self, image_size: tuple[int, int]) -> tuple[int, int, int, int]:
        iw, ih = image_size
        if self.absolute:
            x0 = int(round(self.x))
            y0 = int(round(self.y))
            x1 = int(round(self.x + self.width))
            y1 = int(round(self.y + self.height))
        else:
            x0 = int(round(self.x * iw))
            y0 = int(round(self.y * ih))
            x1 = int(round((self.x + self.width) * iw))
            y1 = int(round((self.y + self.height) * ih))
        return x0, y0, x1, y1


class PolygonRegion(BaseModel):
    """Polygon in image space — normalised (0–1) unless ``absolute``."""

    points: list[tuple[float, float]] = Field(default_factory=list)
    absolute: bool = False

    @classmethod
    def from_absolute_rect(
        cls,
        x0: int,
        y0: int,
        x1: int,
        y1: int,
        *,
        image_size: tuple[int, int] | None = None,
    ) -> PolygonRegion:
        corners = [
            (float(x0), float(y0)),
            (float(x1), float(y0)),
            (float(x1), float(y1)),
            (float(x0), float(y1)),
        ]
        if image_size is None:
            return cls(points=corners, absolute=True)
        iw, ih = max(1, image_size[0]), max(1, image_size[1])
        return cls(points=[(x / iw, y / ih) for x, y in corners], absolute=False)

    def to_absolute_points(self, image_size: tuple[int, int]) -> list[tuple[int, int]]:
        iw, ih = image_size
        if self.absolute:
            return [(int(round(x)), int(round(y))) for x, y in self.points]
        return [(int(round(x * iw)), int(round(y * ih))) for x, y in self.points]


class SegmentedRegion(BaseModel):
    """One physical construction region on the uploaded shirt.

    Future colour / stripe / pattern modules consume these regions instead of
    analysing the full image. Segmentation does not recognise design motifs.
    """

    region_id: SegmentationRegionId
    present: DetectedProperty[bool] = Field(default_factory=lambda: DetectedProperty[bool]())
    confidence: float = Field(default=0.0, ge=0.0, le=100.0)
    needs_review: bool = False
    bounding_box: BoundingBox | None = None
    polygon: PolygonRegion | None = None
    # Compact run-length encoding of a binary mask (absolute pixel spans).
    mask_rle: list[tuple[int, int, int]] = Field(
        default_factory=list,
        description="Rows of (y, x_start, x_end) absolute pixel spans.",
    )
    notes: str = ""


class SegmentationSection(BaseModel):
    """Physical shirt structure — foundation for all later recognition modules."""

    image_width: int = 0
    image_height: int = 0
    regions: list[SegmentedRegion] = Field(default_factory=list)
    overall_confidence: float = Field(default=0.0, ge=0.0, le=100.0)
    needs_review: bool = False

    def by_id(self, region_id: SegmentationRegionId) -> SegmentedRegion | None:
        for region in self.regions:
            if region.region_id == region_id:
                return region
        return None

    def construction_regions(self) -> list[SegmentedRegion]:
        skip = {SegmentationRegionId.BACKGROUND}
        return [region for region in self.regions if region.region_id not in skip]

    def present_regions(self) -> list[SegmentedRegion]:
        return [region for region in self.regions if region.present.detected is True]


class GarmentSection(BaseModel):
    garment_type: DetectedProperty[GarmentType] = Field(
        default_factory=lambda: DetectedProperty[GarmentType]()
    )
    view: DetectedProperty[str] = Field(
        default_factory=lambda: DetectedProperty[str](
            detected="front",
            mapped="front",
            confidence=100.0,
            needs_review=False,
        )
    )
    template_id: DetectedProperty[str] = Field(
        default_factory=lambda: DetectedProperty[str]()
    )


class CollarSection(BaseModel):
    detected_style: DetectedProperty[DetectedCollarStyle] = Field(
        default_factory=lambda: DetectedProperty[DetectedCollarStyle]()
    )
    mapped_collar_id: DetectedProperty[str] = Field(
        default_factory=lambda: DetectedProperty[str]()
    )
    colour: DetectedProperty[str] = Field(default_factory=lambda: DetectedProperty[str]())


class SleeveSection(BaseModel):
    construction: DetectedProperty[DetectedSleeveConstruction] = Field(
        default_factory=lambda: DetectedProperty[DetectedSleeveConstruction]()
    )
    colour: DetectedProperty[str] = Field(default_factory=lambda: DetectedProperty[str]())
    trim_colour: DetectedProperty[str] = Field(default_factory=lambda: DetectedProperty[str]())
    mapped_sleeve_id: DetectedProperty[str] = Field(
        default_factory=lambda: DetectedProperty[str]()
    )


class ColourSection(BaseModel):
    primary: DetectedProperty[str] = Field(default_factory=lambda: DetectedProperty[str]())
    secondary: DetectedProperty[str] = Field(default_factory=lambda: DetectedProperty[str]())
    accent: DetectedProperty[str] = Field(default_factory=lambda: DetectedProperty[str]())
    trim: DetectedProperty[str] = Field(default_factory=lambda: DetectedProperty[str]())


class PanelObservation(BaseModel):
    role: PanelRole
    present: DetectedProperty[bool] = Field(default_factory=lambda: DetectedProperty[bool]())
    colour: DetectedProperty[str] = Field(default_factory=lambda: DetectedProperty[str]())
    region: PolygonRegion | BoundingBox | None = None
    segmentation_ids: list[SegmentationRegionId] = Field(default_factory=list)


class PanelSection(BaseModel):
    panels: list[PanelObservation] = Field(default_factory=list)

    def by_role(self, role: PanelRole) -> PanelObservation | None:
        for panel in self.panels:
            if panel.role == role:
                return panel
        return None


class PatternSection(BaseModel):
    family: DetectedProperty[PatternFamily] = Field(
        default_factory=lambda: DetectedProperty[PatternFamily]()
    )
    mapped_pattern_id: DetectedProperty[str] = Field(
        default_factory=lambda: DetectedProperty[str]()
    )
    scale: DetectedProperty[float] = Field(default_factory=lambda: DetectedProperty[float]())
    rotation: DetectedProperty[float] = Field(default_factory=lambda: DetectedProperty[float]())
    direction: DetectedProperty[float] = Field(default_factory=lambda: DetectedProperty[float]())
    opacity: DetectedProperty[float] = Field(
        default_factory=lambda: DetectedProperty[float](
            detected=1.0,
            mapped="1.0",
            confidence=0.0,
            needs_review=True,
        )
    )


class StripeSection(BaseModel):
    """Structural stripe geometry — procedural rebuild inputs, not pixel analysis."""

    present: DetectedProperty[bool] = Field(
        default_factory=lambda: DetectedProperty[bool](detected=False, confidence=0.0)
    )
    orientation: DetectedProperty[StripeOrientation] = Field(
        default_factory=lambda: DetectedProperty[StripeOrientation]()
    )
    count: DetectedProperty[int] = Field(default_factory=lambda: DetectedProperty[int]())
    width: DetectedProperty[float] = Field(default_factory=lambda: DetectedProperty[float]())
    gap: DetectedProperty[float] = Field(default_factory=lambda: DetectedProperty[float]())
    symmetry: DetectedProperty[StripeSymmetry] = Field(
        default_factory=lambda: DetectedProperty[StripeSymmetry]()
    )
    colour: DetectedProperty[str] = Field(default_factory=lambda: DetectedProperty[str]())
    termination: DetectedProperty[StripeTermination] = Field(
        default_factory=lambda: DetectedProperty[StripeTermination]()
    )
    centre_aligned: DetectedProperty[bool] = Field(
        default_factory=lambda: DetectedProperty[bool]()
    )


class BrandingExclusion(BaseModel):
    """Identified branding / overlay region — exclusion mask only.

    Must never become a Design Specification field. Mapped values are forbidden.
    """

    kind: BrandingRegionKind
    region: PolygonRegion | BoundingBox | None = None
    polygon: PolygonRegion | None = None
    bounding_box: BoundingBox | None = None
    mask_rle: list[tuple[int, int, int]] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=100.0)
    needs_review: bool = False
    notes: str = ""


class BrandingSection(BaseModel):
    """All branding detections are exclusion regions only."""

    exclusions: list[BrandingExclusion] = Field(default_factory=list)

    def regions_of(self, kind: BrandingRegionKind) -> list[BrandingExclusion]:
        return [item for item in self.exclusions if item.kind == kind]
