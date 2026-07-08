#!/usr/bin/env python3
"""Benchmark batch render queue throughput — GJS-012."""

from __future__ import annotations

import json
import statistics
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from models.design_specification import DesignSpecification, OutputProfile
from models.project import KitType, ProjectDocument, ProjectManifest
from models.psd_template import TemplateProjectSettings
from services.catalogue_manager_service import CatalogueManagerService
from services.project_format import write_project_package
from services.project_history_service import ProjectHistoryService
from services.psd_renderer_service import PSDRendererService
from services.template_manager_service import TemplateManagerService


def make_spec(name: str) -> DesignSpecification:
    return DesignSpecification(
        club=name,
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
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    tmp = Path(tempfile.mkdtemp())
    templates = TemplateManagerService()
    catalogue = CatalogueManagerService()
    catalogue.load()
    renderer = PSDRendererService(templates, catalogue, ProjectHistoryService())

    paths: list[Path] = []
    for index in range(count):
        manifest = ProjectManifest(
            project_name=f"Bench_{index + 1}",
            club_name=f"Club {index + 1}",
            competition="Championship",
            season="2025/26",
            kit_type=KitType.HOME,
            output_folder=str(tmp / f"out_{index}"),
            author="Benchmark",
        )
        doc = ProjectDocument(
            manifest=manifest,
            design_spec=make_spec(f"Club {index + 1}"),
            template_settings=TemplateProjectSettings(active_template_id="TEMPLATE_BROADCAST_0001"),
        )
        path = tmp / f"bench_{index + 1}.gjs"
        write_project_package(doc, path)
        doc.file_path = str(path)
        paths.append(path)
        renderer.enqueue(doc)

    started = time.perf_counter()
    results = renderer.process_batch()
    total_ms = (time.perf_counter() - started) * 1000.0
    successes = sum(1 for r in results if r.success)
    timings = [r.log.total_ms for r in results if r.success and r.log.total_ms]

    benchmark = {
        "job_count": count,
        "successes": successes,
        "failures": count - successes,
        "total_batch_ms": round(total_ms, 2),
        "mean_render_ms": round(statistics.mean(timings), 2) if timings else 0,
        "median_render_ms": round(statistics.median(timings), 2) if timings else 0,
        "target_100_jerseys_estimated_minutes": round((statistics.mean(timings) * 100) / 60000, 2) if timings else 0,
    }

    out = ROOT / "docs" / "examples" / "GJS012_BENCHMARK.json"
    out.write_text(json.dumps(benchmark, indent=2), encoding="utf-8")
    print(json.dumps(benchmark, indent=2))
    return 0 if successes == count else 1


if __name__ == "__main__":
    raise SystemExit(main())
