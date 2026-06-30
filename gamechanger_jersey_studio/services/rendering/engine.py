"""Rendering Engine — orchestrates live jersey preview assembly."""

from __future__ import annotations

import time
from typing import Callable

from PIL import Image

from models.design_specification import DesignSpecification
from models.renderer import LayerTiming, RenderLayerId, RendererSettings, RenderQuality, RenderResult, RenderStats
from services.catalogue_manager_service import CatalogueManagerService
from services.logging_manager import get_logger
from services.rendering.colour_mapper import ColourMapper, parse_hex_colour
from services.rendering.component_assembler import ComponentAssembler
from services.rendering.layer_manager import LayerManager
from services.rendering.lighting_engine import LightingEngine
from services.rendering.pattern_mapper import PatternMapper
from services.rendering.preview_cache import PreviewCache
from services.rendering.errors import RenderingError
from services.rendering.texture_mapper import TextureMapper

logger = get_logger()

QUALITY_DIMENSIONS: dict[RenderQuality, tuple[int, int]] = {
    RenderQuality.DRAFT: (256, 320),
    RenderQuality.STANDARD: (400, 500),
    RenderQuality.HIGH: (600, 750),
}

RESAMPLING: dict[RenderQuality, int] = {
    RenderQuality.DRAFT: Image.Resampling.BILINEAR,
    RenderQuality.STANDARD: Image.Resampling.BILINEAR,
    RenderQuality.HIGH: Image.Resampling.LANCZOS,
}


LAYER_FIELD_KEYS: dict[RenderLayerId, tuple[str, ...]] = {
    RenderLayerId.PRESENTATION_BACKGROUND: (),
    RenderLayerId.BASE_BODY: ("material_style", "primary_colour"),
    RenderLayerId.SLEEVES: ("sleeve_style", "sleeve_colour", "secondary_colour"),
    RenderLayerId.COLLAR: ("collar_style", "collar_colour"),
    RenderLayerId.TRIM: ("trim_style", "trim_colour"),
    RenderLayerId.PATTERN: (
        "pattern",
        "pattern_scale",
        "pattern_rotation",
        "pattern_opacity",
        "secondary_colour",
        "third_colour",
    ),
    RenderLayerId.TEXTURE: ("texture_style", "material_style"),
    RenderLayerId.SHADOWS: ("shadow_style",),
    RenderLayerId.LIGHTING: ("lighting_style",),
    RenderLayerId.HIGHLIGHTS: ("lighting_style",),
}


