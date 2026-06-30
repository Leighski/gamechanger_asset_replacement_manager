"""Reference image management tests."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest
from PIL import Image

from models.project import KitType, NewProjectRequest, ProjectDocument, ProjectManifest
from models.reference_image import ImageCategory, ReferenceImageManifest
from services.project_format import read_project_package, write_project_package
from services.projects_manager import ProjectsManager
from services.recent_projects_manager import RecentProjectsManager
from services.reference_image_service import REFERENCES_MANIFEST_NAME, ReferenceImageService
from services.reference_image_validation import validate_reference_manifest
from services.reference_thumbnail_service import ReferenceThumbnailService
from services.settings_manager import SettingsManager
from services.workspace_service import WorkspaceService


@pytest.fixture
def workspace(tmp_path: Path) -> WorkspaceService:
    return WorkspaceService(root=tmp_path / "workspace")


@pytest.fixture
def reference_service(workspace: WorkspaceService) -> ReferenceImageService:
    return ReferenceImageService(workspace, application_version="1.0.0-alpha.5")


@pytest.fixture
def projects_manager(tmp_path: Path) -> ProjectsManager:
    settings = SettingsManager(path=tmp_path / "settings.json")
    settings.load()
    recent = RecentProjectsManager(settings)
    workspace = WorkspaceService(root=tmp_path / "workspace")
    return ProjectsManager(recent, workspace=workspace, application_version="1.0.0-alpha.5")


@pytest.fixture
def sample_png(tmp_path: Path) -> Path:
    path = tmp_path / "front.png"
    Image.new("RGB", (800, 600), color=(30, 120, 200)).save(path, format="PNG")
    return path


@pytest.fixture
def sample_document() -> ProjectDocument:
    manifest = ProjectManifest(
        project_name="Test Project",
        club_name="Test FC",
        competition="League",
        season="2025/26",
        kit_type=KitType.HOME,
        output_folder="/tmp/out",
        author="Leigh",
    )
    return ProjectDocument(manifest=manifest, reference_manifest=ReferenceImageManifest())


def test_import_creates_record(reference_service: ReferenceImageService, sample_document, sample_png) -> None:
    imported = reference_service.import_files(
        sample_document,
        [sample_png],
        user="Leigh",
        tags=[ImageCategory.FRONT_VIEW.value],
    )
    assert len(imported) == 1
    record = imported[0]
    assert record.width == 800
    assert record.height == 600
    assert record.checksum
    assert ImageCategory.FRONT_VIEW.value in record.tags
    assert sample_document.dirty
    assert sample_document.manifest.reference_image_count == 1


def test_delete_image(reference_service: ReferenceImageService, sample_document, sample_png) -> None:
    imported = reference_service.import_files(sample_document, [sample_png], user="Leigh")
    image_id = imported[0].image_id
    reference_service.delete_image(sample_document, image_id, user="Leigh")
    assert reference_service.manifest.images == []
    assert sample_document.manifest.reference_image_count == 0


def test_replace_image(reference_service: ReferenceImageService, sample_document, sample_png, tmp_path) -> None:
    imported = reference_service.import_files(sample_document, [sample_png], user="Leigh")
    image_id = imported[0].image_id
    replacement = tmp_path / "rear.png"
    Image.new("RGB", (1024, 768), color=(200, 30, 30)).save(replacement, format="PNG")
    updated = reference_service.replace_image(sample_document, image_id, replacement, user="Leigh")
    assert updated.width == 1024
    assert updated.filename == "rear.png"


def test_validation_warns_without_front_view(reference_service: ReferenceImageService, sample_document, sample_png) -> None:
    reference_service.import_files(sample_document, [sample_png], user="Leigh", tags=[ImageCategory.DETAIL.value])
    result = reference_service.validate()
    assert any("Front View" in issue.message for issue in result.issues)


def test_validation_passes_with_front_view(reference_service: ReferenceImageService, sample_document, sample_png) -> None:
    reference_service.import_files(
        sample_document,
        [sample_png],
        user="Leigh",
        tags=[ImageCategory.FRONT_VIEW.value],
    )
    result = reference_service.validate()
    assert not any("Front View" in issue.message for issue in result.issues)


def test_duplicate_checksum_warning(reference_service: ReferenceImageService, sample_document, sample_png) -> None:
    reference_service.import_files(sample_document, [sample_png], user="Leigh", tags=[ImageCategory.FRONT_VIEW.value])
    reference_service.import_files(sample_document, [sample_png], user="Leigh", tags=[ImageCategory.REAR_VIEW.value])
    result = validate_reference_manifest(reference_service.manifest)
    assert any(issue.field == "checksum" for issue in result.issues)


def test_thumbnail_generation(reference_service: ReferenceImageService, sample_document, sample_png) -> None:
    imported = reference_service.import_files(sample_document, [sample_png], user="Leigh")
    thumb = reference_service.thumbnail_path(sample_document.manifest.project_id, imported[0].image_id)
    assert thumb.is_file()


def test_persistence_in_gjs(reference_service: ReferenceImageService, sample_document, sample_png, tmp_path) -> None:
    reference_service.import_files(
        sample_document,
        [sample_png],
        user="Leigh",
        tags=[ImageCategory.FRONT_VIEW.value],
    )
    target = tmp_path / "Test.gjs"
    write_project_package(sample_document, target, reference_blobs=dict(reference_service.byte_store.items()))
    with zipfile.ZipFile(target) as zf:
        assert REFERENCES_MANIFEST_NAME in zf.namelist()
        names = [name for name in zf.namelist() if name.startswith("references/images/")]
        assert len(names) == 1
    reloaded, blobs = read_project_package(target)
    assert reloaded.reference_manifest is not None
    assert len(reloaded.reference_manifest.images) == 1
    assert blobs


def test_history_on_import(reference_service: ReferenceImageService, sample_document, sample_png) -> None:
    reference_service.import_files(sample_document, [sample_png], user="Leigh")
    assert sample_document.history.entries[-1].event.value == "Reference Image Imported"
    details = json.loads(sample_document.history.entries[-1].details)
    assert "image_id" in details


def test_project_manager_integration(projects_manager: ProjectsManager, sample_png, tmp_path: Path) -> None:
    doc = projects_manager.new_project(
        NewProjectRequest(
            project_name="Image Test",
            club_name="Test FC",
            competition="League",
            season="2025/26",
            kit_type=KitType.HOME,
            output_folder=str(tmp_path / "out"),
            author="Leigh",
        )
    )
    service = projects_manager.reference_image_service
    service.import_files(doc, [sample_png], user="Leigh", tags=[ImageCategory.FRONT_VIEW.value])
    projects_manager.save_project()
    projects_manager.close_project()
    projects_manager.open_project(doc.file_path)
    opened = projects_manager.document
    assert opened is not None
    assert opened.reference_manifest is not None
    assert len(opened.reference_manifest.images) == 1


def test_backward_compatible_without_reference_manifest(projects_manager: ProjectsManager, tmp_path: Path) -> None:
    doc = projects_manager.new_project(
        NewProjectRequest(
            project_name="Legacy",
            club_name="Test FC",
            competition="League",
            season="2025/26",
            kit_type=KitType.HOME,
            output_folder=str(tmp_path / "out"),
            author="Leigh",
        )
    )
    path = Path(doc.file_path)
    projects_manager.close_project()
    reloaded, blobs = read_project_package(path)
    assert reloaded.reference_manifest is not None
    assert blobs == {}
