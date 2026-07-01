"""PSD Template Engine models — bridge between Design Specification and Photoshop."""

from __future__ import annotations

from enum import Enum
from typing import Any

from typing import Any

from pydantic import BaseModel, Field, model_validator


TEMPLATE_ENGINE_SCHEMA_VERSION = "1.0"
TEMPLATE_ENGINE_VERSION = "1.0.0-alpha.10"
UNKNOWN_TEMPLATE_LABEL = "Unknown Template"
_LEGACY_TEMPLATE_ID_FIELDS = ("template_id", "selected_template_id", "template")
_LEGACY_TEMPLATE_VERSION_FIELDS = ("version",)


class TemplateStatus(str, Enum):
    DRAFT = "Draft"
    REVIEW = "Review"
    CERTIFIED = "Certified"
    DEPRECATED = "Deprecated"


class BlendMode(str, Enum):
    NORMAL = "normal"
    MULTIPLY = "multiply"
    SCREEN = "screen"
    OVERLAY = "overlay"
    SOFT_LIGHT = "soft_light"
    HARD_LIGHT = "hard_light"
    COLOR = "color"
    LUMINOSITY = "luminosity"
    PASS_THROUGH = "pass_through"
    UNKNOWN = "unknown"


class PSDLayerNode(BaseModel):
    """Single layer or group node in PSD hierarchy."""

    layer_id: str
    name: str
    parent_id: str = ""
    kind: str = "pixel"
    visible: bool = True
    opacity: float = 1.0
    blend_mode: str = BlendMode.NORMAL.value
    is_group: bool = False
    is_smart_object: bool = False
    is_adjustment: bool = False
    has_mask: bool = False
    offset_x: int = 0
    offset_y: int = 0
    width: int = 0
    height: int = 0
    children: list[str] = Field(default_factory=list)


class SmartObjectRecord(BaseModel):
    """Indexed Smart Object inside a PSD template."""

    smart_object_id: str
    name: str
    layer_id: str
    parent_group: str = ""
    offset_x: int = 0
    offset_y: int = 0
    width: int = 0
    height: int = 0


class AnchorPoint(BaseModel):
    """Named anchor for future artwork positioning."""

    anchor_id: str
    name: str
    role: str
    x: float
    y: float
    width: float = 0.0
    height: float = 0.0
    rotation_degrees: float = 0.0
    notes: str = ""


class LayerMappingRule(BaseModel):
    """Configurable mapping from Design Specification to PSD layer."""

    mapping_id: str
    design_spec_field: str
    component_category: str = ""
    psd_layer_name: str
    psd_layer_id: str = ""
    smart_object_id: str = ""
    layer_group: str = ""
    render_layer: str = ""
    notes: str = ""


class PSDAnalysisReport(BaseModel):
    """Stored PSD analysis — never modifies the source PSD."""

    schema_version: str = TEMPLATE_ENGINE_SCHEMA_VERSION
    template_id: str
    analysed_at: str = ""
    psd_path: str = ""
    psd_version: int = 0
    canvas_width: int = 0
    canvas_height: int = 0
    resolution_ppi: float = 72.0
    colour_profile: str = ""
    colour_mode: str = ""
    layer_count: int = 0
    smart_object_count: int = 0
    group_count: int = 0
    adjustment_layer_count: int = 0
    masked_layer_count: int = 0
    layers: list[PSDLayerNode] = Field(default_factory=list)
    smart_objects: list[SmartObjectRecord] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class PSDTemplate(BaseModel):
    """Registered Gamechanger PSD template."""

    template_id: str
    name: str
    version: str
    description: str = ""
    psd_path: str = ""
    preview_image: str = ""
    status: TemplateStatus = TemplateStatus.CERTIFIED
    build_profile_compatibility: list[str] = Field(default_factory=list)
    supported_collar_types: list[str] = Field(default_factory=list)
    supported_sleeve_types: list[str] = Field(default_factory=list)
    supported_output_profiles: list[str] = Field(default_factory=list)
    slug: str = ""
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TemplateRegistry(BaseModel):
    """All registered PSD templates."""

    schema_version: str = TEMPLATE_ENGINE_SCHEMA_VERSION
    templates: list[PSDTemplate] = Field(default_factory=list)

    def get(self, template_id: str) -> PSDTemplate | None:
        for template in self.templates:
            if template.template_id == template_id:
                return template
        return None


class AnchorPointSet(BaseModel):
    template_id: str
    anchors: list[AnchorPoint] = Field(default_factory=list)


class LayerMappingSet(BaseModel):
    template_id: str
    mappings: list[LayerMappingRule] = Field(default_factory=list)

    def for_field(self, field_name: str) -> list[LayerMappingRule]:
        return [rule for rule in self.mappings if rule.design_spec_field == field_name]


class TemplateValidationIssue(BaseModel):
    severity: str  # error | warning
    code: str
    message: str
    layer_name: str = ""
    field_name: str = ""


class TemplateValidationReport(BaseModel):
    template_id: str
    valid: bool = True
    issues: list[TemplateValidationIssue] = Field(default_factory=list)
    layer_count: int = 0
    smart_object_count: int = 0
    anchor_count: int = 0
    mapping_count: int = 0


class PublishedTemplateMappings(BaseModel):
    """Published mappings consumed by the Render Engine — PSD-agnostic."""

    template_id: str
    template_version: str
    mappings: list[LayerMappingRule] = Field(default_factory=list)
    anchors: list[AnchorPoint] = Field(default_factory=list)
    analysis: PSDAnalysisReport | None = None


class TemplateProjectSettings(BaseModel):
    """Per-project template selection — stored in .gjs."""

    schema_version: str = TEMPLATE_ENGINE_SCHEMA_VERSION
    active_template_id: str = "TEMPLATE_BROADCAST_0001"
    template_version: str = ""

    @model_validator(mode="before")
    @classmethod
    def _coerce_legacy_fields(cls, data: Any) -> Any:
        """Map legacy template fields when loading older .gjs packages."""
        if not isinstance(data, dict):
            return data
        merged = dict(data)
        if not merged.get("active_template_id"):
            for legacy in _LEGACY_TEMPLATE_ID_FIELDS:
                if merged.get(legacy):
                    merged["active_template_id"] = merged[legacy]
                    break
        if not merged.get("template_version"):
            for legacy in _LEGACY_TEMPLATE_VERSION_FIELDS:
                if merged.get(legacy):
                    merged["template_version"] = merged[legacy]
                    break
        return merged

    def template_identifier(self) -> str:
        """Canonical template ID for replay and audit — never raises."""
        if self.active_template_id:
            return self.active_template_id
        return UNKNOWN_TEMPLATE_LABEL

    def template_version_label(self) -> str:
        """Template version label when recorded on the project."""
        return self.template_version

    def replay_details(self) -> dict[str, object]:
        """Safe serialisation for production replay."""
        details: dict[str, object] = {
            "active_template_id": self.template_identifier(),
        }
        version = self.template_version_label()
        if version:
            details["template_version"] = version
        return details

    def audit_details(self) -> str:
        """Summary line for production audit chain links."""
        identifier = self.template_identifier()
        version = self.template_version_label()
        if version and identifier != UNKNOWN_TEMPLATE_LABEL:
            return f"{identifier} v{version}"
        return identifier
