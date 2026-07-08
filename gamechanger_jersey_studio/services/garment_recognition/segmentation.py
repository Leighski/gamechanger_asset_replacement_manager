"""Garment segmentation engine — physical construction regions + exclusions.

Phase 1B: understand shirt structure only. No colour, stripe, or pattern recognition.
Populates ``GarmentRecognitionContract.segmentation`` and branding exclusions.
Never communicates with the renderer.
"""

from __future__ import annotations

import time

import numpy as np
from PIL import Image

from models.garment_recognition.confidence import detected
from models.garment_recognition.contract import GarmentRecognitionContract
from models.garment_recognition.enums import (
    BrandingRegionKind,
    GarmentType,
    PanelRole,
    RecognitionModuleId,
    SegmentationRegionId,
)
from models.garment_recognition.mapping import GAMECHANGER_PRODUCTION_TEMPLATE_ID
from models.garment_recognition.module import ModuleResult, RecognitionContext, RecognitionModuleBase
from models.garment_recognition.sections import (
    BoundingBox,
    BrandingExclusion,
    PanelObservation,
    PolygonRegion,
    SegmentedRegion,
    SegmentationSection,
)
from services.garment_recognition.region_masks import mask_to_rle
from services.vision.confidence import clamp_confidence, confidence_from_area_ratio


# Crop-relative layout fractions: (rx0, ry0, rx1, ry1) within shirt bbox.
_LAYOUT: dict[SegmentationRegionId, tuple[float, float, float, float]] = {
    SegmentationRegionId.COLLAR: (0.34, 0.0, 0.66, 0.14),
    SegmentationRegionId.LEFT_SHOULDER: (0.08, 0.10, 0.38, 0.24),
    SegmentationRegionId.RIGHT_SHOULDER: (0.62, 0.10, 0.92, 0.24),
    SegmentationRegionId.LEFT_SLEEVE: (0.0, 0.12, 0.22, 0.52),
    SegmentationRegionId.RIGHT_SLEEVE: (0.78, 0.12, 1.0, 0.52),
    SegmentationRegionId.MAIN_BODY: (0.20, 0.14, 0.80, 0.90),
    SegmentationRegionId.LEFT_SIDE_PANEL: (0.16, 0.28, 0.28, 0.82),
    SegmentationRegionId.RIGHT_SIDE_PANEL: (0.72, 0.28, 0.84, 0.82),
    SegmentationRegionId.LEFT_CUFF: (0.0, 0.46, 0.20, 0.56),
    SegmentationRegionId.RIGHT_CUFF: (0.80, 0.46, 1.0, 0.56),
}

# Typical front-kit branding priors (exclusion only) — relative to shirt crop.
_EXCLUSION_PRIORS: tuple[tuple[BrandingRegionKind, float, float, float, float, float, str], ...] = (
    # kind, rx0, ry0, rx1, ry1, confidence_scale, notes
    (BrandingRegionKind.BADGE, 0.22, 0.22, 0.38, 0.42, 0.72, "Chest badge prior"),
    (BrandingRegionKind.SPONSOR, 0.32, 0.40, 0.68, 0.58, 0.68, "Chest sponsor prior"),
    (BrandingRegionKind.MANUFACTURER, 0.62, 0.22, 0.78, 0.36, 0.62, "Manufacturer mark prior"),
    (BrandingRegionKind.SLEEVE_SPONSOR, 0.02, 0.22, 0.18, 0.38, 0.55, "Left sleeve sponsor prior"),
    (BrandingRegionKind.COMPETITION_PATCH, 0.82, 0.22, 0.96, 0.38, 0.55, "Right sleeve patch prior"),
)


