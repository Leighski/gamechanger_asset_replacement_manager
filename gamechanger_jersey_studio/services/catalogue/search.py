"""Component search, filter, and sort."""

from __future__ import annotations

from enum import Enum

from models.component_catalogue import CatalogueComponent, ComponentCategory, ComponentLibrary, ComponentStatus


class SortMode(str, Enum):
    NAME_ASC = "name_asc"
    NAME_DESC = "name_desc"
    MODIFIED_DESC = "modified_desc"
    STATUS = "status"


class ComponentSearchService:
    """Search and filter components across the library."""

    def search(
        self,
        library: ComponentLibrary,
        *,
        query: str = "",
        category: ComponentCategory | str | None = None,
        tags: list[str] | None = None,
        status: ComponentStatus | None = None,
        sort: SortMode = SortMode.NAME_ASC,
    ) -> list[CatalogueComponent]:
        if category is not None:
            pool = library.components_for(category)
        else:
            pool = library.all_components()

        query_lower = query.strip().lower()
        tag_set = {tag.lower() for tag in (tags or []) if tag.strip()}

        filtered: list[CatalogueComponent] = []
        for component in pool:
            if status is not None and component.status != status:
                continue
            if tag_set and not tag_set.intersection({t.lower() for t in component.tags}):
                continue
            if query_lower:
                haystack = " ".join(
                    [
                        component.id,
                        component.name,
                        component.description,
                        " ".join(component.tags),
                        " ".join(component.legacy_ids),
                    ]
                ).lower()
                if query_lower not in haystack:
                    continue
            filtered.append(component)

        return self._sort(filtered, sort)

    def _sort(self, components: list[CatalogueComponent], mode: SortMode) -> list[CatalogueComponent]:
        if mode == SortMode.NAME_ASC:
            return sorted(components, key=lambda c: c.name.lower())
        if mode == SortMode.NAME_DESC:
            return sorted(components, key=lambda c: c.name.lower(), reverse=True)
        if mode == SortMode.MODIFIED_DESC:
            return sorted(components, key=lambda c: c.modified_at, reverse=True)
        if mode == SortMode.STATUS:
            order = {
                ComponentStatus.CERTIFIED: 0,
                ComponentStatus.APPROVED: 1,
                ComponentStatus.REVIEW: 2,
                ComponentStatus.DRAFT: 3,
                ComponentStatus.DEPRECATED: 4,
            }
            return sorted(components, key=lambda c: (order.get(c.status, 9), c.name.lower()))
        return components
