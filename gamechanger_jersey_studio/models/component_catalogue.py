"""Component Library catalogue models — permanent source of reusable design assets."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


COMPONENT_LIBRARY_SCHEMA_VERSION = "1.0"
CATALOGUE_MANAGER_VERSION = "1.0.0-alpha.8"


class ComponentCategory(str, Enum):
    COLLARS = "collars"
    SLEEVES = "sleeves"
    PATTERNS = "patterns"
    TRIMS = "trims"
    MATERIALS = "materials"
    TEXTURES = "textures"
    LIGHTING_PROFILES = "lighting_profiles"
    SHADOW_PROFILES = "shadow_profiles"
    EFFECTS = "effects"
    BUILD_PROFILES = "build_profiles"
    VALIDATION_PROFILES = "validation_profiles"
    COLOUR_PALETTES = "colour_palettes"


class ComponentStatus(str, Enum):
    DRAFT = "Draft"
    REVIEW = "Review"
    APPROVED = "Approved"
    CERTIFIED = "Certified"
    DEPRECATED = "Deprecated"


class CatalogueHistoryEventType(str, Enum):
    COMPONENT_CREATED = "Component Created"
    COMPONENT_MODIFIED = "Component Modified"
    COMPONENT_APPROVED = "Component Approved"
    COMPONENT_DEPRECATED = "Component Deprecated"
    COMPONENT_IMPORTED = "Component Imported"
    COMPONENT_EXPORTED = "Component Exported"
    CATALOGUE_LOADED = "Catalogue Loaded"


class ComponentVersionEntry(BaseModel):
    version: str
    date: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )
    notes: str = ""
    author: str = ""


class ComponentAssets(BaseModel):
    png_preview: str = ""
    svg_preview: str = ""
    psd_layer_ref: str = ""
    mask_ref: str = ""
    geometry: dict[str, Any] = Field(default_factory=dict)
    anchor_points: list[dict[str, float]] = Field(default_factory=list)
    rendering_metadata: dict[str, Any] = Field(default_factory=dict)


class CatalogueComponent(BaseModel):
    """Full component definition for the Component Library."""

    id: str
    name: str
    category: ComponentCategory
    description: str = ""
    version: str = "1.0.0"
    status: ComponentStatus = ComponentStatus.DRAFT
    preview_image: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )
    modified_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )
    author: str = ""
    notes: str = ""
    legacy_ids: list[str] = Field(default_factory=list)
    assets: ComponentAssets = Field(default_factory=ComponentAssets)
    dependencies: list[str] = Field(default_factory=list)
    version_history: list[ComponentVersionEntry] = Field(default_factory=list)

    def all_reference_ids(self) -> set[str]:
        return {self.id, *self.legacy_ids}


class CategoryCatalogue(BaseModel):
    """Versioned catalogue manifest for one category."""

    catalogue_id: str
    catalogue_version: str = "1.0.0"
    category: ComponentCategory
    components: list[CatalogueComponent] = Field(default_factory=list)


class CatalogueHistoryEntry(BaseModel):
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )
    event: CatalogueHistoryEventType
    component_id: str = ""
    category: str = ""
    details: str = ""
    user: str = ""


class CatalogueValidationIssue(BaseModel):
    severity: str  # error | warning
    category: str
    component_id: str = ""
    message: str


class ComponentLibrary(BaseModel):
    """All loaded catalogues."""

    schema_version: str = COMPONENT_LIBRARY_SCHEMA_VERSION
    catalogues: dict[str, CategoryCatalogue] = Field(default_factory=dict)

    def components_for(self, category: ComponentCategory | str) -> list[CatalogueComponent]:
        key = category.value if isinstance(category, ComponentCategory) else category
        cat = self.catalogues.get(key)
        return list(cat.components) if cat else []

    def get_component(self, category: ComponentCategory | str, component_id: str) -> CatalogueComponent | None:
        for component in self.components_for(category):
            if component_id in component.all_reference_ids():
                return component
        return None

    def all_components(self) -> list[CatalogueComponent]:
        results: list[CatalogueComponent] = []
        for catalogue in self.catalogues.values():
            results.extend(catalogue.components)
        return results


# Design-spec field → component category mapping
DESIGN_SPEC_CATALOGUE_FIELDS: dict[str, ComponentCategory] = {
    "collar_style": ComponentCategory.COLLARS,
    "sleeve_style": ComponentCategory.SLEEVES,
    "trim_style": ComponentCategory.TRIMS,
    "material_style": ComponentCategory.MATERIALS,
    "pattern": ComponentCategory.PATTERNS,
    "shadow_style": ComponentCategory.SHADOW_PROFILES,
    "lighting_style": ComponentCategory.LIGHTING_PROFILES,
    "texture_style": ComponentCategory.TEXTURES,
    "output_profile": ComponentCategory.BUILD_PROFILES,
}
