"""Component Library and Catalogue Manager tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from core.paths import COMPONENT_LIBRARY_DIR
from models.component_catalogue import ComponentCategory, ComponentStatus
from models.design_specification import DesignSpecification
from services.catalogue.loader import CatalogueLoader
from services.catalogue.resolver import ComponentReferenceResolver
from services.catalogue.search import SortMode
from services.catalogue.validator import CatalogueValidator
from services.catalogue_manager_service import CatalogueManagerService
from services.design_catalogue_service import load_catalogues
from services.design_spec_validation import validate_design_specification


@pytest.fixture
def manager() -> CatalogueManagerService:
    service = CatalogueManagerService(COMPONENT_LIBRARY_DIR)
    service.load()
    return service


def test_catalogue_loading(manager: CatalogueManagerService) -> None:
    assert len(manager.library.all_components()) >= 30
    assert manager.last_load_ms >= 0
    collar = manager.get_component(ComponentCategory.COLLARS, "COLLAR_0001")
    assert collar is not None
    assert collar.name == "Crew Neck"


def test_legacy_reference_resolution(manager: CatalogueManagerService) -> None:
    resolver = manager.resolver
    component = resolver.resolve(manager.library, ComponentCategory.COLLARS, "crew")
    assert component is not None
    assert component.id == "COLLAR_0001"
    assert manager.display_name(ComponentCategory.COLLARS, "v-neck") == "V-Neck"


def test_component_validation(manager: CatalogueManagerService) -> None:
    issues = manager.validate_library()
    errors = [issue for issue in issues if issue.severity == "error"]
    assert not errors


def test_search_and_filter(manager: CatalogueManagerService) -> None:
    collars = manager.search("crew", category=ComponentCategory.COLLARS)
    assert any(c.id == "COLLAR_0001" for c in collars)
    certified = manager.search(category=ComponentCategory.PATTERNS, status=ComponentStatus.CERTIFIED)
    assert certified
    sorted_names = manager.search(category=ComponentCategory.COLLARS, sort=SortMode.NAME_ASC)
    assert sorted_names[0].name <= sorted_names[-1].name


def test_design_catalogues_bridge(manager: CatalogueManagerService) -> None:
    cats = manager.design_catalogues
    assert cats.label_for_id("collars", "crew") == "Crew Neck"
    assert "COLLAR_0001" in cats.collar_ids()


def test_design_spec_validation_with_legacy_ids(manager: CatalogueManagerService) -> None:
    spec = DesignSpecification(
        club="Coventry City",
        competition="Championship",
        season="2025/26",
        manufacturer="Hummel",
        primary_colour="#69B3E7",
        secondary_colour="#FFFFFF",
        third_colour="#69B3E7",
        sleeve_colour="#69B3E7",
        collar_colour="#FFFFFF",
        trim_colour="#FFFFFF",
        pattern="solid",
        collar_style="v-neck",
        sleeve_style="long",
    )
    result = validate_design_specification(spec, manager.design_catalogues, manager.library)
    assert result.is_valid


def test_missing_component_warning(manager: CatalogueManagerService) -> None:
    issues = manager.validate_reference(ComponentCategory.COLLARS, "NOT_A_REAL_ID")
    assert issues
    assert issues[0].severity == "error"


def test_import_export_round_trip(manager: CatalogueManagerService, tmp_path: Path) -> None:
    component = manager.get_component(ComponentCategory.COLLARS, "COLLAR_0001")
    assert component is not None
    export_path = tmp_path / "collar_export.json"
    manager.export_component(component, export_path, user="Test")
    assert export_path.is_file()
    imported = manager.import_component(
        export_path,
        category=ComponentCategory.COLLARS,
        user="Test",
        replace=True,
    )
    assert imported.id == component.id


def test_resolver_normalize_legacy(manager: CatalogueManagerService) -> None:
    spec = DesignSpecification(collar_style="crew", pattern="hoops")
    updates = manager.resolver.normalize_spec_references(manager.library, spec)
    assert updates.get("collar_style") == "COLLAR_0001"
    assert updates.get("pattern") == "PATTERN_0002"


def test_projects_catalogue_performance(manager: CatalogueManagerService) -> None:
    assert manager.last_load_ms < 500.0
