"""Design Specification subsystem tests."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from models.design_specification import DesignSpecification, OutputProfile
from models.project import KitType, NewProjectRequest, ProjectDocument
from services.design_catalogue_service import load_catalogues
from services.design_spec_completion import calculate_completion
from services.design_spec_undo import DesignSpecChange, DesignSpecUndoStack
from services.design_spec_validation import validate_design_specification
from services.design_specification_service import DesignSpecificationService
from services.project_format import DESIGN_SPEC_NAME, read_project_package, write_project_package
from services.project_history_service import ProjectHistoryService
from services.projects_manager import ProjectsManager
from services.recent_projects_manager import RecentProjectsManager
from services.settings_manager import SettingsManager
from services.workspace_service import WorkspaceService


@pytest.fixture
def catalogues(tmp_path: Path):
    source = Path(__file__).resolve().parent.parent / "config" / "catalogues"
    return load_catalogues(source)


@pytest.fixture
def design_service(catalogues) -> DesignSpecificationService:
    return DesignSpecificationService(
        ProjectHistoryService(),
        catalogues=catalogues,
        application_version="1.0.0-alpha.4",
    )


@pytest.fixture
def sample_document() -> ProjectDocument:
    from models.project import ProjectManifest

    manifest = ProjectManifest(
        project_name="Coventry City Home 2026",
        club_name="Coventry City",
        competition="Championship",
        season="2025/26",
        kit_type=KitType.HOME,
        output_folder="/tmp/out",
        author="Leigh",
    )
    return ProjectDocument(manifest=manifest)


@pytest.fixture
def projects_manager(tmp_path: Path) -> ProjectsManager:
    settings = SettingsManager(path=tmp_path / "settings.json")
    settings.load()
    recent = RecentProjectsManager(settings)
    workspace = WorkspaceService(root=tmp_path / "workspace")
    return ProjectsManager(recent, workspace=workspace, application_version="1.0.0-alpha.4")


def _coventry_spec() -> DesignSpecification:
    return DesignSpecification(
        club="Coventry City",
        competition="Championship",
        season="2025/26",
        kit_type=KitType.HOME,
        manufacturer="Hummel",
        primary_colour="#69B3E7",
        secondary_colour="#FFFFFF",
        third_colour="#1C1C1C",
        sleeve_colour="#69B3E7",
        collar_colour="#FFFFFF",
        trim_colour="#1C1C1C",
        pattern="hoops",
        pattern_scale=1.0,
        pattern_rotation=0.0,
        pattern_opacity=0.85,
        sleeve_style="standard",
        collar_style="v-neck",
        trim_style="TRIM_0002",
        material_style="polyester",
        shadow_style="broadcast",
        lighting_style="studio",
        texture_style="fabric",
        output_profile=OutputProfile.GAMECHANGER_BROADCAST,
        operator_notes="Sky Blue home kit — EPIC 3 example project.",
    )


def test_catalogue_loading(catalogues) -> None:
    assert "COLLAR_0001" in catalogues.collar_ids()
    assert "crew" in catalogues.collar_ids()
    assert "PATTERN_0002" in catalogues.pattern_ids()
    assert "hoops" in catalogues.pattern_ids()
    assert len(catalogues.output_profiles) == 4


def test_validation_requires_colours_and_catalogue_ids(design_service, sample_document) -> None:
    spec = design_service.ensure_spec(sample_document)
    result = design_service.validate(spec)
    assert not result.is_valid
    assert any(issue.field == "primary_colour" for issue in result.issues)


def test_validation_passes_for_complete_spec(design_service) -> None:
    result = validate_design_specification(_coventry_spec(), design_service.catalogues)
    assert result.is_valid


def test_pattern_opacity_limits(design_service, catalogues) -> None:
    spec = _coventry_spec()
    spec.pattern_opacity = 1.5
    result = validate_design_specification(spec, catalogues)
    assert any(issue.field == "pattern_opacity" for issue in result.issues)


def test_apply_change_records_history(design_service, sample_document) -> None:
    design_service.apply_change(sample_document, "primary_colour", "#69B3E7", user="Leigh")
    assert sample_document.dirty
    assert sample_document.design_spec is not None
    assert sample_document.design_spec.primary_colour == "#69B3E7"
    assert sample_document.history.entries[-1].event.value == "Design Specification Changed"
    details = json.loads(sample_document.history.entries[-1].details)
    assert details["property"] == "primary_colour"
    assert details["old_value"] == ""
    assert details["new_value"] == "#69B3E7"


def test_undo_redo_round_trip(design_service, sample_document) -> None:
    design_service.apply_change(sample_document, "club", "Coventry City", user="Leigh")
    design_service.apply_change(sample_document, "manufacturer", "Hummel", user="Leigh")
    assert design_service.can_undo()
    design_service.undo(sample_document, user="Leigh")
    assert sample_document.design_spec is not None
    assert sample_document.design_spec.manufacturer == ""
    design_service.redo(sample_document, user="Leigh")
    assert sample_document.design_spec.manufacturer == "Hummel"


def test_undo_stack_push(design_service) -> None:
    stack = DesignSpecUndoStack()
    stack.push(DesignSpecChange("club", "", "Coventry City"))
    assert stack.can_undo()
    change = stack.undo()
    assert change is not None
    assert change.property_name == "club"


def test_completion_calculation(design_service) -> None:
    report = calculate_completion(_coventry_spec())
    assert report.overall_percent >= 90
    assert report.as_dict()["colours"] == 100


def test_persistence_in_gjs_package(design_service, sample_document, tmp_path: Path) -> None:
    spec = _coventry_spec()
    sample_document.design_spec = spec
    target = tmp_path / "Coventry_City_Home_2026.gjs"
    write_project_package(sample_document, target)
    with zipfile.ZipFile(target) as zf:
        assert DESIGN_SPEC_NAME in zf.namelist()
    reloaded, _ = read_project_package(target)
    assert reloaded.design_spec is not None
    assert reloaded.design_spec.club == "Coventry City"
    assert reloaded.design_spec.pattern == "hoops"


def test_backward_compatible_projects_without_design_spec(
    projects_manager: ProjectsManager,
    tmp_path: Path,
) -> None:
    doc = projects_manager.new_project(
        NewProjectRequest(
            project_name="Legacy Project",
            club_name="Test FC",
            competition="League",
            season="2024/25",
            kit_type=KitType.HOME,
            output_folder=str(tmp_path / "out"),
            author="Leigh",
        )
    )
    path = Path(doc.file_path)
    with zipfile.ZipFile(path, "r") as zf:
        names = zf.namelist()
    assert DESIGN_SPEC_NAME in names
    projects_manager.close_project()
    reloaded, _ = read_project_package(path)
    assert reloaded.design_spec is not None
    assert reloaded.design_spec.club == "Test FC"


def test_project_integration_via_manager(projects_manager: ProjectsManager, tmp_path: Path) -> None:
    doc = projects_manager.new_project(
        NewProjectRequest(
            project_name="Coventry City Home 2026",
            club_name="Coventry City",
            competition="Championship",
            season="2025/26",
            kit_type=KitType.HOME,
            output_folder=str(tmp_path / "out"),
            author="Leigh",
        )
    )
    service = projects_manager.design_specification_service
    service.apply_change(doc, "manufacturer", "Hummel", user="Leigh")
    service.apply_change(doc, "primary_colour", "#69B3E7", user="Leigh")
    projects_manager.save_project()
    projects_manager.close_project()
    projects_manager.open_project(doc.file_path)
    opened = projects_manager.document
    assert opened is not None
    assert opened.design_spec is not None
    assert opened.design_spec.manufacturer == "Hummel"


def test_manifest_sync_on_project_fields(design_service, sample_document) -> None:
    design_service.apply_change(sample_document, "club", "Coventry City", user="Leigh")
    assert sample_document.manifest.club_name == "Coventry City"
    design_service.apply_change(
        sample_document,
        "output_profile",
        OutputProfile.AUTHENTIC,
        user="Leigh",
    )
    assert sample_document.manifest.build_profile == "Authentic"
