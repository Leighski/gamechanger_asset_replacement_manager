#!/usr/bin/env python3
"""Benchmark the Live Renderer — Coventry City example."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from models.design_specification import DesignSpecification, OutputProfile
from models.project import KitType
from models.renderer import RendererSettings, RenderQuality
from services.catalogue_manager_service import CatalogueManagerService
from services.rendering.engine import RenderingEngine


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


def main() -> None:
    catalogue = CatalogueManagerService()
    catalogue.load()
    engine = RenderingEngine(catalogue)
    spec = coventry_spec()
    docs = ROOT / "docs" / "examples"
    docs.mkdir(parents=True, exist_ok=True)

    results: dict[str, object] = {}
    for quality in RenderQuality:
        settings = RendererSettings(quality=quality)
        engine.cache.invalidate()
        engine.render(spec, settings)
        start = time.perf_counter()
        warm = engine.render(spec, settings)
        elapsed = (time.perf_counter() - start) * 1000.0
        out_path = docs / f"coventry_render_{quality.value.lower()}.png"
        out_path.write_bytes(warm.image_png)
        results[quality.value] = {
            "warm_ms": round(elapsed, 2),
            "cache_hits": warm.stats.cache_hits,
            "cache_misses": warm.stats.cache_misses,
            "memory_mb": warm.stats.memory_usage_mb,
            "output": str(out_path.name),
        }
        print(f"{quality.value}: {elapsed:.1f} ms (hits={warm.stats.cache_hits}, misses={warm.stats.cache_misses})")

    partial = spec.model_copy(deep=True)
    partial.collar_colour = "#000000"
    start = time.perf_counter()
    partial_result = engine.render(partial, RendererSettings(quality=RenderQuality.STANDARD))
    partial_ms = (time.perf_counter() - start) * 1000.0
    results["partial_collar_change_ms"] = round(partial_ms, 2)
    results["partial_cache_hits"] = partial_result.stats.cache_hits
    print(f"Partial (collar colour): {partial_ms:.1f} ms, hits={partial_result.stats.cache_hits}")

    benchmark_path = docs / "GJS009_BENCHMARK.json"
    benchmark_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"Wrote {benchmark_path}")


if __name__ == "__main__":
    main()
