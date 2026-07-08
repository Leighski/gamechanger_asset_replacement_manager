"""Garment recognition services — Phase 1B segmentation and future modules.

Recognition modules populate ``GarmentRecognitionContract`` only.
They never talk to the renderer.
"""

from models.garment_recognition import (
    GarmentRecognitionContract,
    ModuleResult,
    RecognitionContext,
    RecognitionModule,
    RecognitionModuleBase,
    RecognitionModuleId,
    SegmentationRegionId,
    apply_contract_to_design_spec,
    build_design_spec_updates,
)
from services.garment_recognition.overlay import render_segmentation_overlay
from services.garment_recognition.region_masks import (
    analysis_mask_for_region,
    crop_region_rgba,
    exclusion_union_mask,
)
from services.garment_recognition.segmentation import GarmentSegmentationModule, segment_shirt

__all__ = [
    "GarmentRecognitionContract",
    "GarmentSegmentationModule",
    "ModuleResult",
    "RecognitionContext",
    "RecognitionModule",
    "RecognitionModuleBase",
    "RecognitionModuleId",
    "SegmentationRegionId",
    "analysis_mask_for_region",
    "apply_contract_to_design_spec",
    "build_design_spec_updates",
    "crop_region_rgba",
    "exclusion_union_mask",
    "render_segmentation_overlay",
    "segment_shirt",
]
