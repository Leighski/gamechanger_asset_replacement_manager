"""Visual overlay for garment segmentation review.

Shows garment outline, sleeve/collar/panel boundaries, and exclusion regions.
Does not perform colour, stripe, or pattern analysis.
"""

from __future__ import annotations

from PIL import Image, ImageDraw

from models.garment_recognition.contract import GarmentRecognitionContract
from models.garment_recognition.enums import SegmentationRegionId
from models.garment_recognition.sections import BoundingBox, PolygonRegion

# Distinct colours per construction role (RGBA).
_REGION_COLOURS: dict[SegmentationRegionId, tuple[int, int, int, int]] = {
    SegmentationRegionId.SHIRT_BOUNDARY: (60, 200, 120, 70),
    SegmentationRegionId.BACKGROUND: (40, 40, 40, 0),  # not filled
    SegmentationRegionId.COLLAR: (80, 160, 255, 90),
    SegmentationRegionId.LEFT_SLEEVE: (255, 170, 60, 90),
    SegmentationRegionId.RIGHT_SLEEVE: (255, 170, 60, 90),
    SegmentationRegionId.MAIN_BODY: (120, 220, 160, 55),
    SegmentationRegionId.LEFT_SHOULDER: (180, 120, 255, 80),
    SegmentationRegionId.RIGHT_SHOULDER: (180, 120, 255, 80),
    SegmentationRegionId.LEFT_CUFF: (255, 100, 140, 90),
    SegmentationRegionId.RIGHT_CUFF: (255, 100, 140, 90),
    SegmentationRegionId.LEFT_SIDE_PANEL: (100, 220, 220, 80),
    SegmentationRegionId.RIGHT_SIDE_PANEL: (100, 220, 220, 80),
}

_OUTLINE_COLOURS: dict[SegmentationRegionId, tuple[int, int, int, int]] = {
    key: (rgba[0], rgba[1], rgba[2], 230) for key, rgba in _REGION_COLOURS.items()
}

_EXCLUSION_FILL = (220, 40, 40, 110)
_EXCLUSION_OUTLINE = (255, 60, 60, 255)


def render_segmentation_overlay(
    image: Image.Image,
    contract: GarmentRecognitionContract,
    *,
    show_regions: bool = True,
    show_exclusions: bool = True,
    show_labels: bool = True,
    show_shirt_outline: bool = True,
) -> Image.Image:
    """Composite a review overlay onto a copy of the source image."""
    base = image.convert("RGBA")
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay, "RGBA")
    size = base.size

    if show_regions:
        for region in contract.segmentation.regions:
            if region.region_id == SegmentationRegionId.BACKGROUND:
                continue
            if region.present.detected is not True:
                continue
            if region.region_id == SegmentationRegionId.SHIRT_BOUNDARY and not show_shirt_outline:
                continue
            fill = _REGION_COLOURS.get(region.region_id, (200, 200, 200, 60))
            outline = _OUTLINE_COLOURS.get(region.region_id, (255, 255, 255, 220))
            # Shirt boundary: outline only so interior panels stay visible.
            if region.region_id == SegmentationRegionId.SHIRT_BOUNDARY:
                _draw_geometry(draw, region.polygon, region.bounding_box, size, fill=None, outline=outline, width=3)
            else:
                _draw_geometry(draw, region.polygon, region.bounding_box, size, fill=fill, outline=outline, width=2)
            if show_labels and region.bounding_box is not None:
                x0, y0, _, _ = region.bounding_box.to_absolute_xyxy(size)
                label = region.region_id.value.replace("_", " ")
                draw.text((x0 + 4, y0 + 4), label, fill=outline)

    if show_exclusions:
        for exclusion in contract.branding.exclusions:
            poly = exclusion.polygon or (
                exclusion.region if isinstance(exclusion.region, PolygonRegion) else None
            )
            box = exclusion.bounding_box or (
                exclusion.region if isinstance(exclusion.region, BoundingBox) else None
            )
            _draw_geometry(draw, poly, box, size, fill=_EXCLUSION_FILL, outline=_EXCLUSION_OUTLINE, width=2)
            if show_labels and box is not None:
                x0, y0, _, _ = box.to_absolute_xyxy(size)
                draw.text((x0 + 4, y0 + 4), f"excl:{exclusion.kind.value}", fill=_EXCLUSION_OUTLINE)

    return Image.alpha_composite(base, overlay)


def _draw_geometry(
    draw: ImageDraw.ImageDraw,
    polygon: PolygonRegion | None,
    box: BoundingBox | None,
    size: tuple[int, int],
    *,
    fill: tuple[int, int, int, int] | None,
    outline: tuple[int, int, int, int],
    width: int,
) -> None:
    if polygon is not None and len(polygon.points) >= 3:
        points = polygon.to_absolute_points(size)
        draw.polygon(points, fill=fill, outline=outline)
        # Reinforce outline for review clarity.
        if len(points) >= 2:
            draw.line(points + [points[0]], fill=outline, width=width)
        return
    if box is not None:
        x0, y0, x1, y1 = box.to_absolute_xyxy(size)
        draw.rectangle([x0, y0, x1, y1], fill=fill, outline=outline, width=width)
