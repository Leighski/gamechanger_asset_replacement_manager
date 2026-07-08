"""Load component library catalogues from JSON manifests."""

from __future__ import annotations

import json
from pathlib import Path

from core.paths import COMPONENT_LIBRARY_DIR
from models.component_catalogue import (
    CategoryCatalogue,
    ComponentCategory,
    ComponentLibrary,
    ComponentStatus,
    CatalogueComponent,
    ComponentAssets,
    ComponentVersionEntry,
)


CATEGORY_MANIFEST_FILES: dict[ComponentCategory, str] = {
    ComponentCategory.COLLARS: "collars/manifest.json",
    ComponentCategory.SLEEVES: "sleeves/manifest.json",
    ComponentCategory.PATTERNS: "patterns/manifest.json",
    ComponentCategory.TRIMS: "trims/manifest.json",
    ComponentCategory.MATERIALS: "materials/manifest.json",
    ComponentCategory.TEXTURES: "textures/manifest.json",
    ComponentCategory.LIGHTING_PROFILES: "lighting_profiles/manifest.json",
    ComponentCategory.SHADOW_PROFILES: "shadow_profiles/manifest.json",
    ComponentCategory.EFFECTS: "effects/manifest.json",
    ComponentCategory.BUILD_PROFILES: "build_profiles/manifest.json",
    ComponentCategory.VALIDATION_PROFILES: "validation_profiles/manifest.json",
    ComponentCategory.COLOUR_PALETTES: "colour_palettes/manifest.json",
}


class CatalogueLoader:
    """Load versioned category catalogues from the component library directory."""

    def __init__(self, root: Path | None = None) -> None:
        self._root = root or COMPONENT_LIBRARY_DIR

    @property
    def root(self) -> Path:
        return self._root

    def load_library(self) -> ComponentLibrary:
        library = ComponentLibrary()
        for category, relative in CATEGORY_MANIFEST_FILES.items():
            path = self._root / relative
            if not path.is_file():
                continue
            catalogue = self.load_category_manifest(path)
            library.catalogues[category.value] = catalogue
        return library

    def load_category_manifest(self, path: Path) -> CategoryCatalogue:
        data = json.loads(path.read_text(encoding="utf-8"))
        return CategoryCatalogue.model_validate(data)

    def save_category_manifest(self, catalogue: CategoryCatalogue) -> Path:
        relative = CATEGORY_MANIFEST_FILES[catalogue.category]
        path = self._root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(catalogue.model_dump(mode="json"), indent=2),
            encoding="utf-8",
        )
        return path


def build_component(
    *,
    component_id: str,
    name: str,
    category: ComponentCategory,
    description: str = "",
    status: ComponentStatus = ComponentStatus.CERTIFIED,
    legacy_ids: list[str] | None = None,
    tags: list[str] | None = None,
    preview_image: str = "",
    author: str = "Gamechanger",
) -> CatalogueComponent:
    return CatalogueComponent(
        id=component_id,
        name=name,
        category=category,
        description=description,
        status=status,
        legacy_ids=legacy_ids or [],
        tags=tags or [],
        preview_image=preview_image,
        author=author,
        assets=ComponentAssets(png_preview=preview_image),
        version_history=[
            ComponentVersionEntry(version="1.0.0", notes="Initial certified release", author=author)
        ],
    )
