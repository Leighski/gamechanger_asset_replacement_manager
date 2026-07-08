"""Tests for Phase 1B — Garment Segmentation."""

from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw

from models.design_specification import DesignSpecification
from models.garment_recognition import (
    BrandingRegionKind,
    PanelRole,
    RecognitionModuleId,
    SegmentationRegionId,
    apply_contract_to_design_spec,
    build_design_spec_updates,
)
from services.garment_recognition.overlay import render_segmentation_overlay
from services.garment_recognition.region_masks import (
    analysis_mask_for_region,
    exclusion_union_mask,
)
from services.garment_recognition.segmentation import GarmentSegmentationModule, segment_shirt


def _synthetic_front_shirt(size: tuple[int, int] = (400, 500)) -> Image.Image:
    """Flat-lay style shirt on a pale background — structure only."""
    width, height = size
    image = Image.new("RGB", size, (245, 245, 245))
    draw = ImageDraw.Draw(image)
    # Main body
    draw.rectangle([110, 90, 290, 430], fill=(20, 80, 160))
    # Sleeves
    draw.rectangle([30, 110, 110, 260], fill=(20, 80, 160))
    draw.rectangle([290, 110, 370, 260], fill=(20, 80, 160))
    # Collar notch
    draw.polygon([(170, 90), (230, 90), (200, 130)], fill=(245, 245, 245))
    # Fake badge / sponsor blobs (should become exclusions, not design)
    draw.ellipse([140, 160, 180, 200], fill=(240, 240, 240))
    draw.rectangle([160, 230, 240, 270], fill=(250, 250, 250))
    return image


def test_segmentation_module_is_independently_testable() -> None:
    image = _synthetic_front_shirt()
    result = segment_shirt(image, source_image_id="synth_001")
    assert result.success
    assert result.module_id == RecognitionModuleId.SEGMENTATION
    assert RecognitionModuleId.SEGMENTATION in result.contract.modules_completed


def test_detects_core_construction_regions() -> None:
    result = segment_shirt(_synthetic_front_shirt())
    seg = result.contract.segmentation
    assert seg.image_width == 400
    assert seg.image_height == 500

    required = {
        SegmentationRegionId.SHIRT_BOUNDARY,
        SegmentationRegionId.BACKGROUND,
        SegmentationRegionId.COLLAR,
        SegmentationRegionId.LEFT_SLEEVE,
        SegmentationRegionId.RIGHT_SLEEVE,
        SegmentationRegionId.MAIN_BODY,
        SegmentationRegionId.LEFT_SHOULDER,
        SegmentationRegionId.RIGHT_SHOULDER,
    }
    present_ids = {r.region_id for r in seg.regions if r.present.detected}
    assert required.issubset(present_ids)

    body = seg.by_id(SegmentationRegionId.MAIN_BODY)
    assert body is not None
    assert body.bounding_box is not None
    assert body.polygon is not None
    assert body.confidence > 0
    assert isinstance(body.needs_review, bool)


def test_each_region_has_confidence_and_geometry() -> None:
    result = segment_shirt(_synthetic_front_shirt())
    for region in result.contract.segmentation.present_regions():
        if region.region_id == SegmentationRegionId.BACKGROUND:
            continue
        assert 0.0 <= region.confidence <= 100.0
        assert region.bounding_box is not None or region.polygon is not None


def test_exclusions_never_project_to_design_spec() -> None:
    result = segment_shirt(_synthetic_front_shirt())
    contract = result.contract
    assert len(contract.branding.exclusions) >= 1
    kinds = {item.kind for item in contract.branding.exclusions}
    assert BrandingRegionKind.BADGE in kinds or BrandingRegionKind.SPONSOR in kinds

    updates = build_design_spec_updates(contract)
    for banned in (
        "club_badge_path",
        "sponsor_logo_path",
        "manufacturer_logo_path",
        "enable_branding_graphics",
    ):
        assert banned not in updates

    spec = apply_contract_to_design_spec(contract, DesignSpecification())
    assert spec.club_badge_path == ""
    assert spec.sponsor_logo_path == ""
    assert spec.enable_branding_graphics is False


def test_segmentation_does_not_set_colours_or_stripes() -> None:
    """Phase 1B sole objective is structure — no design motif recognition."""
    result = segment_shirt(_synthetic_front_shirt())
    contract = result.contract
    assert contract.colours.primary.detected is None
    assert contract.stripes.present.detected in (None, False)
    assert contract.patterns.family.detected is None


def test_analysis_mask_excludes_branding() -> None:
    result = segment_shirt(_synthetic_front_shirt())
    contract = result.contract
    body = analysis_mask_for_region(contract, SegmentationRegionId.MAIN_BODY, exclude_branding=True)
    body_raw = analysis_mask_for_region(contract, SegmentationRegionId.MAIN_BODY, exclude_branding=False)
    exclusions = exclusion_union_mask(contract)
    assert body.sum() <= body_raw.sum()
    # Branding pixels removed from analysis mask.
    assert not np.any(body & exclusions)


def test_overlay_renders_without_renderer() -> None:
    image = _synthetic_front_shirt()
    result = segment_shirt(image)
    overlay = render_segmentation_overlay(image, result.contract)
    assert overlay.size == image.size
    assert overlay.mode == "RGBA"
    # Overlay should differ from a flat conversion of the source.
    base = np.array(image.convert("RGBA"))
    out = np.array(overlay)
    assert not np.array_equal(base, out)


def test_detection_summary_includes_segmentation() -> None:
    result = segment_shirt(_synthetic_front_shirt())
    keys = {item.property_key for item in result.contract.detection_summary()}
    assert any(key.startswith("segmentation.") for key in keys)
    assert any(key.startswith("branding.") for key in keys)


def test_panels_mirror_segmentation() -> None:
    result = segment_shirt(_synthetic_front_shirt())
    roles = {panel.role for panel in result.contract.panels.panels}
    assert PanelRole.BODY in roles
    assert PanelRole.SLEEVES in roles
    assert PanelRole.COLLAR in roles


def test_module_class_matches_protocol() -> None:
    module = GarmentSegmentationModule()
    assert module.module_id == RecognitionModuleId.SEGMENTATION
