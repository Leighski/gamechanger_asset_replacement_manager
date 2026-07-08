#!/usr/bin/env python3
"""Zoomed visual evidence for the base_template.psd asset upgrade.

Produces (a) a High-tier render crop comparison (legacy vs regenerated assets)
and (b) an asset-level edge-detail comparison. Offline; no renderer changes.
"""

from __future__ import annotations

import io
import shutil
import sys
from pathlib import Path

from PIL import Image

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from core.paths import GARMENT_TEMPLATES_ASSETS_DIR
from models.renderer import RenderQuality, RendererSettings
from scripts.reference_calibration_specs import reference_spec_for_key

TEMPLATE_ID = "GARMENT_ENGLISH_FOOTBALL_BASE_0001"
OUT = _REPO_ROOT / "output" / "renders" / "milestones" / "milestone_base_template"
LEGACY_ASSETS = OUT / "backup_legacy" / f"assets_{TEMPLATE_ID}"
NEW_ASSETS = OUT / "backup_new" / f"assets_{TEMPLATE_ID}"
LIVE_ASSETS = GARMENT_TEMPLATES_ASSETS_DIR / TEMPLATE_ID


def _swap(source: Path) -> None:
    if LIVE_ASSETS.exists():
        shutil.rmtree(LIVE_ASSETS)
    shutil.copytree(source, LIVE_ASSETS)


def _render_high(key: str) -> Image.Image:
    from services.template_definition_service import TemplateDefinitionService
    from services.garment_renderer import GarmentRenderer

    svc = TemplateDefinitionService()
    svc.load()
    renderer = GarmentRenderer(svc)
    renderer.load(TEMPLATE_ID)
    spec = reference_spec_for_key(key)
    result = renderer.render_to_result(spec, RendererSettings(quality=RenderQuality.HIGH))
    return Image.open(io.BytesIO(result.image_png)).convert("RGBA")


def _zoom_crop(image: Image.Image, box: tuple[int, int, int, int], factor: int = 3) -> Image.Image:
    crop = image.crop(box)
    return crop.resize((crop.width * factor, crop.height * factor), Image.Resampling.NEAREST)


def _label(im: Image.Image, text: str) -> Image.Image:
    from PIL import ImageDraw

    canvas = Image.new("RGBA", (im.width, im.height + 22), (28, 28, 32, 255))
    canvas.alpha_composite(im.convert("RGBA"), (0, 22))
    d = ImageDraw.Draw(canvas)
    d.text((4, 5), text, fill=(220, 220, 220))
    return canvas


def _stack(images: list[Image.Image], gap: int = 10) -> Image.Image:
    h = max(i.height for i in images)
    total = sum(i.width for i in images) + gap * (len(images) + 1)
    strip = Image.new("RGBA", (total, h + gap * 2), (28, 28, 32, 255))
    x = gap
    for im in images:
        strip.alpha_composite(im, (x, gap))
        x += im.width + gap
    return strip


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    # Render crops at High tier: collar (top-centre) and chest/badge region.
    boxes = {
        "collar": (250, 40, 360, 150),
        "chest": (210, 180, 400, 380),
    }
    try:
        _swap(LEGACY_ASSETS)
        before = _render_high("base")
        _swap(NEW_ASSETS)
        after = _render_high("base")
    finally:
        _swap(NEW_ASSETS)

    for name, box in boxes.items():
        b = _label(_zoom_crop(before, box), "legacy 1200-sourced")
        a = _label(_zoom_crop(after, box), "canonical master")
        _stack([b, a]).convert("RGB").save(OUT / f"render_zoom_{name}.png")

    # Asset-level edge comparison: shirt panel mask, collar effect.
    pairs = [
        ("masks/shirt_base_editable_parts_shirt.png", (0.30, 0.30, 0.55, 0.55)),
        ("raster/v_neck_collar_1_effects_details.png", (0.20, 0.20, 0.80, 0.80)),
    ]
    for rel, frac in pairs:
        legacy_p = LEGACY_ASSETS / rel
        new_p = NEW_ASSETS / rel
        if not legacy_p.is_file() or not new_p.is_file():
            continue
        lim = Image.open(legacy_p).convert("RGBA")
        nim = Image.open(new_p).convert("RGBA")
        # Crop same relative region, scale both to a common display height.
        def region(im: Image.Image) -> Image.Image:
            w, h = im.size
            box = (int(w * frac[0]), int(h * frac[1]), int(w * frac[2]), int(h * frac[3]))
            c = im.crop(box)
            disp_h = 360
            return c.resize((max(1, round(c.width * disp_h / c.height)), disp_h), Image.Resampling.NEAREST)

        b = _label(region(lim), f"legacy {lim.size[0]}x{lim.size[1]}")
        a = _label(region(nim), f"master {nim.size[0]}x{nim.size[1]}")
        safe = rel.replace("/", "_").replace(".png", "")
        _stack([b, a]).convert("RGB").save(OUT / f"asset_zoom_{safe}.png")

    print(f"Zoom evidence written to {OUT}")
    for p in sorted(OUT.glob("render_zoom_*.png")) + sorted(OUT.glob("asset_zoom_*.png")):
        print(f"  {p.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
