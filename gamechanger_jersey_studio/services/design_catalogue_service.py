"""Load design catalogues — bridges Component Library to legacy DesignCatalogues."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.paths import CONFIG_DIR, COMPONENT_LIBRARY_DIR
from models.component_catalogue import ComponentCategory, ComponentLibrary, CatalogueComponent

CATALOGUES_DIR = CONFIG_DIR / "catalogues"

@dataclass(frozen=True)
class CatalogueItem:
    id: str
    label: str
    description: str = ""
    component_id: str = ""
    status: str = ""
    legacy_ids: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CatalogueItem:
        legacy = data.get("legacy_ids", [])
        return cls(
            id=str(data["id"]),
            label=str(data.get("label", data["id"])),
            description=str(data.get("description", "")),
            component_id=str(data.get("component_id", data["id"])),
            status=str(data.get("status", "")),
            legacy_ids=tuple(str(item) for item in legacy) if legacy else (),
        )

    @classmethod
    def from_component(cls, component: CatalogueComponent) -> CatalogueItem:
        return cls(
            id=component.id,
            label=component.name,
            description=component.description,
            component_id=component.id,
            status=component.status.value,
            legacy_ids=tuple(component.legacy_ids),
        )


@dataclass(frozen=True)
class DesignCatalogues:
    collars: tuple[CatalogueItem, ...]
    patterns: tuple[CatalogueItem, ...]
    sleeves: tuple[CatalogueItem, ...]
    materials: tuple[CatalogueItem, ...]
    trims: tuple[CatalogueItem, ...]
    shadows: tuple[CatalogueItem, ...]
    lighting: tuple[CatalogueItem, ...]
    textures: tuple[CatalogueItem, ...]
    output_profiles: tuple[CatalogueItem, ...]
    colour_palettes: tuple[CatalogueItem, ...] = ()

    def _items(self, category: str) -> tuple[CatalogueItem, ...]:
        mapping = {
            "collars": self.collars,
            "patterns": self.patterns,
            "sleeves": self.sleeves,
            "materials": self.materials,
            "trims": self.trims,
            "shadows": self.shadows,
            "lighting": self.lighting,
            "textures": self.textures,
            "output_profiles": self.output_profiles,
            "colour_palettes": self.colour_palettes,
        }
        return mapping[category]

    def collar_ids(self) -> set[str]:
        return self._all_ids(self.collars)

    def pattern_ids(self) -> set[str]:
        return self._all_ids(self.patterns)

    def sleeve_ids(self) -> set[str]:
        return self._all_ids(self.sleeves)

    def material_ids(self) -> set[str]:
        return self._all_ids(self.materials)

    def trim_ids(self) -> set[str]:
        return self._all_ids(self.trims)

    def shadow_ids(self) -> set[str]:
        return self._all_ids(self.shadows)

    def lighting_ids(self) -> set[str]:
        return self._all_ids(self.lighting)

    def texture_ids(self) -> set[str]:
        return self._all_ids(self.textures)

    def output_profile_ids(self) -> set[str]:
        return self._all_ids(self.output_profiles)

    def colour_palette_ids(self) -> set[str]:
        return self._all_ids(self.colour_palettes)

    def labels_for(self, category: str) -> list[str]:
        return [item.label for item in self._items(category)]

    def id_for_label(self, category: str, label: str) -> str:
        for item in self._items(category):
            if item.label == label:
                return item.id
        return label

    def label_for_id(self, category: str, item_id: str) -> str:
        for item in self._items(category):
            if item.id == item_id or item_id in item.legacy_ids:
                return item.label
        return item_id

    def id_for_reference(self, category: str, reference: str) -> str:
        for item in self._items(category):
            if item.id == reference or reference in item.legacy_ids:
                return item.id
        return reference

    def resolve_id(self, category: str, reference: str) -> str | None:
        """Resolve legacy or canonical reference to canonical component ID."""
        ref = reference.strip()
        for item in self._items(category):
            if item.id == ref:
                return item.id
        for item in self._items(category):
            if ref in (item.id, item.label):
                return item.id
        return None

    @staticmethod
    def _all_ids(items: tuple[CatalogueItem, ...]) -> set[str]:
        ids: set[str] = set()
        for item in items:
            ids.add(item.id)
            ids.update(item.legacy_ids)
        return ids


def catalogue_items_from_library(library: ComponentLibrary) -> DesignCatalogues:
    def items(category: ComponentCategory) -> tuple[CatalogueItem, ...]:
        return tuple(
            CatalogueItem.from_component(component)
            for component in library.components_for(category)
        )

    return DesignCatalogues(
        collars=items(ComponentCategory.COLLARS),
        patterns=items(ComponentCategory.PATTERNS),
        sleeves=items(ComponentCategory.SLEEVES),
        materials=items(ComponentCategory.MATERIALS),
        trims=items(ComponentCategory.TRIMS),
        shadows=items(ComponentCategory.SHADOW_PROFILES),
        lighting=items(ComponentCategory.LIGHTING_PROFILES),
        textures=items(ComponentCategory.TEXTURES),
        output_profiles=items(ComponentCategory.BUILD_PROFILES),
        colour_palettes=items(ComponentCategory.COLOUR_PALETTES),
    )


def _load_items(path: Path) -> tuple[CatalogueItem, ...]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return tuple(CatalogueItem.from_dict(item) for item in data.get("items", []))


def _load_effects(path: Path) -> tuple[tuple[CatalogueItem, ...], tuple[CatalogueItem, ...], tuple[CatalogueItem, ...]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    shadows = tuple(CatalogueItem.from_dict(item) for item in data.get("shadows", []))
    lighting = tuple(CatalogueItem.from_dict(item) for item in data.get("lighting", []))
    textures = tuple(CatalogueItem.from_dict(item) for item in data.get("textures", []))
    return shadows, lighting, textures


def load_catalogues(catalogues_dir: Path | None = None) -> DesignCatalogues:
    """Load catalogues — prefers Component Library, falls back to legacy JSON."""
    if COMPONENT_LIBRARY_DIR.is_dir() and any(COMPONENT_LIBRARY_DIR.rglob("manifest.json")):
        from services.catalogue.loader import CatalogueLoader

        library = CatalogueLoader(COMPONENT_LIBRARY_DIR).load_library()
        if library.all_components():
            return catalogue_items_from_library(library)

    root = catalogues_dir or CATALOGUES_DIR
    shadows, lighting, textures = _load_effects(root / "effects.json")
    return DesignCatalogues(
        collars=_load_items(root / "collars.json"),
        patterns=_load_items(root / "patterns.json"),
        sleeves=_load_items(root / "sleeves.json"),
        materials=_load_items(root / "materials.json"),
        trims=(),
        shadows=shadows,
        lighting=lighting,
        textures=textures,
        output_profiles=_load_items(root / "output_profiles.json"),
        colour_palettes=(),
    )