class GarmentSegmentationModule(RecognitionModuleBase):
    """Segment front-view football shirt construction and exclusion regions."""

    @property
    def module_id(self) -> RecognitionModuleId:
        return RecognitionModuleId.SEGMENTATION

    def analyze(
        self,
        context: RecognitionContext,
        contract: GarmentRecognitionContract,
    ) -> ModuleResult:
        started = time.perf_counter()
        rgb = context.image.convert("RGB")
        pixels = np.array(rgb, dtype=np.uint8)
        height, width = pixels.shape[:2]
        image_size = (width, height)

        shirt_mask, boundary_box, boundary_confidence = self._detect_shirt(pixels)
        sx0, sy0, sx1, sy1 = boundary_box
        crop_w = max(1, sx1 - sx0)
        crop_h = max(1, sy1 - sy0)

        regions: list[SegmentedRegion] = []

        # Shirt boundary + background
        regions.append(
            self._region_from_mask(
                SegmentationRegionId.SHIRT_BOUNDARY,
                shirt_mask,
                image_size=image_size,
                confidence=boundary_confidence,
                review_threshold=context.review_threshold,
                notes="Foreground shirt silhouette",
            )
        )
        background_mask = ~shirt_mask
        bg_ratio = float(background_mask.mean())
        regions.append(
            self._region_from_mask(
                SegmentationRegionId.BACKGROUND,
                background_mask,
                image_size=image_size,
                confidence=clamp_confidence(boundary_confidence * 0.95),
                review_threshold=context.review_threshold,
                notes=f"Background ({bg_ratio:.0%} of frame)",
            )
        )

        for region_id, fractions in _LAYOUT.items():
            rx0, ry0, rx1, ry1 = fractions
            x0 = int(sx0 + rx0 * crop_w)
            y0 = int(sy0 + ry0 * crop_h)
            x1 = int(sx0 + rx1 * crop_w)
            y1 = int(sy0 + ry1 * crop_h)
            part = np.zeros_like(shirt_mask)
            part[max(0, y0) : min(height, y1), max(0, x0) : min(width, x1)] = True
            part &= shirt_mask
            coverage = float(part.sum()) / max(1.0, float(shirt_mask.sum()))
            # Side panels / cuffs may be absent on some kits — flag low coverage.
            present = coverage >= 0.004
            confidence = clamp_confidence(boundary_confidence * (0.75 + min(0.25, coverage * 8.0)))
            if region_id in (
                SegmentationRegionId.LEFT_SIDE_PANEL,
                SegmentationRegionId.RIGHT_SIDE_PANEL,
            ):
                # Side panels are optional; lower confidence when barely present.
                if coverage < 0.01:
                    present = False
                    confidence = clamp_confidence(boundary_confidence * 0.55)
            regions.append(
                self._region_from_mask(
                    region_id,
                    part if present else np.zeros_like(shirt_mask),
                    image_size=image_size,
                    confidence=confidence if present else clamp_confidence(confidence * 0.7),
                    review_threshold=context.review_threshold,
                    force_present=present,
                    bbox_fallback=(x0, y0, x1, y1) if present else None,
                )
            )

        overall = round(sum(r.confidence for r in regions) / max(1, len(regions)), 1)
        contract.segmentation = SegmentationSection(
            image_width=width,
            image_height=height,
            regions=regions,
            overall_confidence=overall,
            needs_review=any(r.needs_review for r in regions) or overall < context.review_threshold,
        )

        # Mirror construction into panels for Design Detection Summary continuity.
        contract.panels.panels = self._panels_from_regions(regions)

        # Garment-level identity (structure-only — still no colours).
        contract.garment.garment_type = detected(
            GarmentType.FOOTBALL_SHIRT,
            mapped=GarmentType.FOOTBALL_SHIRT.value,
            confidence=boundary_confidence,
            review_threshold=context.review_threshold,
        )
        contract.garment.template_id = detected(
            GAMECHANGER_PRODUCTION_TEMPLATE_ID,
            mapped=GAMECHANGER_PRODUCTION_TEMPLATE_ID,
            confidence=100.0,
            needs_review=False,
        )
        contract.garment.view = detected(
            "front",
            mapped="front",
            confidence=100.0,
            needs_review=False,
        )

        contract.source_image_id = context.source_image_id or contract.source_image_id
        contract.source_image_path = context.source_image_path or contract.source_image_path
        contract.review_threshold = context.review_threshold

        # Exclusion priors inside shirt (never projected to Design Spec).
        contract.branding.exclusions = self._exclusion_priors(
            shirt_box=boundary_box,
            image_size=image_size,
            shirt_confidence=boundary_confidence,
            review_threshold=context.review_threshold,
            shirt_mask=shirt_mask,
        )

        elapsed_ms = (time.perf_counter() - started) * 1000.0
        return ModuleResult(
            module_id=self.module_id,
            contract=contract,
            success=True,
            message=f"Segmented {len(regions)} regions",
            metrics={
                "elapsed_ms": round(elapsed_ms, 2),
                "shirt_confidence": boundary_confidence,
                "region_count": float(len(regions)),
                "exclusion_count": float(len(contract.branding.exclusions)),
            },
        )

    def _detect_shirt(
        self,
        pixels: np.ndarray,
    ) -> tuple[np.ndarray, tuple[int, int, int, int], float]:
        height, width = pixels.shape[:2]
        gray = np.mean(pixels.astype(np.float32), axis=2)
        # Prefer edge-of-frame background estimate.
        border = np.concatenate(
            [
                gray[0, :],
                gray[-1, :],
                gray[:, 0],
                gray[:, -1],
            ]
        )
        background = float(np.median(border))
        foreground = np.abs(gray - background) > 18.0

        margin_y = max(2, int(height * 0.06))
        margin_x = max(2, int(width * 0.06))
        foreground[:margin_y, :] = False
        foreground[-margin_y:, :] = False
        foreground[:, :margin_x] = False
        foreground[:, -margin_x:] = False

        # Morphological clean-up without depending on OpenCV / scipy.
        foreground = self._dilate(self._erode(foreground, 1), 2)

        if not foreground.any():
            box = (margin_x, margin_y, width - margin_x, height - margin_y)
            mask = np.zeros((height, width), dtype=bool)
            mask[box[1] : box[3], box[0] : box[2]] = True
            return mask, box, 35.0

        ys, xs = np.where(foreground)
        x0, x1 = int(xs.min()), int(xs.max()) + 1
        y0, y1 = int(ys.min()), int(ys.max()) + 1
        pad_x = max(2, int((x1 - x0) * 0.03))
        pad_y = max(2, int((y1 - y0) * 0.03))
        x0 = max(0, x0 - pad_x)
        y0 = max(0, y0 - pad_y)
        x1 = min(width, x1 + pad_x)
        y1 = min(height, y1 + pad_y)
        box = (x0, y0, x1, y1)

        mask = np.zeros((height, width), dtype=bool)
        mask[y0:y1, x0:x1] = foreground[y0:y1, x0:x1]
        # Fill holes inside bbox using simple row/column span fill on foreground blob.
        mask = self._fill_bbox_blob(mask, box)

        area_ratio = float(mask.sum()) / float(max(1, width * height))
        confidence = confidence_from_area_ratio(area_ratio)
        return mask, box, confidence

    @staticmethod
    def _erode(mask: np.ndarray, iterations: int = 1) -> np.ndarray:
        out = mask
        for _ in range(iterations):
            padded = np.pad(out, 1, constant_values=False)
            out = (
                padded[1:-1, 1:-1]
                & padded[:-2, 1:-1]
                & padded[2:, 1:-1]
                & padded[1:-1, :-2]
                & padded[1:-1, 2:]
            )
        return out

    @staticmethod
    def _dilate(mask: np.ndarray, iterations: int = 1) -> np.ndarray:
        out = mask
        for _ in range(iterations):
            padded = np.pad(out, 1, constant_values=False)
            out = (
                padded[1:-1, 1:-1]
                | padded[:-2, 1:-1]
                | padded[2:, 1:-1]
                | padded[1:-1, :-2]
                | padded[1:-1, 2:]
            )
        return out

    @staticmethod
    def _fill_bbox_blob(mask: np.ndarray, box: tuple[int, int, int, int]) -> np.ndarray:
        x0, y0, x1, y1 = box
        filled = mask.copy()
        for y in range(y0, y1):
            row = mask[y, x0:x1]
            if not row.any():
                continue
            xs = np.where(row)[0]
            filled[y, x0 + int(xs.min()) : x0 + int(xs.max()) + 1] = True
        return filled

    def _region_from_mask(
        self,
        region_id: SegmentationRegionId,
        mask: np.ndarray,
        *,
        image_size: tuple[int, int],
        confidence: float,
        review_threshold: float,
        notes: str = "",
        force_present: bool | None = None,
        bbox_fallback: tuple[int, int, int, int] | None = None,
    ) -> SegmentedRegion:
        present_flag = bool(mask.any()) if force_present is None else force_present
        confidence = clamp_confidence(confidence)
        needs_review = confidence < review_threshold or not present_flag
        if region_id == SegmentationRegionId.BACKGROUND:
            needs_review = confidence < review_threshold

        if present_flag and mask.any():
            ys, xs = np.where(mask)
            x0, x1 = int(xs.min()), int(xs.max()) + 1
            y0, y1 = int(ys.min()), int(ys.max()) + 1
            rle = mask_to_rle(mask)
        elif bbox_fallback is not None and present_flag:
            x0, y0, x1, y1 = bbox_fallback
            rle = []
        else:
            x0 = y0 = x1 = y1 = 0
            rle = []

        bbox = BoundingBox.from_absolute(x0, y0, x1, y1, image_size=image_size) if present_flag else None
        polygon = (
            PolygonRegion.from_absolute_rect(x0, y0, x1, y1, image_size=image_size)
            if present_flag
            else None
        )
        return SegmentedRegion(
            region_id=region_id,
            present=detected(
                present_flag,
                mapped="present" if present_flag else "absent",
                confidence=confidence,
                needs_review=needs_review,
                review_threshold=review_threshold,
            ),
            confidence=confidence,
            needs_review=needs_review,
            bounding_box=bbox,
            polygon=polygon,
            mask_rle=rle,
            notes=notes,
        )

    def _panels_from_regions(
        self,
        regions: list[SegmentedRegion],
    ) -> list[PanelObservation]:
        by_id = {region.region_id: region for region in regions}

        def _obs(
            role: PanelRole,
            ids: list[SegmentationRegionId],
        ) -> PanelObservation:
            parts = [by_id[i] for i in ids if i in by_id]
            present_any = any(p.present.detected for p in parts)
            confidence = (
                round(sum(p.confidence for p in parts) / len(parts), 1) if parts else 0.0
            )
            region_geom = parts[0].polygon if parts else None
            return PanelObservation(
                role=role,
                present=detected(
                    present_any,
                    mapped="present" if present_any else "absent",
                    confidence=confidence,
                    needs_review=any(p.needs_review for p in parts) if parts else True,
                ),
                region=region_geom,
                segmentation_ids=ids,
            )

        return [
            _obs(PanelRole.BODY, [SegmentationRegionId.MAIN_BODY]),
            _obs(
                PanelRole.SLEEVES,
                [SegmentationRegionId.LEFT_SLEEVE, SegmentationRegionId.RIGHT_SLEEVE],
            ),
            _obs(PanelRole.COLLAR, [SegmentationRegionId.COLLAR]),
            _obs(
                PanelRole.CUFFS,
                [SegmentationRegionId.LEFT_CUFF, SegmentationRegionId.RIGHT_CUFF],
            ),
            _obs(
                PanelRole.SHOULDERS,
                [SegmentationRegionId.LEFT_SHOULDER, SegmentationRegionId.RIGHT_SHOULDER],
            ),
            _obs(
                PanelRole.SIDE_PANELS,
                [SegmentationRegionId.LEFT_SIDE_PANEL, SegmentationRegionId.RIGHT_SIDE_PANEL],
            ),
        ]

    def _exclusion_priors(
        self,
        *,
        shirt_box: tuple[int, int, int, int],
        image_size: tuple[int, int],
        shirt_confidence: float,
        review_threshold: float,
        shirt_mask: np.ndarray,
    ) -> list[BrandingExclusion]:
        sx0, sy0, sx1, sy1 = shirt_box
        crop_w = max(1, sx1 - sx0)
        crop_h = max(1, sy1 - sy0)
        width, height = image_size
        exclusions: list[BrandingExclusion] = []
        for kind, rx0, ry0, rx1, ry1, scale, notes in _EXCLUSION_PRIORS:
            x0 = int(sx0 + rx0 * crop_w)
            y0 = int(sy0 + ry0 * crop_h)
            x1 = int(sx0 + rx1 * crop_w)
            y1 = int(sy0 + ry1 * crop_h)
            mask = np.zeros((height, width), dtype=bool)
            mask[max(0, y0) : min(height, y1), max(0, x0) : min(width, x1)] = True
            mask &= shirt_mask
            if not mask.any():
                continue
            confidence = clamp_confidence(shirt_confidence * scale)
            exclusions.append(
                BrandingExclusion(
                    kind=kind,
                    bounding_box=BoundingBox.from_absolute(x0, y0, x1, y1, image_size=image_size),
                    polygon=PolygonRegion.from_absolute_rect(x0, y0, x1, y1, image_size=image_size),
                    region=PolygonRegion.from_absolute_rect(x0, y0, x1, y1, image_size=image_size),
                    mask_rle=mask_to_rle(mask),
                    confidence=confidence,
                    needs_review=confidence < review_threshold,
                    notes=notes,
                )
            )
        return exclusions


def segment_shirt(
    image: Image.Image,
    *,
    source_image_id: str = "",
    source_image_path: str = "",
    review_threshold: float = 85.0,
    contract: GarmentRecognitionContract | None = None,
) -> ModuleResult:
    """Convenience entry point for tests and future orchestration."""
    module = GarmentSegmentationModule()
    context = RecognitionContext(
        image=image,
        source_image_id=source_image_id,
        source_image_path=source_image_path,
        review_threshold=review_threshold,
    )
    return module.run(context, contract)
