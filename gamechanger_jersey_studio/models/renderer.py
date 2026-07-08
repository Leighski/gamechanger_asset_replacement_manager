"""Live Renderer models — preview assembly from certified catalogue components."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

RENDERER_SCHEMA_VERSION = "1.0"
LIVE_RENDERER_VERSION = "1.0.0-alpha.9"


class RenderQuality(str, Enum):
    DRAFT = "Draft"
    STANDARD = "Standard"
    HIGH = "High"


class RenderLayerId(str, Enum):
    PRESENTATION_BACKGROUND = "presentation_background"
    BASE_BODY = "base_body"
    SLEEVES = "sleeves"
    COLLAR = "collar"
    TRIM = "trim"
    PATTERN = "pattern"
    TEXTURE = "texture"
    SHADOWS = "shadows"
    LIGHTING = "lighting"
    HIGHLIGHTS = "highlights"


DEFAULT_LAYER_ORDER: tuple[RenderLayerId, ...] = (
    RenderLayerId.PRESENTATION_BACKGROUND,
    RenderLayerId.BASE_BODY,
    RenderLayerId.SLEEVES,
    RenderLayerId.COLLAR,
    RenderLayerId.TRIM,
    RenderLayerId.PATTERN,
    RenderLayerId.TEXTURE,
    RenderLayerId.SHADOWS,
    RenderLayerId.LIGHTING,
    RenderLayerId.HIGHLIGHTS,
)


class RendererSettings(BaseModel):
    """Per-project renderer preferences — stored in .gjs, not preview pixels."""

    schema_version: str = RENDERER_SCHEMA_VERSION
    quality: RenderQuality = RenderQuality.STANDARD
    background_colour: str = "#1A1F2E"
    layer_visibility: dict[str, bool] = Field(
        default_factory=lambda: {layer.value: True for layer in RenderLayerId}
    )
    show_inspector: bool = False

    def is_layer_visible(self, layer_id: RenderLayerId | str) -> bool:
        key = layer_id.value if isinstance(layer_id, RenderLayerId) else layer_id
        return self.layer_visibility.get(key, True)


class LayerTiming(BaseModel):
    layer_id: str
    duration_ms: float
    cache_hit: bool = False


class RenderStats(BaseModel):
    total_ms: float = 0.0
    layer_timings: list[LayerTiming] = Field(default_factory=list)
    cache_hits: int = 0
    cache_misses: int = 0
    memory_usage_mb: float = 0.0
    quality: RenderQuality = RenderQuality.STANDARD
    width: int = 0
    height: int = 0


class RenderResult(BaseModel):
    """Output of a live render — image bytes kept outside model for size."""

    model_config = {"arbitrary_types_allowed": True}

    success: bool = True
    error: str = ""
    stats: RenderStats = Field(default_factory=RenderStats)
    image_png: bytes = b""
