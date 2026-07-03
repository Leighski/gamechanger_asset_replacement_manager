#!/usr/bin/env python3
"""Regenerate garment template assets from the canonical production master PSD.

This is an OFFLINE tool. It rebuilds the companion PNG assets referenced by an
existing Template Definition using ``base_template.psd`` — the full-resolution
(8190x8190) production master — as the single authoritative source.

Design goals (see docs/CANONICAL_BASE_TEMPLATE_UPGRADE.md):
  * Structural parity — the Template Definition keeps the same modules, panels,
    effect layers, stitches, dynamic-lighting layers and SO anchors it uses
    today. Logical coordinates (1200-space bounds) are preserved unchanged, so
    the runtime renderer operates exactly as it does now.
  * Maximum fidelity — each referenced layer is re-exported from the master at
    production resolution (capped to a memory-safe long edge), preserving soft
    alpha edges, transparency and blend semantics.
  * Precise masks — panel masks are exported from the true alpha channel rather
    than the colour-luminance of the shape fill, improving mask precision.

The runtime renderer never opens a PSD; it consumes only these extracted assets.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from core.paths import (
    GARMENT_TEMPLATES_ASSETS_DIR,
    GARMENT_TEMPLATES_DEFINITIONS_DIR,
)

DEFAULT_MASTER_PSD = Path(
    "/Volumes/04_GRAPHICS/03_JERSEYS/02_ENGLISH_FOOTBALL_JERSEYS/base_template.psd"
)
DEFAULT_TEMPLATE_ID = "GARMENT_ENGLISH_FOOTBALL_BASE_0001"

# Top-level module groups active in the runtime template (variant groups,
# background and embossed-logo groups are toggled off in the master and are not
# part of today's render path).
ACTIVE_TOP_GROUPS = {"shirt base", "short sleeves", "v neck collar 1"}


def _build_path_index(psd: Any) -> dict[str, Any]:
    """Map every layer's full path -> node, restricted to active modules."""
    index: dict[str, Any] = {}

    def walk(node: Any, parent: str) -> None:
        for layer in node:
            name = str(getattr(layer, "name", "") or "")
            path = f"{parent}/{name}" if parent else name
            index[path] = layer
            if bool(getattr(layer, "is_group", lambda: False)()):
                walk(layer, path)

    for layer in psd:
        name = str(getattr(layer, "name", "") or "")
        if name.strip().lower() in ACTIVE_TOP_GROUPS:
            index[name] = layer
            walk(layer, name)
    return index


def _cap(image: Image.Image, max_edge: int) -> Image.Image:
    w, h = image.size
    longest = max(w, h)
    if max_edge <= 0 or longest <= max_edge:
        return image
    ratio = max_edge / float(longest)
    new_size = (max(1, round(w * ratio)), max(1, round(h * ratio)))
    return image.resize(new_size, Image.Resampling.LANCZOS)


def _composite_node(node: Any) -> Image.Image | None:
    """Composite a single layer, forcing visibility for toggled-off layers."""
    original_visible = getattr(node, "visible", True)
    try:
        try:
            node.visible = True
        except Exception:
            pass
        image = node.composite()
    except Exception:
        return None
    finally:
        try:
            node.visible = original_visible
        except Exception:
            pass
    if image is None:
        return None
    return image.convert("RGBA")


def _export_rgba(node: Any, dest: Path, max_edge: int) -> tuple[int, int] | None:
    image = _composite_node(node)
    if image is None:
        return None
    image = _cap(image, max_edge)
    dest.parent.mkdir(parents=True, exist_ok=True)
    image.save(dest, format="PNG")
    return image.size


def _export_alpha_mask(node: Any, dest: Path, max_edge: int) -> tuple[int, int] | None:
    """Export the layer's alpha channel as a grayscale coverage mask."""
    image = _composite_node(node)
    if image is None:
        return None
    alpha = image.split()[-1]  # true coverage, independent of fill colour
    alpha = _cap(alpha, max_edge)
    dest.parent.mkdir(parents=True, exist_ok=True)
    alpha.save(dest, format="PNG")
    return alpha.size


def _asset_path_for(assets_root: Path, template_id: str, relative: str) -> Path:
    return assets_root / template_id / relative


