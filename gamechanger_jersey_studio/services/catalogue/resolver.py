"""Resolve catalogue references to components with backwards compatibility."""

from __future__ import annotations

from models.component_catalogue import (
    CatalogueComponent,
    ComponentCategory,
    ComponentLibrary,
    DESIGN_SPEC_CATALOGUE_FIELDS,
)
from models.design_specification import DesignSpecification


class ComponentReferenceResolver:
    """Resolve design-spec references to catalogue components."""

    def resolve(
        self,
        library: ComponentLibrary,
        category: ComponentCategory | str,
        reference: str,
    ) -> CatalogueComponent | None:
        if not reference or not reference.strip():
            return None
        return library.get_component(category, reference.strip())

    def canonical_id(
        self,
        library: ComponentLibrary,
        category: ComponentCategory | str,
        reference: str,
    ) -> str:
        component = self.resolve(library, category, reference)
        return component.id if component else reference

    def display_name(
        self,
        library: ComponentLibrary,
        category: ComponentCategory | str,
        reference: str,
    ) -> str:
        component = self.resolve(library, category, reference)
        return component.name if component else reference

    def resolve_spec_field(
        self,
        library: ComponentLibrary,
        field_name: str,
        reference: str,
    ) -> CatalogueComponent | None:
        category = DESIGN_SPEC_CATALOGUE_FIELDS.get(field_name)
        if category is None:
            return None
        return self.resolve(library, category, reference)

    def display_for_spec_field(
        self,
        library: ComponentLibrary,
        field_name: str,
        reference: str,
    ) -> str:
        category = DESIGN_SPEC_CATALOGUE_FIELDS.get(field_name)
        if category is None:
            return reference
        return self.display_name(library, category, reference)

    def normalize_spec_references(
        self,
        library: ComponentLibrary,
        spec: DesignSpecification,
    ) -> dict[str, str]:
        """Return field → canonical ID mappings for legacy references."""
        updates: dict[str, str] = {}
        for field_name, category in DESIGN_SPEC_CATALOGUE_FIELDS.items():
            current = str(spec.get_field(field_name) or "")
            if not current:
                continue
            canonical = self.canonical_id(library, category, current)
            if canonical != current:
                updates[field_name] = canonical
        return updates
