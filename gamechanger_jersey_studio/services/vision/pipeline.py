"""Vision Engine pipeline — orchestrates all analysis services."""

from __future__ import annotations

import time
import tracemalloc

from models.reference_image import AnalysisStatus
from models.vision_analysis import (
    PerformanceMetrics,
    SuggestedMapping,
    VisionAnalysisResult,
    VISION_ENGINE_VERSION,
)
from services.vision.background_removal import BackgroundRemover
from services.vision.colour_analysis import ColourAnalyser
from services.vision.image_loader import ImageLoader
from services.vision.image_normalisation import ImageNormaliser
from services.vision.pattern_analysis import PatternAnalyser
from services.vision.region_detection import RegionDetector
from services.vision.shape_analysis import ShapeAnalyser
from services.vision.shirt_detection import ShirtDetector


class VisionEngineError(RuntimeError):
    """Raised when image analysis cannot complete."""


class VisionEngine:
    """Measurement-based vision pipeline — never modifies source images or design spec."""

    def __init__(self) -> None:
        self._loader = ImageLoader()
        self._normaliser = ImageNormaliser()
        self._shirt_detector = ShirtDetector()
        self._background_remover = BackgroundRemover()
        self._colour_analyser = ColourAnalyser()
        self._region_detector = RegionDetector()
        self._shape_analyser = ShapeAnalyser()
        self._pattern_analyser = PatternAnalyser()

    def analyse_image(
        self,
        *,
        image_id: str,
        image_filename: str,
        image_bytes: bytes,
        orientation: int = 0,
    ) -> VisionAnalysisResult:
        started = time.perf_counter()
        tracemalloc.start()
        try:
            loaded = self._loader.load(image_bytes, orientation=orientation)
            normalised = self._normaliser.normalise(loaded)
            shirt = self._shirt_detector.detect(normalised)
            mask = self._background_remover.segment(shirt)
            colours = self._colour_analyser.analyse(shirt, mask)
            regions = self._region_detector.detect(shirt)
            shapes = self._shape_analyser.analyse(shirt)
            patterns = self._pattern_analyser.analyse(shirt, mask)
            warnings: list[str] = []
            if shirt.result.requires_review:
                warnings.append("Shirt detection confidence is low — operator review required.")
            suggested = self._build_suggestions(colours)
            confidence_summary = self._build_confidence_summary(colours, regions, patterns, shirt.result.confidence)
            _, peak = tracemalloc.get_traced_memory()
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            return VisionAnalysisResult(
                image_id=image_id,
                image_filename=image_filename,
                engine_version=VISION_ENGINE_VERSION,
                status=AnalysisStatus.COMPLETE,
                shirt_detection=shirt.result,
                colours=colours,
                regions=regions,
                shapes=shapes,
                patterns=patterns,
                warnings=warnings,
                suggested_mappings=suggested,
                performance=PerformanceMetrics(
                    processing_time_ms=round(elapsed_ms, 2),
                    image_width=loaded.width,
                    image_height=loaded.height,
                    memory_usage_mb=round(peak / (1024 * 1024), 2),
                    cpu_time_ms=round(elapsed_ms, 2),
                    gpu_usage="Not available",
                ),
                confidence_summary=confidence_summary,
            )
        except Exception as exc:
            raise VisionEngineError(str(exc)) from exc
        finally:
            tracemalloc.stop()

    def _build_suggestions(self, colours) -> list[SuggestedMapping]:
        field_map = {
            "Primary Colour": "primary_colour",
            "Secondary Colour": "secondary_colour",
            "Accent Colour": "third_colour",
            "Trim Colour": "trim_colour",
            "Collar Colour": "collar_colour",
            "Sleeve Colour": "sleeve_colour",
        }
        suggestions: list[SuggestedMapping] = []
        for colour in colours:
            field = field_map.get(colour.name)
            if not field:
                continue
            suggestions.append(
                SuggestedMapping(
                    design_spec_field=field,
                    suggested_value=colour.channels.hex_value,
                    confidence=colour.confidence,
                    source_measurement=colour.name,
                )
            )
        return suggestions

    def _build_confidence_summary(self, colours, regions, patterns, shirt_confidence) -> dict[str, float]:
        summary = {"Shirt Detection": shirt_confidence}
        for colour in colours:
            summary[colour.name] = colour.confidence
        for region in regions:
            summary[f"{region.name} Region"] = region.confidence
        if patterns:
            summary["Pattern Density"] = patterns.density.confidence
            summary["Pattern Coverage"] = patterns.coverage_percent.confidence
        return summary
