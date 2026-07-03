#!/usr/bin/env python3
"""Before/after validation for the canonical base_template.psd asset upgrade.

Renders identical design specs with the legacy (1200-sourced) assets and the
regenerated production-resolution assets, scores both with the Production
Fidelity tools, and writes side-by-side comparisons.

Offline validation tool — does not modify the renderer.
"""

from __future__ import annotations

import io
import json
import shutil
import sys
from datetime import datetime, timezone
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
REFERENCES = ("base", "coventry")


def _swap_assets(source: Path) -> None:
    if LIVE_ASSETS.exists():
        shutil.rmtree(LIVE_ASSETS)
    shutil.copytree(source, LIVE_ASSETS)


def _render(reference_key: str) -> Image.Image:
    # Fresh services so on-disk assets are re-read and caches are cold.
    from services.template_definition_service import TemplateDefinitionService
    from services.garment_renderer import GarmentRenderer

    svc = TemplateDefinitionService()
    svc.load()
    renderer = GarmentRenderer(svc)
    renderer.load(TEMPLATE_ID)
    spec = reference_spec_for_key(reference_key)
    result = renderer.render_to_result(spec, RendererSettings(quality=RenderQuality.STANDARD))
    if not result.success or not result.image_png:
        raise RuntimeError(f"Render failed for {reference_key}: {result.error}")
    return Image.open(io.BytesIO(result.image_png)).convert("RGBA")


def _score(reference_key: str, image: Image.Image, out_dir: Path) -> dict:
    from services.production_validation_service import ProductionValidationService

    validation = ProductionValidationService()
    reference = next(r for r in validation.list_references() if r.key == reference_key)
    out_dir.mkdir(parents=True, exist_ok=True)
    report = validation.compute_fidelity_with_artifacts(image, reference, output_dir=out_dir)
    cat = {c.name: round(c.score, 2) for c in report.categories}
    comp = {c.name: round(c.score, 2) for c in report.components}
    return {
        "overall": round(report.overall_score, 2),
        "categories": cat,
        "highlight_rolloff": comp.get("Lighting \u00b7 Highlight Roll-off"),
        "colour_distribution": comp.get("Colour Accuracy \u00b7 Colour Distribution"),
    }


def _side_by_side(reference_key: str, before: Image.Image, after: Image.Image) -> None:
    from services.production_validation_service import ProductionValidationService

    validation = ProductionValidationService()
    reference = next(r for r in validation.list_references() if r.key == reference_key)
    ref_img = validation.load_reference_image(reference).convert("RGBA")

    target_h = 700
    def fit(im: Image.Image) -> Image.Image:
        w, h = im.size
        nw = max(1, round(w * target_h / h))
        canvas = Image.new("RGBA", (nw, target_h), (30, 30, 34, 255))
        r = im.resize((nw, target_h), Image.Resampling.LANCZOS)
        canvas.alpha_composite(r)
        return canvas

    panels = [fit(ref_img), fit(before), fit(after)]
    gap = 12
    total_w = sum(p.width for p in panels) + gap * (len(panels) + 1)
    strip = Image.new("RGBA", (total_w, target_h + 24), (30, 30, 34, 255))
    x = gap
    for p in panels:
        strip.alpha_composite(p, (x, 20))
        x += p.width + gap
    strip.convert("RGB").save(OUT / f"{reference_key}_reference_before_after.png")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    if not LEGACY_ASSETS.exists():
        print(f"Legacy asset backup missing: {LEGACY_ASSETS}", file=sys.stderr)
        return 1

    # Snapshot the current (regenerated) live assets as the "new" set.
    if NEW_ASSETS.exists():
        shutil.rmtree(NEW_ASSETS)
    NEW_ASSETS.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(LIVE_ASSETS, NEW_ASSETS)

    summary: dict = {
        "milestone": "Canonical Base Template Upgrade (base_template.psd)",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "references": {},
    }

    try:
        results: dict[str, dict[str, Image.Image]] = {}
        for mode, source in (("before", LEGACY_ASSETS), ("after", NEW_ASSETS)):
            _swap_assets(source)
            for key in REFERENCES:
                image = _render(key)
                image.save(OUT / f"{key}_{mode}.png")
                score = _score(key, image, OUT / f"artifacts_{mode}")
                summary["references"].setdefault(key, {})[mode] = score
                results.setdefault(key, {})[mode] = image
                print(f"[{mode}] {key}: overall {score['overall']}  categories {score['categories']}")
    finally:
        _swap_assets(NEW_ASSETS)  # leave the regenerated assets live

    for key in REFERENCES:
        _side_by_side(key, results[key]["before"], results[key]["after"])
        b = summary["references"][key]["before"]["overall"]
        a = summary["references"][key]["after"]["overall"]
        summary["references"][key]["delta_overall"] = round(a - b, 2)

    (OUT / "before_after_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print("\nSummary:")
    for key in REFERENCES:
        r = summary["references"][key]
        print(f"  {key}: {r['before']['overall']} -> {r['after']['overall']}  (Δ {r['delta_overall']})")
    print(f"Saved: {OUT / 'before_after_summary.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
