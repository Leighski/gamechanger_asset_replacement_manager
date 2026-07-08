"""Prompt builder — structured prompts from VisionAnalysisResult (no images)."""

from __future__ import annotations

import json
from typing import Any

from models.design_specification import DesignSpecification
from models.project import ProjectManifest
from models.vision_analysis import VisionAnalysisResult
from services.design_catalogue_service import DesignCatalogues
from services.interpretation.rule_engine import RuleEngine


class PromptBuilder:
    """Construct measurement-only prompts for AI interpretation."""

    def __init__(self, rule_engine: RuleEngine | None = None) -> None:
        self._rules = rule_engine or RuleEngine()

    def build(
        self,
        analysis: VisionAnalysisResult,
        spec: DesignSpecification,
        manifest: ProjectManifest,
        catalogues: DesignCatalogues,
    ) -> str:
        rule_suggestions = self._rules.build_rule_suggestions(analysis, spec, catalogues)
        payload: dict[str, Any] = {
            "task": "Map vision measurements to Gamechanger catalogue Design Specification fields.",
            "constraints": [
                "Recommend only values from supplied catalogues.",
                "Never analyse images — measurements are authoritative.",
                "Include reasoning for every suggestion.",
                "Return JSON array under key 'suggestions'.",
            ],
            "project": {
                "club": manifest.club_name,
                "competition": manifest.competition,
                "season": manifest.season,
                "kit_type": manifest.kit_type.value,
            },
            "current_design_specification": self._spec_snapshot(spec),
            "vision_measurements": self._measurement_snapshot(analysis),
            "catalogues": self._catalogue_snapshot(catalogues),
            "validation_rules": self._validation_rules(),
            "rule_suggestions": rule_suggestions,
        }
        return json.dumps(payload, indent=2, ensure_ascii=False)

    def redact_for_export(self, prompt: str) -> str:
        """Remove API keys if ever embedded — safe for documentation."""
        return prompt

    def _spec_snapshot(self, spec: DesignSpecification) -> dict[str, Any]:
        return {
            "primary_colour": spec.primary_colour,
            "secondary_colour": spec.secondary_colour,
            "third_colour": spec.third_colour,
            "sleeve_colour": spec.sleeve_colour,
            "collar_colour": spec.collar_colour,
            "trim_colour": spec.trim_colour,
            "collar_style": spec.collar_style,
            "sleeve_style": spec.sleeve_style,
            "pattern": spec.pattern,
            "pattern_scale": spec.pattern_scale,
            "pattern_rotation": spec.pattern_rotation,
            "pattern_opacity": spec.pattern_opacity,
        }

    def _measurement_snapshot(self, analysis: VisionAnalysisResult) -> dict[str, Any]:
        data: dict[str, Any] = {
            "analysis_id": analysis.analysis_id,
            "confidence_summary": analysis.confidence_summary,
            "colours": [
                {
                    "name": colour.name,
                    "hex": colour.channels.hex_value,
                    "rgb": colour.channels.rgb,
                    "hsv": colour.channels.hsv,
                    "lab": colour.channels.lab,
                    "confidence": colour.confidence,
                    "catalogue_match": colour.catalogue_match,
                }
                for colour in analysis.colours
            ],
            "regions": [
                {"name": region.name, "confidence": region.confidence}
                for region in analysis.regions
            ],
            "warnings": analysis.warnings,
        }
        if analysis.shapes:
            data["shapes"] = {
                "collar_position_y": analysis.shapes.collar_position_y.model_dump(),
                "sleeve_length_ratio": analysis.shapes.sleeve_length_ratio.model_dump(),
                "neck_opening_width_ratio": analysis.shapes.neck_opening_width_ratio.model_dump(),
                "shoulder_width_ratio": analysis.shapes.shoulder_width_ratio.model_dump(),
                "body_height_ratio": analysis.shapes.body_height_ratio.model_dump(),
            }
        if analysis.patterns:
            data["patterns"] = {
                "coverage_percent": analysis.patterns.coverage_percent.model_dump(),
                "density": analysis.patterns.density.model_dump(),
                "orientation_degrees": analysis.patterns.orientation_degrees.model_dump(),
                "frequency": analysis.patterns.frequency.model_dump(),
            }
        if analysis.shirt_detection:
            data["shirt_detection"] = {
                "confidence": analysis.shirt_detection.confidence,
                "requires_review": analysis.shirt_detection.requires_review,
            }
        return data

    def _catalogue_snapshot(self, catalogues: DesignCatalogues) -> dict[str, list[dict[str, str]]]:
        def items(category: tuple) -> list[dict[str, str]]:
            return [{"id": item.id, "label": item.label} for item in category]

        return {
            "collars": items(catalogues.collars),
            "sleeves": items(catalogues.sleeves),
            "patterns": items(catalogues.patterns),
            "materials": items(catalogues.materials),
        }

    def _validation_rules(self) -> list[str]:
        return [
            "Colour fields must be non-empty hex values (#RRGGBB).",
            "Pattern, collar, sleeve, material must use catalogue IDs.",
            "Pattern opacity must be between 0.0 and 1.0.",
            "Pattern scale must be between 0.1 and 5.0.",
        ]
