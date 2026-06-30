"""Component catalogue validation."""

from __future__ import annotations

from models.component_catalogue import (
    CatalogueComponent,
    CatalogueValidationIssue,
    ComponentCategory,
    ComponentLibrary,
    ComponentStatus,
)


class CatalogueValidator:
    """Validate component library integrity and design-spec references."""

    def validate_library(self, library: ComponentLibrary) -> list[CatalogueValidationIssue]:
        issues: list[CatalogueValidationIssue] = []
        seen_ids: dict[str, str] = {}

        for category_key, catalogue in library.catalogues.items():
            for component in catalogue.components:
                issues.extend(self._validate_component(component, category_key))
                if component.id in seen_ids:
                    issues.append(
                        CatalogueValidationIssue(
                            severity="error",
                            category=category_key,
                            component_id=component.id,
                            message=f"Duplicate ID across library (also in {seen_ids[component.id]}).",
                        )
                    )
                seen_ids[component.id] = category_key
                for legacy in component.legacy_ids:
                    legacy_key = f"legacy:{legacy}"
                    if legacy_key in seen_ids:
                        issues.append(
                            CatalogueValidationIssue(
                                severity="error",
                                category=category_key,
                                component_id=component.id,
                                message=f"Duplicate legacy ID '{legacy}'.",
                            )
                        )
                    seen_ids[legacy_key] = category_key

        return issues

    def validate_reference(
        self,
        library: ComponentLibrary,
        category: ComponentCategory | str,
        reference: str,
        *,
        production: bool = True,
    ) -> list[CatalogueValidationIssue]:
        if not reference or not reference.strip():
            return []
        ref = reference.strip()
        component = library.get_component(category, ref)
        cat_key = category.value if isinstance(category, ComponentCategory) else category
        if component is None:
            return [
                CatalogueValidationIssue(
                    severity="error",
                    category=cat_key,
                    component_id=ref,
                    message=f"Missing component reference '{ref}'.",
                )
            ]
        issues: list[CatalogueValidationIssue] = []
        if component.status == ComponentStatus.DEPRECATED:
            issues.append(
                CatalogueValidationIssue(
                    severity="warning",
                    category=cat_key,
                    component_id=component.id,
                    message=f"Component '{component.name}' is deprecated.",
                )
            )
        if production and component.status in (ComponentStatus.DRAFT, ComponentStatus.REVIEW):
            issues.append(
                CatalogueValidationIssue(
                    severity="warning",
                    category=cat_key,
                    component_id=component.id,
                    message=f"Component '{component.name}' is {component.status.value} — not certified for production.",
                )
            )
        return issues

    def _validate_component(self, component: CatalogueComponent, category: str) -> list[CatalogueValidationIssue]:
        issues: list[CatalogueValidationIssue] = []
        if not component.id:
            issues.append(
                CatalogueValidationIssue(
                    severity="error",
                    category=category,
                    message="Component missing ID.",
                )
            )
        if not component.name:
            issues.append(
                CatalogueValidationIssue(
                    severity="error",
                    category=category,
                    component_id=component.id,
                    message="Component missing name.",
                )
            )
        if not component.version:
            issues.append(
                CatalogueValidationIssue(
                    severity="warning",
                    category=category,
                    component_id=component.id,
                    message="Component missing version.",
                )
            )
        for dep in component.dependencies:
            if not dep:
                issues.append(
                    CatalogueValidationIssue(
                        severity="warning",
                        category=category,
                        component_id=component.id,
                        message="Empty dependency reference.",
                    )
                )
        return issues
