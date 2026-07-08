#!/usr/bin/env python3
"""Export Live Preview panel screenshots for GJS-009 deliverables."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication

from models.design_specification import DesignSpecification, OutputProfile
from models.project import KitType, ProjectDocument, ProjectManifest
from models.renderer import RendererSettings
from services.catalogue_manager_service import CatalogueManagerService
from services.live_renderer_service import LiveRendererService
from ui.widgets.preview_panel import PreviewPanel
from ui.widgets.renderer_inspector import RendererInspector


def coventry_document() -> ProjectDocument:
    spec = DesignSpecification(
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
    manifest = ProjectManifest(
        project_name="Coventry City Home 2026",
        club_name="Coventry City",
        competition="Championship",
        season="2025/26",
        kit_type=KitType.HOME,
        output_folder=str(ROOT / "docs" / "examples"),
        author="Gamechanger",
    )
    doc = ProjectDocument(manifest=manifest, design_spec=spec)
    doc.renderer_settings = RendererSettings(show_inspector=True)
    return doc


def main() -> None:
    app = QApplication(sys.argv)
    out_dir = ROOT / "docs" / "examples"
    out_dir.mkdir(parents=True, exist_ok=True)

    catalogue = CatalogueManagerService()
    catalogue.load()
    renderer = LiveRendererService(catalogue)
    document = coventry_document()

    panel = PreviewPanel()
    panel.resize(360, 720)
    panel.set_renderer_service(renderer)
    panel.set_project(document)
    panel.grab().save(str(out_dir / "GJS009_SCREENSHOT_LIVE_PREVIEW.png"))

    inspector = RendererInspector()
    inspector.resize(320, 280)
    result = renderer.render_document(document)
    from models.renderer import RenderLayerId

    active = [layer for layer in RenderLayerId if document.renderer_settings.is_layer_visible(layer)]
    inspector.update_stats(result.stats, active)
    inspector.grab().save(str(out_dir / "GJS009_SCREENSHOT_RENDERER_INSPECTOR.png"))

    cache_stats = {
        "render_ms": result.stats.total_ms,
        "cache_hits": result.stats.cache_hits,
        "cache_misses": result.stats.cache_misses,
        "memory_mb": result.stats.memory_usage_mb,
        "layer_timings": [t.model_dump() for t in result.stats.layer_timings],
    }
    (out_dir / "GJS009_CACHE_STATS.json").write_text(json.dumps(cache_stats, indent=2), encoding="utf-8")
    print(f"Screenshots written to {out_dir}")


if __name__ == "__main__":
    main()
