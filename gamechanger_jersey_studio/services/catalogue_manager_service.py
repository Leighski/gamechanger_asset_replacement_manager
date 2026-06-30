"""Catalogue Manager — load, validate, search, and manage the Component Library."""

from __future__ import annotations

import time
from pathlib import Path

from models.component_catalogue import (
    CatalogueComponent,
    CatalogueHistoryEventType,
    CatalogueValidationIssue,
    CategoryCatalogue,
    ComponentCategory,
    ComponentLibrary,
    ComponentStatus,
)
from services.catalogue.history import CatalogueHistoryService
from services.catalogue.import_export import CatalogueImportExport
from services.catalogue.loader import CatalogueLoader
from services.catalogue.resolver import ComponentReferenceResolver
from services.catalogue.search import ComponentSearchService, SortMode
from services.catalogue.validator import CatalogueValidator
from services.design_catalogue_service import DesignCatalogues, catalogue_items_from_library
from services.logging_manager import get_logger

logger = get_logger()


class CatalogueManagerService:
    """Production catalogue subsystem for reusable Gamechanger design components."""

    def __init__(self, library_root: Path | None = None) -> None:
        self._loader = CatalogueLoader(library_root)
        self._validator = CatalogueValidator()
        self._search = ComponentSearchService()
        self._resolver = ComponentReferenceResolver()
        self._import_export = CatalogueImportExport()
        self._history = CatalogueHistoryService()
        self._library = ComponentLibrary()
        self._design_catalogues: DesignCatalogues | None = None
        self._last_load_ms: float = 0.0

    @property
    def library(self) -> ComponentLibrary:
        return self._library

    @property
    def resolver(self) -> ComponentReferenceResolver:
        return self._resolver

    @property
    def design_catalogues(self) -> DesignCatalogues:
        if self._design_catalogues is None:
            self._design_catalogues = catalogue_items_from_library(self._library)
        return self._design_catalogues

    @property
    def last_load_ms(self) -> float:
        return self._last_load_ms

    def load(self) -> ComponentLibrary:
        started = time.perf_counter()
        self._history.load()
        self._library = self._loader.load_library()
        self._design_catalogues = catalogue_items_from_library(self._library)
        self._last_load_ms = round((time.perf_counter() - started) * 1000.0, 2)
        issues = self.validate_library()
        error_count = sum(1 for issue in issues if issue.severity == "error")
        self._history.record(
            CatalogueHistoryEventType.CATALOGUE_LOADED,
            details=f"{len(self._library.all_components())} components, {error_count} errors",
        )
        self._history.save()
        logger.info(
            "Component library loaded — {} components in {:.1f}ms",
            len(self._library.all_components()),
            self._last_load_ms,
        )
        return self._library

    def reload(self) -> ComponentLibrary:
        return self.load()

    def validate_library(self) -> list[CatalogueValidationIssue]:
        return self._validator.validate_library(self._library)

    def validate_reference(
        self,
        category: ComponentCategory | str,
        reference: str,
        *,
        production: bool = True,
    ) -> list[CatalogueValidationIssue]:
        return self._validator.validate_reference(
            self._library, category, reference, production=production
        )

    def get_component(
        self,
        category: ComponentCategory | str,
        component_id: str,
    ) -> CatalogueComponent | None:
        return self._library.get_component(category, component_id)

    def search(
        self,
        query: str = "",
        *,
        category: ComponentCategory | str | None = None,
        tags: list[str] | None = None,
        status: ComponentStatus | None = None,
        sort: SortMode = SortMode.NAME_ASC,
    ) -> list[CatalogueComponent]:
        return self._search.search(
            self._library,
            query=query,
            category=category,
            tags=tags,
            status=status,
            sort=sort,
        )

    def categories(self) -> list[ComponentCategory]:
        return [ComponentCategory(key) for key in self._library.catalogues]

    def display_name(self, category: ComponentCategory | str, reference: str) -> str:
        return self._resolver.display_name(self._library, category, reference)

    def canonical_id(self, category: ComponentCategory | str, reference: str) -> str:
        return self._resolver.canonical_id(self._library, category, reference)

    def export_component(self, component: CatalogueComponent, target: Path, *, user: str = "") -> Path:
        path = self._import_export.export_component(component, target)
        self._history.record(
            CatalogueHistoryEventType.COMPONENT_EXPORTED,
            component_id=component.id,
            category=component.category.value,
            user=user,
            details=str(path),
        )
        self._history.save()
        logger.info("Component exported — {} to {}", component.id, path)
        return path

    def import_component(
        self,
        source: Path,
        *,
        category: ComponentCategory,
        user: str = "",
        replace: bool = False,
    ) -> CatalogueComponent:
        component = self._import_export.import_component(source)
        catalogue = self._library.catalogues.get(category.value)
        if catalogue is None:
            catalogue = CategoryCatalogue(
                catalogue_id=category.value,
                category=category,
                components=[],
            )
            self._library.catalogues[category.value] = catalogue
        self._import_export.merge_into_catalogue(catalogue, component, replace=replace)
        self._loader.save_category_manifest(catalogue)
        self._design_catalogues = catalogue_items_from_library(self._library)
        self._history.record(
            CatalogueHistoryEventType.COMPONENT_IMPORTED,
            component_id=component.id,
            category=category.value,
            user=user,
            details=str(source),
        )
        self._history.save()
        logger.info("Component imported — {} ({})", component.id, category.value)
        return component

    def preview_path(self, component: CatalogueComponent) -> Path | None:
        rel = component.preview_image or component.assets.png_preview
        if not rel:
            return None
        path = self._loader.root / rel
        return path if path.is_file() else None