def upgrade(
    *,
    master_psd: Path,
    template_id: str,
    definitions_dir: Path,
    assets_dir: Path,
    max_edge: int,
) -> dict[str, Any]:
    from psd_tools import PSDImage

    definition_path = definitions_dir / f"{template_id}.json"
    if not definition_path.is_file():
        raise FileNotFoundError(f"Template definition not found: {definition_path}")
    definition = json.loads(definition_path.read_text(encoding="utf-8"))

    print(f"Opening master PSD (this is large) — {master_psd}")
    psd = PSDImage.open(master_psd)
    master_size = (int(psd.width), int(psd.height))
    print(f"Master canvas: {master_size[0]}x{master_size[1]}")
    index = _build_path_index(psd)
    print(f"Indexed {len(index)} layers across active modules")

    stats: dict[str, Any] = {
        "master_psd": str(master_psd),
        "master_size": master_size,
        "max_edge": max_edge,
        "exported": [],
        "missing": [],
    }

    mask_lookup = {m["mask_id"]: m for m in definition.get("vector_masks", [])}
    stitch_asset_paths = {
        layer.get("asset", {}).get("path")
        for layer in definition.get("stitch_layers", [])
        if layer.get("asset")
    }

    def record(kind: str, layer_path: str, asset_rel: str, old_size, new_size) -> None:
        stats["exported"].append(
            {
                "kind": kind,
                "layer_path": layer_path,
                "asset": asset_rel,
                "old_size": list(old_size) if old_size else None,
                "new_size": list(new_size) if new_size else None,
            }
        )

    def old_size_of(asset_rel: str):
        p = _asset_path_for(assets_dir, template_id, asset_rel)
        if p.is_file():
            with Image.open(p) as im:
                return im.size
        return None

    # 1) Panel masks -> true alpha coverage (grayscale). Stitch masks stay RGBA.
    for mask in definition.get("vector_masks", []):
        asset = mask.get("asset")
        if not asset:
            continue
        asset_rel = asset["path"]
        layer_path = mask["layer_path"]
        node = index.get(layer_path)
        dest = _asset_path_for(assets_dir, template_id, asset_rel)
        old = old_size_of(asset_rel)
        if node is None:
            stats["missing"].append({"kind": "mask", "layer_path": layer_path})
            continue
        if asset_rel in stitch_asset_paths:
            new = _export_rgba(node, dest, max_edge)  # stitches composited as RGBA
            record("stitch_mask", layer_path, asset_rel, old, new)
        else:
            new = _export_alpha_mask(node, dest, max_edge)
            record("panel_mask", layer_path, asset_rel, old, new)

    # 2) Raster effect stacks (shadows, highlights, lighting) -> composite RGBA.
    for key in ("shadow_layers", "highlight_layers", "fixed_artwork"):
        for layer in definition.get(key, []):
            asset = layer.get("asset")
            if not asset:
                continue
            asset_rel = asset["path"]
            layer_path = layer["layer_path"]
            node = index.get(layer_path)
            dest = _asset_path_for(assets_dir, template_id, asset_rel)
            old = old_size_of(asset_rel)
            if node is None:
                stats["missing"].append({"kind": key, "layer_path": layer_path})
                continue
            new = _export_rgba(node, dest, max_edge)
            record(key, layer_path, asset_rel, old, new)

    # 3) Dynamic lighting Smart Objects -> composite RGBA (Screen @ ~64%).
    for layer in definition.get("dynamic_lighting_layers", []):
        asset = layer.get("asset")
        if not asset:
            continue
        asset_rel = asset["path"]
        layer_path = layer["layer_path"]
        node = index.get(layer_path)
        dest = _asset_path_for(assets_dir, template_id, asset_rel)
        old = old_size_of(asset_rel)
        if node is None:
            stats["missing"].append({"kind": "dynamic_lighting", "layer_path": layer_path})
            continue
        new = _export_rgba(node, dest, max_edge)
        record("dynamic_lighting", layer_path, asset_rel, old, new)

    # 4) Stitch layers whose asset was not already covered via vector_masks.
    for layer in definition.get("stitch_layers", []):
        asset = layer.get("asset")
        if not asset:
            continue
        asset_rel = asset["path"]
        if any(e["asset"] == asset_rel for e in stats["exported"]):
            continue
        layer_path = layer["layer_path"]
        node = index.get(layer_path)
        dest = _asset_path_for(assets_dir, template_id, asset_rel)
        old = old_size_of(asset_rel)
        if node is None:
            stats["missing"].append({"kind": "stitch", "layer_path": layer_path})
            continue
        new = _export_rgba(node, dest, max_edge)
        record("stitch", layer_path, asset_rel, old, new)

    # Update provenance metadata; structure and logical bounds are preserved.
    definition["extraction"] = {
        **definition.get("extraction", {}),
        "source_psd": str(master_psd),
        "canonical_master": True,
        "asset_regenerated_at": datetime.now(timezone.utc).isoformat(),
        "asset_source_size": list(master_size),
        "asset_max_edge": max_edge,
        "asset_mask_channel": "alpha",
        "notes": (
            "Assets regenerated from canonical base_template.psd at production "
            "resolution. Logical coordinates unchanged (1200-space); runtime "
            "renderer downsamples assets to render size as before."
        ),
    }
    definition_path.write_text(json.dumps(definition, indent=2), encoding="utf-8")
    stats["definition"] = str(definition_path)
    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--psd", type=Path, default=DEFAULT_MASTER_PSD)
    parser.add_argument("--template-id", default=DEFAULT_TEMPLATE_ID)
    parser.add_argument("--definitions-dir", type=Path, default=GARMENT_TEMPLATES_DEFINITIONS_DIR)
    parser.add_argument("--assets-dir", type=Path, default=GARMENT_TEMPLATES_ASSETS_DIR)
    parser.add_argument(
        "--max-edge",
        type=int,
        default=2048,
        help="Max long-edge (px) for exported assets. 0 = no cap (full production resolution).",
    )
    parser.add_argument("--report", type=Path, default=None, help="Optional JSON report output path")
    args = parser.parse_args()

    if not args.psd.is_file():
        print(f"Master PSD not found: {args.psd}", file=sys.stderr)
        return 1

    stats = upgrade(
        master_psd=args.psd,
        template_id=args.template_id,
        definitions_dir=args.definitions_dir,
        assets_dir=args.assets_dir,
        max_edge=args.max_edge,
    )

    exported = stats["exported"]
    upscaled = [e for e in exported if e["old_size"] and e["new_size"] and e["new_size"][0] * e["new_size"][1] > e["old_size"][0] * e["old_size"][1]]
    print(f"\nRegenerated {len(exported)} assets from canonical master")
    print(f"  Higher resolution than legacy: {len(upscaled)}")
    if stats["missing"]:
        print(f"  WARNING: {len(stats['missing'])} layer(s) not found in master:")
        for m in stats["missing"]:
            print(f"    - {m['kind']}: {m['layer_path']}")
    # Show a few representative increases
    for e in exported[:6]:
        print(f"  {e['kind']}: {e['layer_path']}  {e['old_size']} -> {e['new_size']}")

    if args.report is not None:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(stats, indent=2), encoding="utf-8")
        print(f"Report saved: {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
