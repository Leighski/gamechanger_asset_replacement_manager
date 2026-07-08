#!/usr/bin/env python3
"""Benchmark the Production PSD Renderer — Coventry City Home spec."""

from __future__ import annotations

import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from models.design_specification import DesignSpecification, OutputProfile
from models.project import KitType
from services.catalogue_manager_service import CatalogueManagerService
from services.psd_rendering.psd_render_service import PSDRenderService
from services.template_manager_service import TemplateManagerService


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


def main() -> int:
    out_dir = ROOT / "docs" / "examples"
    out_dir.mkdir(parents=True, exist_ok=True)
    tmp = out_dir / "_benchmark_tmp"
    tmp.mkdir(exist_ok=True)

    templates = TemplateManagerService()
    catalogue = CatalogueManagerService()
    catalogue.load()
    renderer = PSDRenderService(templates.manager, catalogue)
    mappings = templates.manager.publish_mappings("TEMPLATE_BROADCAST_0001")
    if mappings is None:
        print("No published mappings", file=sys.stderr)
        return 1

    spec = coventry_spec()
    runs: list[dict] = []
    for index in range(3):
        started = time.perf_counter()
        result = renderer.render(
            spec,
            mappings,
            project_name=f"Coventry_Benchmark_{index + 1}",
            output_folder=str(tmp),
        )
        elapsed = (time.perf_counter() - started) * 1000.0
        if not result.success:
            print(f"Render failed: {result.error}", file=sys.stderr)
            return 1
        stage_timings = {stage.stage.value: stage.duration_ms for stage in result.log.stages}
        runs.append({"total_ms": round(elapsed, 2), "stages": stage_timings})

    totals = [run["total_ms"] for run in runs]
    benchmark = {
        "template_id": mappings.template_id,
        "runs": runs,
        "total_ms_mean": round(statistics.mean(totals), 2),
        "total_ms_median": round(statistics.median(totals), 2),
        "total_ms_min": round(min(totals), 2),
        "total_ms_max": round(max(totals), 2),
        "stage_ms_mean": {
            stage: round(statistics.mean(run["stages"].get(stage, 0.0) for run in runs), 2)
            for stage in runs[0]["stages"]
        },
    }

    target = out_dir / "GJS011_BENCHMARK.json"
    target.write_text(json.dumps(benchmark, indent=2), encoding="utf-8")
    print(json.dumps(benchmark, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
