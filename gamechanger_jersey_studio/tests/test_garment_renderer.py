"""Tests for the photorealistic garment template renderer."""

from __future__ import annotations

import builtins
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
from PIL import Image

from models.design_specification import DesignSpecification, OutputProfile
from models.project import KitType
from models.renderer import RenderLayerId, RendererSettings, RenderQuality
from services.garment_renderer import DEFAULT_GARMENT_TEMPLATE_ID, GarmentRenderer
from services.garment_renderer.garment_renderer import QUALITY_DIMENSIONS
from services.template_definition_service import TemplateDefinitionService

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEMO_SCRIPT = PROJECT_ROOT / "scripts" / "render_demo_preview.py"


@pytest.fixture
def garment_renderer() -> GarmentRenderer:
    renderer = GarmentRenderer()
    renderer.load(DEFAULT_GARMENT_TEMPLATE_ID)
    return renderer


@pytest.fixture
def demo_spec() -> DesignSpecification:
    return DesignSpecification(
        club="Test FC",
        competition="Test",
        season="2025/26",
        kit_type=KitType.HOME,
        primary_colour="#CC0000",
        secondary_colour="#000000",
        third_colour="#FFFFFF",
        sleeve_colour="#000000",
        collar_colour="#FFFFFF",
        trim_colour="#000000",
        pattern="diagonal_fade",
        pattern_scale=1.0,
        pattern_opacity=0.8,
        material_style="polyester",
        output_profile=OutputProfile.GAMECHANGER_BROADCAST,
    )


def test_garment_renderer_produces_image(
    garment_renderer: GarmentRenderer,
    demo_spec: DesignSpecification,
) -> None:
    settings = RendererSettings(quality=RenderQuality.STANDARD)
    result = garment_renderer.render_to_result(demo_spec, settings)
    assert result.success, result.error
    assert result.image_png
    image = Image.open(__import__("io").BytesIO(result.image_png)).convert("RGBA")
    assert image.size == QUALITY_DIMENSIONS[RenderQuality.STANDARD]
    alpha = np.array(image.split()[-1])
    assert alpha.max() > 0
    assert (alpha > 0).sum() > 500
    assert image.getpixel((0, 0))[3] == 0
    assert image.getpixel((image.width - 1, image.height - 1))[3] == 0


def test_render_output_is_transparent_not_baked_background(
    garment_renderer: GarmentRenderer,
    demo_spec: DesignSpecification,
) -> None:
    result = garment_renderer.render_to_result(demo_spec, RendererSettings(quality=RenderQuality.STANDARD))
    assert result.success, result.error
    image = Image.open(__import__("io").BytesIO(result.image_png)).convert("RGBA")
    data = np.array(image)
    alpha = data[..., 3]
    edge = np.concatenate(
        [
            alpha[0, :],
            alpha[-1, :],
            alpha[:, 0],
            alpha[:, -1],
        ]
    )
    assert edge.max() == 0


def test_no_placeholder_circle_artifacts(
    garment_renderer: GarmentRenderer,
    demo_spec: DesignSpecification,
) -> None:
    """Chest region must not contain large saturated red elliptical placeholder badges."""
    settings = RendererSettings(quality=RenderQuality.STANDARD)
    result = garment_renderer.render_to_result(demo_spec, settings)
    assert result.success, result.error
    image = Image.open(__import__("io").BytesIO(result.image_png)).convert("RGBA")
    data = np.array(image)
    width, height = image.size

    # Chest area where placeholder badges were previously drawn
    x0, x1 = int(width * 0.30), int(width * 0.70)
    y0, y1 = int(height * 0.18), int(height * 0.58)
    chest = data[y0:y1, x0:x1]

    alpha = chest[..., 3]
    opaque = alpha > 128
    if not opaque.any():
        return

    rgb = chest[..., :3].astype(np.float32)
    red_dom = (rgb[..., 0] > 180) & (rgb[..., 1] < 80) & (rgb[..., 2] < 80)
    saturated_red = red_dom & opaque
    red_fraction = saturated_red.sum() / max(opaque.sum(), 1)
    assert red_fraction < 0.08, (
        f"Detected placeholder-like saturated red regions in chest area ({red_fraction:.1%})"
    )


