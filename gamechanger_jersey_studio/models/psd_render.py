"""Production PSD Renderer models."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

PSD_RENDERER_SCHEMA_VERSION = "1.0"
PSD_RENDERER_VERSION = "1.0.0-alpha.11"


class PSDRenderStage(str, Enum):
    OPEN_PSD = "Open PSD template"
    RESOLVE_MAPPINGS = "Resolve template mappings"
    RESOLVE_COMPONENTS = "Resolve component IDs"
    APPLY_COLOURS = "Apply colours"
    APPLY_PATTERNS = "Apply patterns"
    APPLY_TEXTURES = "Apply textures"
    UPDATE_SMART_OBJECTS = "Update Smart Objects"
    TOGGLE_LAYERS = "Toggle optional layers"
    VALIDATE = "Validate layer state"
    SAVE = "Save rendered PSD"


PIPELINE_STAGES: tuple[PSDRenderStage, ...] = (
    PSDRenderStage.OPEN_PSD,
    PSDRenderStage.RESOLVE_MAPPINGS,
    PSDRenderStage.RESOLVE_COMPONENTS,
    PSDRenderStage.APPLY_COLOURS,
    PSDRenderStage.APPLY_PATTERNS,
    PSDRenderStage.APPLY_TEXTURES,
    PSDRenderStage.UPDATE_SMART_OBJECTS,
    PSDRenderStage.TOGGLE_LAYERS,
    PSDRenderStage.VALIDATE,
    PSDRenderStage.SAVE,
)


class PSDRenderStageLog(BaseModel):
    stage: PSDRenderStage
    duration_ms: float = 0.0
    layer_name: str = ""
    message: str = ""
    success: bool = True


class PSDRenderValidationIssue(BaseModel):
    severity: str  # error | warning
    code: str
    message: str
    field_name: str = ""
    layer_name: str = ""


class PSDRenderLog(BaseModel):
    schema_version: str = PSD_RENDERER_SCHEMA_VERSION
    template_id: str = ""
    template_version: str = ""
    project_name: str = ""
    started_at: str = ""
    completed_at: str = ""
    success: bool = False
    total_ms: float = 0.0
    stages: list[PSDRenderStageLog] = Field(default_factory=list)
    component_ids: dict[str, str] = Field(default_factory=dict)
    colours_applied: dict[str, str] = Field(default_factory=dict)
    patterns_applied: list[str] = Field(default_factory=list)
    textures_applied: list[str] = Field(default_factory=list)
    smart_objects_updated: list[str] = Field(default_factory=list)
    layers_toggled: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    validation_issues: list[PSDRenderValidationIssue] = Field(default_factory=list)


class PSDRenderResult(BaseModel):
    success: bool = False
    error: str = ""
    psd_path: str = ""
    png_path: str = ""
    log_path: str = ""
    output_dir: str = ""
    log: PSDRenderLog = Field(default_factory=PSDRenderLog)


class PSDRenderProgress(BaseModel):
    current_stage: PSDRenderStage | None = None
    completed_stages: list[PSDRenderStage] = Field(default_factory=list)
    remaining_stages: list[PSDRenderStage] = Field(default_factory=list)
    current_layer: str = ""
    elapsed_ms: float = 0.0
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