class RenderingEngine:
    """Assemble jersey previews from certified catalogue components."""

    def __init__(self, catalogue: CatalogueManagerService) -> None:
        self._assembler = ComponentAssembler(catalogue)
        self._colour = ColourMapper()
        self._pattern = PatternMapper()
        self._texture = TextureMapper()
        self._lighting = LightingEngine()
        self._layers = LayerManager()
        self._cache = PreviewCache()

    @property
    def cache(self) -> PreviewCache:
        return self._cache

    def render(
        self,
        spec: DesignSpecification,
        settings: RendererSettings,
        *,
        token_check: Callable[[], bool] | None = None,
    ) -> RenderResult:
        started = time.perf_counter()
        quality = settings.quality
        width, height = QUALITY_DIMENSIONS[quality]
        size = (width, height)
        resampling = RESAMPLING[quality]
        stats = RenderStats(quality=quality, width=width, height=height)
        built: dict[RenderLayerId, Image.Image] = {}

        logger.info(
            "Render started — quality={}, size={}x{}, club={}",
            quality.value,
            width,
            height,
            spec.club or "—",
        )

        try:
            for layer_id in self._layers.ordered_layers(settings):
                if token_check is not None and not token_check():
                    return RenderResult(success=False, error="Superseded render", stats=stats)
                layer_started = time.perf_counter()
                cache_key = self._layer_cache_key(layer_id, spec, settings, width, height)
                cached = self._cache.get(layer_id.value, cache_key)
                cache_hit = cached is not None
                if cache_hit:
                    image = cached
                else:
                    image = self._build_layer(layer_id, spec, settings, size, resampling)
                    self._cache.put(layer_id.value, cache_key, image)
                built[layer_id] = image
                duration = (time.perf_counter() - layer_started) * 1000.0
                stats.layer_timings.append(
                    LayerTiming(layer_id=layer_id.value, duration_ms=round(duration, 2), cache_hit=cache_hit)
                )

            composite = self._layers.composite(built, settings)
            png_bytes = self._layers.to_png_bytes(composite)
            stats.total_ms = round((time.perf_counter() - started) * 1000.0, 2)
            stats.cache_hits = self._cache.stats.hits
            stats.cache_misses = self._cache.stats.misses
            stats.memory_usage_mb = round(self._estimate_memory_mb(), 3)
            logger.info(
                "Render completed — {:.1f}ms, cache hits={}, misses={}",
                stats.total_ms,
                stats.cache_hits,
                stats.cache_misses,
            )
            for timing in stats.layer_timings:
                logger.debug(
                    "Layer {} — {:.1f}ms ({})",
                    timing.layer_id,
                    timing.duration_ms,
                    "hit" if timing.cache_hit else "miss",
                )
            return RenderResult(success=True, stats=stats, image_png=png_bytes)
        except RenderingError as exc:
            stats.total_ms = round((time.perf_counter() - started) * 1000.0, 2)
            logger.error("Render failed — {}", exc)
            return RenderResult(success=False, error=str(exc), stats=stats)

    def _layer_cache_key(
        self,
        layer_id: RenderLayerId,
        spec: DesignSpecification,
        settings: RendererSettings,
        width: int,
        height: int,
    ) -> str:
        fields = LAYER_FIELD_KEYS.get(layer_id, ())
        parts = [layer_id.value, settings.quality.value, str(width), str(height)]
        if layer_id == RenderLayerId.PRESENTATION_BACKGROUND:
            parts.append(settings.background_colour)
        for field in fields:
            parts.append(f"{field}={spec.get_field(field)}")
        return PreviewCache.make_key(*parts)

    def _build_layer(
        self,
        layer_id: RenderLayerId,
        spec: DesignSpecification,
        settings: RendererSettings,
        size: tuple[int, int],
        resampling: int,
    ) -> Image.Image:
        width, height = size
        if layer_id == RenderLayerId.PRESENTATION_BACKGROUND:
            rgb = parse_hex_colour(settings.background_colour, (26, 31, 46))
            return Image.new("RGBA", size, (*rgb, 255))

        if layer_id == RenderLayerId.BASE_BODY:
            image, _ = self._assembler.load_field_image(
                "material_style", spec.material_style, size, resampling=resampling
            )
            return self._colour.tint_rgba(image, spec.primary_colour or "#808080")

        if layer_id == RenderLayerId.SLEEVES:
            image, _ = self._assembler.load_field_image(
                "sleeve_style", spec.sleeve_style, size, resampling=resampling
            )
            colour = spec.sleeve_colour or spec.secondary_colour or spec.primary_colour
            return self._colour.tint_rgba(image, colour or "#808080")

        if layer_id == RenderLayerId.COLLAR:
            image, _ = self._assembler.load_field_image(
                "collar_style", spec.collar_style, size, resampling=resampling
            )
            return self._colour.tint_rgba(image, spec.collar_colour or "#FFFFFF")

        if layer_id == RenderLayerId.TRIM:
            image, _ = self._assembler.load_field_image(
                "trim_style", spec.trim_style, size, resampling=resampling
            )
            return self._colour.tint_rgba(image, spec.trim_colour or spec.third_colour or "#1C1C1C")

        if layer_id == RenderLayerId.PATTERN:
            base = Image.new("RGBA", size, (0, 0, 0, 0))
            if spec.pattern:
                pattern_image, _ = self._assembler.load_field_image(
                    "pattern", spec.pattern, size, resampling=resampling
                )
                tinted = self._colour.tint_rgba(
                    pattern_image,
                    spec.secondary_colour or spec.primary_colour or "#FFFFFF",
                )
                return self._pattern.apply_pattern(
                    base,
                    tinted,
                    scale=spec.pattern_scale,
                    rotation_degrees=spec.pattern_rotation,
                    opacity=spec.pattern_opacity,
                )
            return base

        if layer_id == RenderLayerId.TEXTURE:
            if spec.texture_style:
                material, _ = self._assembler.load_field_image(
                    "material_style", spec.material_style, size, resampling=resampling
                )
                texture_image, _ = self._assembler.load_field_image(
                    "texture_style", spec.texture_style, size, resampling=resampling
                )
                masked = self._texture.apply_texture(material, texture_image, strength=0.35)
                return masked
            return Image.new("RGBA", size, (0, 0, 0, 0))

        if layer_id == RenderLayerId.SHADOWS:
            if spec.shadow_style:
                shadow_image, _ = self._assembler.load_field_image(
                    "shadow_style", spec.shadow_style, size, resampling=resampling
                )
                return self._scale_layer_alpha(shadow_image, 0.45)
            return Image.new("RGBA", size, (0, 0, 0, 0))

        if layer_id == RenderLayerId.LIGHTING:
            if spec.lighting_style:
                light_image, _ = self._assembler.load_field_image(
                    "lighting_style", spec.lighting_style, size, resampling=resampling
                )
                return self._scale_layer_alpha(light_image, 0.4)
            return Image.new("RGBA", size, (0, 0, 0, 0))

        if layer_id == RenderLayerId.HIGHLIGHTS:
            if spec.lighting_style:
                light_image, _ = self._assembler.load_field_image(
                    "lighting_style", spec.lighting_style, size, resampling=resampling
                )
                return self._scale_layer_alpha(light_image, 0.2)
            return Image.new("RGBA", size, (0, 0, 0, 0))

        raise RenderingError(f"Unknown layer: {layer_id}")

    @staticmethod
    def _scale_layer_alpha(image: Image.Image, strength: float) -> Image.Image:
        import numpy as np

        rgba = image.convert("RGBA")
        data = np.array(rgba, dtype=np.float32)
        data[..., 3] *= strength
        return Image.fromarray(data.astype(np.uint8), mode="RGBA")

    def _estimate_memory_mb(self) -> float:
        total_bytes = sum(img.width * img.height * 4 for img in self._cache._layers.values())
        return total_bytes / (1024.0 * 1024.0)