def test_panel_colour_change_invalidates_only_colour_layer(
    garment_renderer: GarmentRenderer,
    demo_spec: DesignSpecification,
) -> None:
    settings = RendererSettings(quality=RenderQuality.DRAFT)
    garment_renderer.render_to_result(demo_spec, settings)
    misses_before = garment_renderer.cache.stats.misses

    updated = demo_spec.model_copy(deep=True)
    updated.collar_colour = "#0000FF"
    result = garment_renderer.render_to_result(updated, settings)
    assert result.success

    collar_timing = next(t for t in result.stats.layer_timings if t.layer_id == RenderLayerId.COLLAR.value)
    body_timing = next(t for t in result.stats.layer_timings if t.layer_id == RenderLayerId.BASE_BODY.value)
    assert not collar_timing.cache_hit
    assert body_timing.cache_hit
    assert garment_renderer.cache.stats.misses > misses_before


def test_no_psd_access_at_runtime(
    garment_renderer: GarmentRenderer,
    demo_spec: DesignSpecification,
) -> None:
    original_open = builtins.open

    def guarded_open(file, *args, **kwargs):
        path = str(file)
        if path.lower().endswith(".psd"):
            raise AssertionError(f"PSD opened at runtime: {path}")
        return original_open(file, *args, **kwargs)

    with patch("builtins.open", side_effect=guarded_open):
        result = garment_renderer.render_to_result(demo_spec, RendererSettings(quality=RenderQuality.DRAFT))
    assert result.success


def test_template_definition_service_only(
    demo_spec: DesignSpecification,
) -> None:
    service = TemplateDefinitionService()
    service.load()
    definition = service.get_definition(DEFAULT_GARMENT_TEMPLATE_ID)
    assert definition is not None
    issues = service.validate_definition(DEFAULT_GARMENT_TEMPLATE_ID)
    assert not issues, issues

    renderer = GarmentRenderer(service)
    renderer.load()
    result = renderer.render_to_result(demo_spec, RendererSettings(quality=RenderQuality.DRAFT))
    assert result.success


def test_dynamic_lighting_layers_are_composited(
    garment_renderer: GarmentRenderer,
    demo_spec: DesignSpecification,
) -> None:
    """Production Dynamic lighting assets must change the final composite."""
    service = garment_renderer._definitions  # noqa: SLF001
    definition = service.get_definition(DEFAULT_GARMENT_TEMPLATE_ID)
    assert definition is not None
    assert len(definition.dynamic_lighting_layers) >= 3

    settings = RendererSettings(quality=RenderQuality.STANDARD)
    with_layers = garment_renderer.render_to_result(demo_spec, settings)
    assert with_layers.success, with_layers.error
    with_image = Image.open(__import__("io").BytesIO(with_layers.image_png)).convert("RGBA")

    saved = list(definition.dynamic_lighting_layers)
    definition.dynamic_lighting_layers = []
    without_layers = garment_renderer.render_to_result(demo_spec, settings)
    definition.dynamic_lighting_layers = saved
    assert without_layers.success, without_layers.error
    without_image = Image.open(__import__("io").BytesIO(without_layers.image_png)).convert("RGBA")

    with_rgb = np.array(with_image)[..., :3].astype(np.float32)
    without_rgb = np.array(without_image)[..., :3].astype(np.float32)
    alpha = np.array(with_image)[..., 3] > 0
    delta = np.abs(with_rgb - without_rgb).mean(axis=-1)
    assert float(delta[alpha].mean()) > 1.5


def test_demo_script_produces_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from scripts import render_demo_preview as demo_module

    monkeypatch.setattr(demo_module, "OUTPUT_DIR", tmp_path)
    assert demo_module.main() == 0
    output = tmp_path / "demo_jersey_preview.png"
    assert output.is_file()
    image = Image.open(output)
    assert image.width > 0 and image.height > 0
