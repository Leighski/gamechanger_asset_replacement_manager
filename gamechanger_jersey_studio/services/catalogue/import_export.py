"""Import and export catalogue components as JSON."""

from __future__ import annotations

import json
from pathlib import Path

from models.component_catalogue import CatalogueComponent, CategoryCatalogue, ComponentCategory


class CatalogueImportExport:
    """JSON manifest import/export for individual components."""

    def export_component(self, component: CatalogueComponent, target: Path) -> Path:
        target = Path(target).expanduser().resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(component.model_dump(mode="json"), indent=2),
            encoding="utf-8",
        )
        return target

    def import_component(self, source: Path) -> CatalogueComponent:
        data = json.loads(Path(source).read_text(encoding="utf-8"))
        return CatalogueComponent.model_validate(data)

    def merge_into_catalogue(
        self,
        catalogue: CategoryCatalogue,
        component: CatalogueComponent,
        *,
        replace: bool = False,
    ) -> CategoryCatalogue:
        existing = {item.id: index for index, item in enumerate(catalogue.components)}
        if component.id in existing:
            if replace:
                catalogue.components[existing[component.id]] = component
            return catalogue
        catalogue.components.append(component)
        return catalogue
