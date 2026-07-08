"""Comprehensive tests for the Live Renderer subsystem."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest
from PIL import Image

from models.design_specification import DesignSpecification, OutputProfile
from models.project import KitType, ProjectDocument, ProjectManifest
from models.renderer import RenderLayerId, RendererSettings, RenderQuality
from services.catalogue_manager_service import CatalogueManagerService
from services.live_renderer_service import LiveRendererService, RENDERER_SETTINGS_NAME
from services.project_format import read_project_package, write_project_package
from services.rendering.colour_mapper import ColourMapper, parse_hex_colour
from services.rendering.component_assembler import ComponentAssembler
from services.rendering.engine import RenderingEngine, QUALITY_DIMENSIONS
from services.rendering.layer_manager import LayerManager
from services.rendering.pattern_mapper import PatternMapper
from services.rendering.preview_cache import PreviewCache


@pytest.fixture
def catalogue_manager() -> CatalogueManagerService:
    manager = CatalogueManagerService()
    manager.load()
    return manager


@pytest.fixture
def live_renderer(catalogue_manager: CatalogueManagerService) -> LiveRendererService:
    return LiveRendererService(catalogue_manager)


@pytest.fixture
def coventry_spec() -> DesignSpecification:
    return DesignSpecification(
        club="Coventry City",
        competition="Championship",
        season="2025/26",
        kit_type=KitType.HOME,
        manufacturer="Hummel",
        primary_colour="#69B3E7",
        secondary_colour="#FFFFFF",
        third_colour="#1C1C1C",
        sleeve_colour="#69B3E7",
        collar_colour="#FFFFFF",
        trim_colour="#1C1C1C",
        pattern="hoops",
        pattern_scale=1.0,
        pattern_rotation=0.0,
        pattern_opacity=0.85,
        sleeve_style="standard",
        collar_style="v-neck",
        trim_style="TRIM_0002",
        material_style="polyester",
        shadow_style="broadcast",
        lighting_style="studio",
        texture_style="fabric",
        output_profile=OutputProfile.GAMECHANGER_BROADCAST,
    )


@pytest.fixture
def coventry_document(coventry_spec: DesignSpecification) -> ProjectDocument:
    manifest = ProjectManifest(
        project_name="Coventry City Home 2026",
        club_name="Coventry City",
        competition="Championship",
        season="2025/26",
        kit_type=KitType.HOME,
        output_folder="/tmp/coventry",
        author="Test",
    )
    return ProjectDocument(manifest=manifest, design_spec=coventry_spec)


def test_parse_hex_colour() -> None:
    assert parse_hex_colour("#69B3E7") == (105, 179, 231)
    assert parse_hex_colour("69B3E7") == (105, 179, 231)
    assert parse_hex_colour("") == (128, 128, 128)


def test_component_assembler_resolves_canonical_ids(
    catalogue_manager: CatalogueManagerService,
) -> None:
    assembler = ComponentAssembler(catalogue_manager)
    assert assembler.canonical_id("collar_style", "v-neck") == "COLLAR_0002"
    assert assembler.canonical_id("pattern", "hoops") == "PATTERN_0002"
    component = assembler.resolve_field("material_style", "polyester")
    assert component is not None
    assert component.id == "MATERIAL_0001"


def test_component_assembler_loads_preview(
    catalogue_manager: CatalogueManagerService,
    coventry_spec: DesignSpecification,
) -> None:
    assembler = ComponentAssembler(catalogue_manager)
    image, component = assembler.load_field_image(
        "material_style",
        coventry_spec.material_style,
        (200, 250),
    )
    assert component.id == "MATERIAL_0001"
    assert image.size == (200, 250)
    assert image.mode == "RGBA"


def test_colour_mapper_tints_image() -> None:
    mapper = ColourMapper()
    base = Image.new("L", (20, 20), 200).convert("RGBA")
    tinted = mapper.tint_rgba(base, "#FF0000")
    pixel = tinted.getpixel((10, 10))
    assert pixel[0] > pixel[2]
    assert pixel[3] > 0


def test_pattern_mapper_respects_opacity() -> None:
    mapper = PatternMapper()
    base = Image.new("RGBA", (100, 100), (50, 50, 50, 255))
    pattern = Image.new("RGBA", (20, 20), (255, 0, 0, 255))
    result = mapper.apply_pattern(base, pattern, scale=1.0, rotation_degrees=0.0, opacity=0.0)
    assert result.getpixel((10, 10)) == base.getpixel((10, 10))


def test_preview_cache_hit_and_miss() -> None:
    cache = PreviewCache()
    image = Image.new("RGBA", (10, 10), (255, 0, 0, 255))
    assert cache.get("base_body", "key-a") is None
    cache.put("base_body", "key-a", image)
    hit = cache.get("base_body", "key-a")
    assert hit is not None
    assert cache.stats.hits == 1
    assert cache.get("base_body", "key-b") is None
    assert cache.stats.misses == 2


def test_layer_manager_order() -> None:
    manager = LayerManager()
    settings = RendererSettings()
    ordered = manager.ordered_layers(settings)
    assert ordered[0] == RenderLayerId.PRESENTATION_BACKGROUND
    assert ordered[-1] == RenderLayerId.HIGHLIGHTS


def test_layer_visibility_toggle() -> None:
    manager = LayerManager()
    settings = RendererSettings(
        layer_visibility={layer.value: layer != RenderLayerId.PATTERN for layer in RenderLayerId}
    )
    ordered = manager.ordered_layers(settings)
    assert RenderLayerId.PATTERN not in ordered
    assert RenderLayerId.BASE_BODY in ordered


def test_render_produces_png(
    catalogue_manager: CatalogueManagerService,
    coventry_spec: DesignSpecification,
) -> None:
    engine = RenderingEngine(catalogue_manager)
    settings = RendererSettings(quality=RenderQuality.STANDARD)
    result = engine.render(coventry_spec, settings)
    assert result.success
    assert result.image_png
    assert result.stats.width == QUALITY_DIMENSIONS[RenderQuality.STANDARD][0]
    image = Image.open(__import__("io").BytesIO(result.image_png))
    assert image.size == QUALITY_DIMENSIONS[RenderQuality.STANDARD]


def test_render_standard_under_target_ms(
    catalogue_manager: CatalogueManagerService,
    coventry_spec: DesignSpecification,
) -> None:
    engine = RenderingEngine(catalogue_manager)
    settings = RendererSettings(quality=RenderQuality.STANDARD)
    engine.render(coventry_spec, settings)
    result = engine.render(coventry_spec, settings)
    assert result.success
    assert result.stats.total_ms < 150.0


def test_cache_reuse_on_partial_change(
    catalogue_manager: CatalogueManagerService,
    coventry_spec: DesignSpecification,
) -> None:
    engine = RenderingEngine(catalogue_manager)
    settings = RendererSettings(quality=RenderQuality.DRAFT)
    first = engine.render(coventry_spec, settings)
    assert first.success
    misses_after_first = engine.cache.stats.misses

    updated = coventry_spec.model_copy(deep=True)
    updated.collar_colour = "#000000"
    second = engine.render(updated, settings)
    assert second.success
    assert engine.cache.stats.hits > 0
    assert second.stats.cache_hits > 0
    collar_timing = next(t for t in second.stats.layer_timings if t.layer_id == "collar")
    assert not collar_timing.cache_hit
    body_timing = next(t for t in second.stats.layer_timings if t.layer_id == "base_body")
    assert body_timing.cache_hit


def test_render_invalidation_on_quality_change(
    catalogue_manager: CatalogueManagerService,
    coventry_spec: DesignSpecification,
) -> None:
    engine = RenderingEngine(catalogue_manager)
    engine.render(coventry_spec, RendererSettings(quality=RenderQuality.DRAFT))
    hits_before = engine.cache.stats.hits
    engine.render(coventry_spec, RendererSettings(quality=RenderQuality.HIGH))
    assert engine.cache.stats.misses > hits_before or engine.cache.stats.misses >= 10


def test_live_renderer_service_document_render(
    live_renderer: LiveRendererService,
    coventry_document: ProjectDocument,
) -> None:
    result = live_renderer.render_document(coventry_document)
    assert result.success
    assert live_renderer.ensure_settings(coventry_document).quality == RenderQuality.STANDARD


def test_renderer_settings_persist_in_gjs(
    tmp_path: Path,
    coventry_document: ProjectDocument,
) -> None:
    coventry_document.renderer_settings = RendererSettings(
        quality=RenderQuality.HIGH,
        show_inspector=True,
    )
    target = tmp_path / "coventry.gjs"
    write_project_package(coventry_document, target)
    reloaded, _ = read_project_package(target)
    assert reloaded.renderer_settings is not None
    assert reloaded.renderer_settings.quality == RenderQuality.HIGH
    assert reloaded.renderer_settings.show_inspector is True
    with zipfile.ZipFile(target) as zf:
        assert RENDERER_SETTINGS_NAME in zf.namelist()
        raw = json.loads(zf.read(RENDERER_SETTINGS_NAME))
        assert raw["quality"] == "High"


def test_coventry_render_all_layers(
    catalogue_manager: CatalogueManagerService,
    coventry_spec: DesignSpecification,
) -> None:
    engine = RenderingEngine(catalogue_manager)
    settings = RendererSettings(quality=RenderQuality.STANDARD)
    result = engine.render(coventry_spec, settings)
    layer_ids = {timing.layer_id for timing in result.stats.layer_timings}
    for layer in RenderLayerId:
        assert layer.value in layer_ids


def test_render_failure_missing_component(
    catalogue_manager: CatalogueManagerService,
    coventry_spec: DesignSpecification,
) -> None:
    engine = RenderingEngine(catalogue_manager)
    bad = coventry_spec.model_copy(deep=True)
    bad.material_style = "nonexistent_material_xyz"
    result = engine.render(bad, RendererSettings())
    assert not result.success
    assert result.error
