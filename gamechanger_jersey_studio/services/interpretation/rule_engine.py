"""Rule engine — map vision measurements to catalogue recommendations."""

from __future__ import annotations

from typing import Any

from models.design_specification import DesignSpecification
from models.vision_analysis import VisionAnalysisResult
from services.design_catalogue_service import CatalogueItem, DesignCatalogues
from services.design_spec_validation import validate_design_specification


COLOUR_FIELD_MAP = {
    "Primary Colour": "primary_colour",
    "Secondary Colour": "secondary_colour",
    "Accent Colour": "third_colour",
    "Trim Colour": "trim_colour",
    "Collar Colour": "collar_colour",
    "Sleeve Colour": "sleeve_colour",
}


class RuleEngine:
    """Deterministic rules converting authoritative vision measurements into catalogue mappings."""

    def build_rule_suggestions(
        self,
        analysis: VisionAnalysisResult,
        spec: DesignSpecification,
        catalogues: DesignCatalogues,
    ) -> list[dict[str, Any]]:
        suggestions: list[dict[str, Any]] = []

        for colour in analysis.colours:
            field = COLOUR_FIELD_MAP.get(colour.name)
            if not field:
                continue
            current = str(spec.get_field(field) or "")
            proposed = colour.channels.hex_value
            if current == proposed:
                continue
            reasoning = (
                f"Measured {colour.name.lower()} ({colour.channels.hex_value}) "
                f"with {colour.confidence:.0f}% confidence"
            )
            if colour.catalogue_match:
                reasoning += f"; nearest catalogue swatch is {colour.catalogue_match}"
            suggestions.append(
                {
                    "target_field": field,
                    "current_value": current,
                    "proposed_value": proposed,
                    "confidence": colour.confidence,
                    "reasoning": reasoning,
                    "source_measurements": [colour.name, f"confidence:{colour.confidence:.1f}"],
                }
            )

        if analysis.shapes:
            collar = self._suggest_collar(analysis, spec, catalogues)
            if collar:
                suggestions.append(collar)
            sleeve = self._suggest_sleeve(analysis, spec, catalogues)
            if sleeve:
                suggestions.append(sleeve)

        if analysis.patterns and analysis.patterns.coverage_percent.value > 5.0:
            pattern = self._suggest_pattern(analysis, spec, catalogues)
            if pattern:
                suggestions.append(pattern)

        return suggestions

    def validate_proposed_change(
        self,
        spec: DesignSpecification,
        field: str,
        value: str,
        catalogues: DesignCatalogues,
    ) -> tuple[bool, str]:
        candidate = spec.model_copy_with_field(field, value)
        result = validate_design_specification(candidate, catalogues)
        field_issues = [issue for issue in result.issues if issue.field == field]
        if field_issues:
            return False, field_issues[0].message
        return True, ""

    def _suggest_collar(
        self,
        analysis: VisionAnalysisResult,
        spec: DesignSpecification,
        catalogues: DesignCatalogues,
    ) -> dict[str, Any] | None:
        if analysis.shapes is None:
            return None
        neck_ratio = analysis.shapes.neck_opening_width_ratio
        collar_y = analysis.shapes.collar_position_y
        confidence = min(neck_ratio.confidence, collar_y.confidence)
        if neck_ratio.value >= 0.22:
            item = self._find_item(catalogues.collars, "v-neck")
            reasoning = (
                "Measured neck opening width ratio "
                f"({neck_ratio.value:.3f}) and collar depth most closely match the "
                f"Gamechanger {item.label} catalogue entry."
            )
        else:
            item = self._find_item(catalogues.collars, "crew")
            reasoning = (
                "Measured neck opening width ratio "
                f"({neck_ratio.value:.3f}) indicates a round crew neckline matching "
                f"the Gamechanger {item.label} catalogue entry."
            )
        current = str(spec.collar_style or "")
        if current == item.id:
            return None
        return {
            "target_field": "collar_style",
            "current_value": current,
            "proposed_value": item.id,
            "confidence": confidence,
            "reasoning": reasoning,
            "source_measurements": [
                "neck_opening_width_ratio",
                "collar_position_y",
            ],
        }

    def _suggest_sleeve(
        self,
        analysis: VisionAnalysisResult,
        spec: DesignSpecification,
        catalogues: DesignCatalogues,
    ) -> dict[str, Any] | None:
        if analysis.shapes is None:
            return None
        sleeve_ratio = analysis.shapes.sleeve_length_ratio
        if sleeve_ratio.value >= 0.38:
            item = self._find_item(catalogues.sleeves, "long")
        elif sleeve_ratio.value >= 0.22:
            item = self._find_item(catalogues.sleeves, "cap")
        else:
            item = self._find_item(catalogues.sleeves, "standard")
        current = str(spec.sleeve_style or "")
        if current == item.id:
            return None
        return {
            "target_field": "sleeve_style",
            "current_value": current,
            "proposed_value": item.id,
            "confidence": sleeve_ratio.confidence,
            "reasoning": (
                f"Measured sleeve length ratio ({sleeve_ratio.value:.3f}) maps to "
                f"Gamechanger {item.label} in the sleeve catalogue."
            ),
            "source_measurements": ["sleeve_length_ratio"],
        }

    def _suggest_pattern(
        self,
        analysis: VisionAnalysisResult,
        spec: DesignSpecification,
        catalogues: DesignCatalogues,
    ) -> dict[str, Any] | None:
        if analysis.patterns is None:
            return None
        coverage = analysis.patterns.coverage_percent
        density = analysis.patterns.density
        confidence = min(coverage.confidence, density.confidence)
        if density.value >= 0.5:
            item = self._find_item(catalogues.patterns, "stripes")
        elif coverage.value >= 40.0:
            item = self._find_item(catalogues.patterns, "hoops")
        else:
            item = self._find_item(catalogues.patterns, "solid")
        current = str(spec.pattern or "")
        if current == item.id:
            return None
        return {
            "target_field": "pattern",
            "current_value": current,
            "proposed_value": item.id,
            "confidence": confidence,
            "reasoning": (
                f"Pattern coverage {coverage.value:.1f}% and density {density.value:.3f} "
                f"suggest the Gamechanger {item.label} pattern catalogue entry."
            ),
            "source_measurements": ["pattern_coverage", "pattern_density"],
        }

    @staticmethod
    def _find_item(items: tuple[CatalogueItem, ...], item_id: str) -> CatalogueItem:
        for item in items:
            if item.id == item_id:
                return item
        return items[0]
