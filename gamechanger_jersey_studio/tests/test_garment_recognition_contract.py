"""Tests for the Garment Recognition Contract (Phase 1A)."""

from __future__ import annotations

from PIL import Image

from models.design_specification import DesignSpecification
from models.garment_recognition import (
    BRANDING_SPEC_FIELDS,
    GAMECHANGER_VNECK_COLLAR_ID,
    RECOGNITION_PROJECTABLE_FIELDS,
    BrandingExclusion,
    BrandingRegionKind,
    DetectedCollarStyle,
    DetectedSleeveConstruction,
    GarmentRecognitionContract,
    GarmentType,
    ModuleResult,
    PatternFamily,
    RecognitionContext,
    RecognitionModuleBase,
    RecognitionModuleId,
    StripeOrientation,
    apply_contract_to_design_spec,
    assert_no_branding_leak,
    build_design_spec_updates,
    detected,
    map_collar,
    map_pattern_family,
    map_sleeve,
)
from models.garment_recognition.enums import RecognitionStatus


def test_empty_contract_serialises() -> None:
    contract = GarmentRecognitionContract(source_image_id="img_001")
    payload = contract.model_dump(mode="json")
    restored = GarmentRecognitionContract.model_validate(payload)
    assert restored.source_image_id == "img_001"
    assert restored.status == RecognitionStatus.EMPTY
    assert restored.schema_version == "1.0"


def test_detected_property_review_gate() -> None:
    high = detected("#FF0000", mapped="#FF0000", confidence=96.0)
    low = detected("#00FF00", mapped="#00FF00", confidence=40.0)
    assert high.needs_review is False
    assert low.needs_review is True


def test_collar_always_maps_to_vneck() -> None:
    for style in DetectedCollarStyle:
        assert map_collar(style) == GAMECHANGER_VNECK_COLLAR_ID


def test_crew_collar_projects_as_vneck() -> None:
    contract = GarmentRecognitionContract()
    contract.collar.detected_style = detected(
        DetectedCollarStyle.CREW,
        confidence=90.0,
        needs_review=False,
    )
    contract.colours.primary = detected("#1A3A6B", mapped="#1A3A6B", confidence=95.0)
    updates = build_design_spec_updates(contract)
    assert updates["collar_style"] == GAMECHANGER_VNECK_COLLAR_ID
    assert "club_badge_path" not in updates


def test_branding_never_projects_into_design_spec() -> None:
    contract = GarmentRecognitionContract()
    contract.colours.primary = detected("#FFFFFF", mapped="#FFFFFF", confidence=99.0)
    contract.branding.exclusions.append(
        BrandingExclusion(
            kind=BrandingRegionKind.SPONSOR,
            confidence=88.0,
            notes="chest sponsor",
        )
    )
    contract.branding.exclusions.append(
        BrandingExclusion(kind=BrandingRegionKind.BADGE, confidence=92.0)
    )
    updates = build_design_spec_updates(contract)
    assert_no_branding_leak(updates)
    for banned in BRANDING_SPEC_FIELDS:
        assert banned not in updates

    spec = apply_contract_to_design_spec(contract)
    assert spec.club_badge_path == ""
    assert spec.sponsor_logo_path == ""
    assert spec.enable_branding_graphics is False


def test_stripe_structure_projects_to_spec() -> None:
    contract = GarmentRecognitionContract()
    contract.stripes.present = detected(True, confidence=91.0)
    contract.stripes.orientation = detected(StripeOrientation.VERTICAL, confidence=91.0)
    contract.stripes.count = detected(5, mapped="5", confidence=88.0)
    contract.stripes.width = detected(0.12, mapped="0.12", confidence=85.0)
    contract.stripes.gap = detected(0.08, mapped="0.08", confidence=85.0)
    contract.stripes.colour = detected("#FFFFFF", mapped="#FFFFFF", confidence=90.0)
    contract.colours.primary = detected("#0000FF", mapped="#0000FF", confidence=95.0)
    contract.colours.secondary = detected("#FFFFFF", mapped="#FFFFFF", confidence=95.0)

    spec = apply_contract_to_design_spec(contract)
    assert spec.pattern == "PATTERN_0003"  # vertical stripes catalogue id
    assert spec.stripe_count == 5
    assert spec.stripe_orientation == "vertical"
    assert spec.stripe_colour == "#FFFFFF"
    assert spec.primary_colour == "#0000FF"


def test_sleeve_and_pattern_mapping() -> None:
    assert map_sleeve(DetectedSleeveConstruction.RAGLAN) == "SLEEVE_0002"
    assert map_pattern_family(PatternFamily.HALFTONE) == "PATTERN_0006"
    assert map_pattern_family(PatternFamily.CAMOUFLAGE) == "PATTERN_0006"


def test_detection_summary_flags_low_confidence() -> None:
    contract = GarmentRecognitionContract(review_threshold=85.0)
    contract.colours.primary = detected("#112233", mapped="#112233", confidence=50.0)
    contract.colours.secondary = detected("#AABBCC", mapped="#AABBCC", confidence=96.0)
    contract.refresh_review_flags()
    needing = contract.properties_needing_review()
    keys = {item.property_key for item in needing}
    assert "colours.primary" in keys
    assert "colours.secondary" not in keys


def test_apply_preserves_unrelated_spec_fields() -> None:
    existing = DesignSpecification(club="Example FC", competition="League", season="2025/26")
    contract = GarmentRecognitionContract()
    contract.colours.primary = detected("#FF0000", mapped="#FF0000", confidence=99.0)
    updated = apply_contract_to_design_spec(contract, existing)
    assert updated.club == "Example FC"
    assert updated.primary_colour == "#FF0000"


def test_projectable_fields_exclude_branding() -> None:
    assert BRANDING_SPEC_FIELDS.isdisjoint(RECOGNITION_PROJECTABLE_FIELDS)


def test_module_protocol_is_independently_testable() -> None:
    """Every recognition module must be runnable without the renderer."""

    class StubColourModule(RecognitionModuleBase):
        @property
        def module_id(self) -> RecognitionModuleId:
            return RecognitionModuleId.COLOUR

        def analyze(self, context: RecognitionContext, contract: GarmentRecognitionContract) -> ModuleResult:
            contract.colours.primary = detected("#123456", mapped="#123456", confidence=97.0)
            contract.garment.garment_type = detected(
                GarmentType.FOOTBALL_SHIRT,
                mapped=GarmentType.FOOTBALL_SHIRT.value,
                confidence=99.0,
            )
            return ModuleResult(module_id=self.module_id, contract=contract)

    image = Image.new("RGBA", (64, 80), (20, 40, 80, 255))
    context = RecognitionContext(image=image, source_image_id="stub")
    result = StubColourModule().run(context)
    assert result.success
    assert RecognitionModuleId.COLOUR in result.contract.modules_completed
    assert result.contract.colours.primary.detected == "#123456"

    # Projection path only — no renderer involvement.
    spec = apply_contract_to_design_spec(result.contract)
    assert spec.primary_colour == "#123456"
