"""Canonical Design Specification — permanent jersey data model."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator

from models.project import KitType, ProjectManifest, ValidationStatus

DESIGN_SPEC_SCHEMA_VERSION = "1.0"


class OutputProfile(str, Enum):
    GAMECHANGER_BROADCAST = "Gamechanger Broadcast"
    AUTHENTIC = "Authentic"
    EDITORIAL = "Editorial"
    FANTASY = "Fantasy"


class DesignSpecification(BaseModel):
    """Canonical representation of a football jersey design."""

    schema_version: str = DESIGN_SPEC_SCHEMA_VERSION

    # Project Information
    club: str = ""
    competition: str = ""
    season: str = ""
    kit_type: KitType = KitType.HOME
    manufacturer: str = ""

    # Colours
    primary_colour: str = ""
    secondary_colour: str = ""
    third_colour: str = ""
    sleeve_colour: str = ""
    collar_colour: str = ""
    trim_colour: str = ""

    # Pattern
    pattern: str = ""
    pattern_scale: float = Field(default=1.0, ge=0.1, le=5.0)
    pattern_rotation: float = Field(default=0.0, ge=-360.0, le=360.0)
    pattern_opacity: float = Field(default=1.0, ge=0.0, le=1.0)

    # Construction
    sleeve_style: str = ""
    collar_style: str = ""
    trim_style: str = ""
    material_style: str = ""

    # Effects
    shadow_style: str = ""
    lighting_style: str = ""
    texture_style: str = ""

    # Output
    output_profile: OutputProfile = OutputProfile.GAMECHANGER_BROADCAST

    # Validation & notes
    validation_status: ValidationStatus = ValidationStatus.NOT_STARTED
    operator_notes: str = ""

    @field_validator(
        "club",
        "competition",
        "season",
        "manufacturer",
        "primary_colour",
        "secondary_colour",
        "third_colour",
        "sleeve_colour",
        "collar_colour",
        "trim_colour",
        "pattern",
        "sleeve_style",
        "collar_style",
        "trim_style",
        "material_style",
        "shadow_style",
        "lighting_style",
        "texture_style",
        "operator_notes",
        mode="before",
    )
    @classmethod
    def strip_text(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip()
        return value

    @classmethod
    def from_manifest(cls, manifest: ProjectManifest) -> DesignSpecification:
        """Create a design specification seeded from project manifest."""
        profile = OutputProfile.GAMECHANGER_BROADCAST
        try:
            profile = OutputProfile(manifest.build_profile)
        except ValueError:
            pass
        return cls(
            club=manifest.club_name,
            competition=manifest.competition,
            season=manifest.season,
            kit_type=manifest.kit_type,
            output_profile=profile,
        )

    def sync_manifest(self, manifest: ProjectManifest) -> None:
        """Push editable project-information fields back to manifest."""
        manifest.club_name = self.club
        manifest.competition = self.competition
        manifest.season = self.season
        manifest.kit_type = self.kit_type
        manifest.build_profile = self.output_profile.value

    def get_field(self, name: str) -> Any:
        return getattr(self, name)

    def set_field(self, name: str, value: Any) -> None:
        setattr(self, name, value)

    def model_copy_with_field(self, name: str, value: Any) -> DesignSpecification:
        return self.model_copy(update={name: value})

    @property
    def section_fields(self) -> dict[str, tuple[str, ...]]:
        return {
            "project_information": (
                "club",
                "competition",
                "season",
                "kit_type",
                "manufacturer",
            ),
            "colours": (
                "primary_colour",
                "secondary_colour",
                "third_colour",
                "sleeve_colour",
                "collar_colour",
                "trim_colour",
            ),
            "construction": (
                "sleeve_style",
                "collar_style",
                "trim_style",
                "material_style",
            ),
            "pattern": (
                "pattern",
                "pattern_scale",
                "pattern_rotation",
                "pattern_opacity",
            ),
            "effects": (
                "shadow_style",
                "lighting_style",
                "texture_style",
            ),
            "output": ("output_profile",),
            "notes": ("operator_notes",),
        }


def _rebuild_project_document() -> None:
    from models.project import ProjectDocument
    from models.interpretation import InterpretationArchive
    from models.reference_image import ReferenceImageManifest
    from models.renderer import RendererSettings
    from models.vision_analysis import VisionAnalysisArchive

    ProjectDocument.model_rebuild(
        _types_namespace={
            "DesignSpecification": DesignSpecification,
            "ReferenceImageManifest": ReferenceImageManifest,
            "VisionAnalysisArchive": VisionAnalysisArchive,
            "InterpretationArchive": InterpretationArchive,
            "RendererSettings": RendererSettings,
        }
    )


_rebuild_project_document()
