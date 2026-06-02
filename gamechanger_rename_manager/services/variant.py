"""Variant detection for MAIN / CFX / MT linked assets."""

from __future__ import annotations

import re
from pathlib import Path

from gamechanger_rename_manager.services.asset_model import VariantType

_CFX_RE = re.compile(r"_CFX(?:\.|$)", re.IGNORECASE)
_MT_RE = re.compile(r"_MT(?:\.|$)", re.IGNORECASE)
_ENGP_RE = re.compile(r"_ENGP\.(?:mp4|mxf|mov)$", re.IGNORECASE)


def detect_variant(filename: str) -> VariantType:
    name = Path(filename).name
    if _MT_RE.search(name):
        return VariantType.MT
    if _CFX_RE.search(name):
        return VariantType.CFX
    if _ENGP_RE.search(name) or name.upper().endswith("_ENGP.MP4"):
        return VariantType.MAIN
    stem = Path(name).stem
    if stem.upper().endswith("_ENGP"):
        return VariantType.MAIN
    return VariantType.UNKNOWN


def variant_base_stem(filename: str) -> str:
    """Strip variant suffix to find linked family stem."""
    stem = Path(filename).stem
    for suffix in ("_CFX", "_MT", "_ENGP"):
        if stem.upper().endswith(suffix):
            return stem[: -len(suffix)]
    return stem


def linked_variant_filenames(main_filename: str) -> dict[VariantType, str]:
    """Predict CFX/MT filenames from a MAIN ENGP filename."""
    p = Path(main_filename)
    stem = p.stem
    if stem.upper().endswith("_ENGP"):
        base = stem[:-5]
    else:
        base = variant_base_stem(main_filename)
    return {
        VariantType.MAIN: f"{base}_ENGP.mp4",
        VariantType.CFX: f"{base}_CFX.mp4",
        VariantType.MT: f"{base}_MT.mov",
    }


def apply_rename_to_variant(old_name: str, new_name: str) -> str:
    """Map a MAIN rename target onto the same variant family member."""
    old_v = detect_variant(old_name)
    new_main = Path(new_name)
    linked = linked_variant_filenames(new_main.name if detect_variant(new_name) == VariantType.MAIN else new_name)
    if old_v in linked:
        return linked[old_v]
    # Generic: replace basename stem portion
    old_p = Path(old_name)
    new_p = Path(new_name)
    if old_p.suffix == new_p.suffix:
        return new_p.name
    return new_p.stem + old_p.suffix
