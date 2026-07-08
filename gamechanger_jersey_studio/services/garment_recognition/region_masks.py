"""Helpers for consuming segmented regions in later recognition modules."""

from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw

from models.garment_recognition.contract import GarmentRecognitionContract
from models.garment_recognition.enums import SegmentationRegionId
from models.garment_recognition.sections import BoundingBox, PolygonRegion, SegmentedRegion


def rle_to_mask(
    rle: list[tuple[int, int, int]],
    *,
    image_size: tuple[int, int],
) -> np.ndarray:
    """Decode absolute ``(y, x_start, x_end)`` runs into a boolean mask."""
    width, height = image_size
    mask = np.zeros((height, width), dtype=bool)
    for y, x0, x1 in rle:
        if y < 0 or y >= height:
            continue
        xa = max(0, min(width, x0))
        xb = max(0, min(width, x1))
        if xb > xa:
            mask[y, xa:xb] = True
    return mask


def mask_to_rle(mask: np.ndarray) -> list[tuple[int, int, int]]:
    """Encode a boolean mask as absolute row spans."""
    runs: list[tuple[int, int, int]] = []
    height, width = mask.shape
    for y in range(height):
        row = mask[y]
        x = 0
        while x < width:
            if not row[x]:
                x += 1
                continue
            x0 = x
            while x < width and row[x]:
                x += 1
            runs.append((y, int(x0), int(x)))
    return runs


def polygon_mask(
    polygon: PolygonRegion,
    *,
    image_size: tuple[int, int],
) -> np.ndarray:
    width, height = image_size
    image = Image.new("L", (width, height), 0)
    points = polygon.to_absolute_points(image_size)
    if len(points) >= 3:
        ImageDraw.Draw(image).polygon(points, outline=1, fill=1)
    return np.array(image, dtype=bool)


def region_mask(
    region: SegmentedRegion,
    *,
    image_size: tuple[int, int],
) -> np.ndarray:
    if region.mask_rle:
        return rle_to_mask(region.mask_rle, image_size=image_size)
    if region.polygon is not None:
        return polygon_mask(region.polygon, image_size=image_size)
    if region.bounding_box is not None:
        mask = np.zeros((image_size[1], image_size[0]), dtype=bool)
        x0, y0, x1, y1 = region.bounding_box.to_absolute_xyxy(image_size)
        x0, y0 = max(0, x0), max(0, y0)
        x1, y1 = min(image_size[0], x1), min(image_size[1], y1)
        mask[y0:y1, x0:x1] = True
        return mask
    return np.zeros((image_size[1], image_size[0]), dtype=bool)


def exclusion_union_mask(
    contract: GarmentRecognitionContract,
    *,
    image_size: tuple[int, int] | None = None,
) -> np.ndarray:
    """Boolean mask of all branding exclusion regions."""
    width = image_size[0] if image_size else contract.segmentation.image_width
    height = image_size[1] if image_size else contract.segmentation.image_height
    size = (max(1, width), max(1, height))
    mask = np.zeros((size[1], size[0]), dtype=bool)
    for exclusion in contract.branding.exclusions:
        if exclusion.mask_rle:
            mask |= rle_to_mask(exclusion.mask_rle, image_size=size)
            continue
        poly = exclusion.polygon or (
            exclusion.region if isinstance(exclusion.region, PolygonRegion) else None
        )
        box = exclusion.bounding_box or (
            exclusion.region if isinstance(exclusion.region, BoundingBox) else None
        )
        if poly is not None:
            mask |= polygon_mask(poly, image_size=size)
        elif box is not None:
            x0, y0, x1, y1 = box.to_absolute_xyxy(size)
            mask[max(0, y0) : min(size[1], y1), max(0, x0) : min(size[0], x1)] = True
    return mask


def analysis_mask_for_region(
    contract: GarmentRecognitionContract,
    region_id: SegmentationRegionId,
    *,
    exclude_branding: bool = True,
) -> np.ndarray:
    """Mask for a construction region with branding removed — for future modules."""
    size = (
        max(1, contract.segmentation.image_width),
        max(1, contract.segmentation.image_height),
    )
    region = contract.segmentation.by_id(region_id)
    if region is None or region.present.detected is not True:
        return np.zeros((size[1], size[0]), dtype=bool)
    mask = region_mask(region, image_size=size)
    if exclude_branding:
        mask &= ~exclusion_union_mask(contract, image_size=size)
    return mask


def crop_region_rgba(
    image: Image.Image,
    contract: GarmentRecognitionContract,
    region_id: SegmentationRegionId,
    *,
    exclude_branding: bool = True,
) -> Image.Image:
    """Return an RGBA crop of ``region_id`` with outside / branding alpha = 0."""
    rgba = image.convert("RGBA")
    arr = np.array(rgba)
    mask = analysis_mask_for_region(contract, region_id, exclude_branding=exclude_branding)
    if mask.shape[:2] != arr.shape[:2]:
        raise ValueError("Segmentation image size does not match source image")
    out = arr.copy()
    out[~mask, 3] = 0
    ys, xs = np.where(mask)
    if len(xs) == 0:
        return Image.new("RGBA", (1, 1), (0, 0, 0, 0))
    x0, x1 = int(xs.min()), int(xs.max()) + 1
    y0, y1 = int(ys.min()), int(ys.max()) + 1
    return Image.fromarray(out[y0:y1, x0:x1], mode="RGBA")
