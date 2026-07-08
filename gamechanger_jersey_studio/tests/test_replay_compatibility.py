"""Regression tests for ReferenceImageRecord compatibility and production replay."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from PIL import Image

from models.project import KitType, ProjectDocument, ProjectManifest
from models.reference_image import ImageCategory, ReferenceImageManifest, ReferenceImageRecord
from models.psd_template import UNKNOWN_TEMPLATE_LABEL, TemplateProjectSettings
from models.validation import ReplayStageType
from services.production.audit_service import ProductionAuditService
from services.production.replay_service import ReplayService
from services.projects_manager import ProjectsManager
from services.recent_projects_manager import RecentProjectsManager
from services.reference_image_service import ReferenceImageService
from services.settings_manager import SettingsManager
from services.workspace_service import WorkspaceService

pytestmark = pytest.mark.skipif(
    os.environ.get("GJS_SKIP_QT_TESTS") == "1",
    reason="Qt GUI tests disabled",
)


@pytest.fixture
def replay_service() -> ReplayService:
    return ReplayService()


def test_legacy_view_type_migrated_to_tags() -> None:
    record = ReferenceImageRecord.model_validate(
        {
            "filename": "legacy.png",
            "view_type": "Front View",
            "imported_at": "2025-01-01T12:00:00+00:00",
        }
    )
    assert record.category_labels() == ["Front View"]
    assert record.import_timestamp() == "2025-01-01T12:00:00+00:00"


def test_current_schema_uses_tags() -> None:
    record = ReferenceImageRecord(
        filename="current.png",
        tags=[ImageCategory.FRONT_VIEW.value, ImageCategory.DETAIL.value],
    )
    assert record.primary_category_label() == ImageCategory.FRONT_VIEW.value
    assert len(record.category_labels()) == 2


def test_missing_optional_fields_replay_entry() -> None:
    record = ReferenceImageRecord(filename="minimal.png")
    entry = record.replay_entry()
    assert entry["id"]
    assert entry["filename"] == "minimal.png"
    assert "categories" not in entry


def test_replay_entry_includes_categories_when_present() -> None:
    record = ReferenceImageRecord(
        filename="tagged.png",
        tags=[ImageCategory.COLLAR.value],
    )
    entry = record.replay_entry()
    assert entry["categories"] == [ImageCategory.COLLAR.value]


def test_legacy_category_field_image_category() -> None:
    record = ReferenceImageRecord.model_validate(
        {"filename": "x.png", "image_category": "Rear View"}
    )
    assert record.category_labels() == ["Rear View"]


def test_replay_with_current_reference_images(replay_service: ReplayService) -> None:
    manifest = ProjectManifest(
        project_name="Replay Test",
        club_name="Test FC",
        competition="League",
        season="2025/26",
        kit_type=KitType.HOME,
        output_folder="/tmp",
        author="Test",
    )
    record = ReferenceImageRecord(
        filename="front.png",
        tags=[ImageCategory.FRONT_VIEW.value],
    )
    document = ProjectDocument(
        manifest=manifest,
        reference_manifest=ReferenceImageManifest(images=[record]),
    )
    replay = replay_service.build_replay(document)
    ref_step = next(s for s in replay.steps if s.stage == ReplayStageType.REFERENCE_IMAGES)
    images = ref_step.details["images"]
    assert images[0]["categories"] == [ImageCategory.FRONT_VIEW.value]


def test_replay_with_legacy_view_type_json(replay_service: ReplayService) -> None:
    manifest = ProjectManifest(
        project_name="Legacy Replay",
        club_name="Test FC",
        competition="League",
        season="2025/26",
        kit_type=KitType.HOME,
        output_folder="/tmp",
        author="Test",
    )
    legacy = ReferenceImageRecord.model_validate(
        {"filename": "legacy.png", "view_type": "Side View"}
    )
    document = ProjectDocument(
        manifest=manifest,
        reference_manifest=ReferenceImageManifest(images=[legacy]),
    )
    replay = replay_service.build_replay(document)
    ref_step = next(s for s in replay.steps if s.stage == ReplayStageType.REFERENCE_IMAGES)
    assert ref_step.details["images"][0]["categories"] == ["Side View"]


def test_replay_without_reference_manifest(replay_service: ReplayService) -> None:
    manifest = ProjectManifest(
        project_name="No Refs",
        club_name="Test FC",
        competition="League",
        season="2025/26",
        kit_type=KitType.HOME,
        output_folder="/tmp",
        author="Test",
    )
    document = ProjectDocument(manifest=manifest)
    replay = replay_service.build_replay(document)
    assert not any(s.stage == ReplayStageType.REFERENCE_IMAGES for s in replay.steps)


def test_audit_chain_uses_model_api() -> None:
    manifest = ProjectManifest(
        project_name="Audit",
        club_name="Test FC",
        competition="League",
        season="2025/26",
        kit_type=KitType.HOME,
        output_folder="/tmp",
        author="Test",
    )
    record = ReferenceImageRecord(
        filename="front.png",
        tags=[ImageCategory.FRONT_VIEW.value],
    )
    document = ProjectDocument(
        manifest=manifest,
        reference_manifest=ReferenceImageManifest(images=[record]),
    )
    audit = ProductionAuditService()
    chain_record = audit.build_chain(
        document,
        render_psd_path="/tmp/out.psd",
        render_png_path="/tmp/out.png",
        template_id="T1",
        template_version="1",
    )
    ref_link = next(link for link in chain_record.chain if link.link_type == "Reference Image")
    assert ref_link.details == ImageCategory.FRONT_VIEW.value
    assert ref_link.timestamp == record.import_timestamp()


def test_audit_chain_legacy_view_type() -> None:
    manifest = ProjectManifest(
        project_name="Audit Legacy",
        club_name="Test FC",
        competition="League",
        season="2025/26",
        kit_type=KitType.HOME,
        output_folder="/tmp",
        author="Test",
    )
    legacy = ReferenceImageRecord.model_validate(
        {"filename": "legacy.png", "view_type": "Pattern", "imported_at": "2024-06-01T00:00:00+00:00"}
    )
    document = ProjectDocument(
        manifest=manifest,
        reference_manifest=ReferenceImageManifest(images=[legacy]),
    )
    audit = ProductionAuditService()
    chain_record = audit.build_chain(
        document,
        render_psd_path="/tmp/out.psd",
        render_png_path="/tmp/out.png",
        template_id="T1",
        template_version="1",
    )
    ref_link = next(link for link in chain_record.chain if link.link_type == "Reference Image")
    assert ref_link.details == "Pattern"


@pytest.fixture
def vision_project(tmp_path: Path) -> ProjectDocument:
    from models.vision_analysis import VisionAnalysisArchive, VisionAnalysisResult

    manifest = ProjectManifest(
        project_name="Vision Replay",
        club_name="Coventry City",
        competition="Championship",
        season="2025/26",
        kit_type=KitType.HOME,
        output_folder=str(tmp_path),
        author="Test",
    )
    record = ReferenceImageRecord(
        filename="front.png",
        tags=[ImageCategory.FRONT_VIEW.value],
    )
    analysis = VisionAnalysisResult(image_id=record.image_id)
    return ProjectDocument(
        manifest=manifest,
        reference_manifest=ReferenceImageManifest(images=[record]),
        vision_analyses=VisionAnalysisArchive(analyses=[analysis]),
        template_settings=TemplateProjectSettings(active_template_id="TEMPLATE_BROADCAST_0001"),
        file_path=str(tmp_path / "vision.gjs"),
    )


def test_replay_after_vision_analysis(replay_service: ReplayService, vision_project: ProjectDocument) -> None:
    replay = replay_service.build_replay(vision_project)
    stages = {step.stage for step in replay.steps}
    assert ReplayStageType.REFERENCE_IMAGES in stages
    assert ReplayStageType.VISION_ANALYSIS in stages


def test_replay_panel_refresh_after_vision(qapp, tmp_path: Path, vision_project: ProjectDocument) -> None:  # noqa: ARG001
    from ui.widgets.production_replay_panel import ProductionReplayPanel

    settings = SettingsManager(tmp_path / "settings.json")
    settings.load()
    projects = ProjectsManager(
        RecentProjectsManager(settings),
        settings_manager=settings,
        workspace=WorkspaceService(root=tmp_path / "workspace"),
        application_version="1.0.0-rc.1",
    )
    projects._document = vision_project
    panel = ProductionReplayPanel()
    panel.set_services(projects)
    panel.refresh()
    assert panel._replay is not None
    assert len(panel._replay.steps) >= 2


def test_validation_refresh_after_vision_analysis(
    qapp, tmp_path: Path, vision_project: ProjectDocument  # noqa: ARG001
) -> None:
    from ui.widgets.validation_panel import ValidationPanel

    settings = SettingsManager(tmp_path / "settings.json")
    settings.load()
    projects = ProjectsManager(
        RecentProjectsManager(settings),
        settings_manager=settings,
        workspace=WorkspaceService(root=tmp_path / "workspace"),
        application_version="1.0.0-rc.1",
    )
    projects._document = vision_project
    panel = ValidationPanel()
    panel.set_services(projects)
    panel.set_project(vision_project)
    panel.refresh()


def test_imported_reference_then_replay(
    replay_service: ReplayService,
    tmp_path: Path,
) -> None:
    png = tmp_path / "front.png"
    Image.new("RGB", (400, 400), color=(10, 10, 10)).save(png)
    manifest = ProjectManifest(
        project_name="Import Replay",
        club_name="Test FC",
        competition="League",
        season="2025/26",
        kit_type=KitType.HOME,
        output_folder=str(tmp_path),
        author="Test",
    )
    document = ProjectDocument(manifest=manifest, reference_manifest=ReferenceImageManifest())
    service = ReferenceImageService(WorkspaceService(root=tmp_path / "ws"))
    service.import_files(document, [png], user="Test", tags=[ImageCategory.FRONT_VIEW.value])
    replay = replay_service.build_replay(document)
    ref_step = next(s for s in replay.steps if s.stage == ReplayStageType.REFERENCE_IMAGES)
    assert ref_step.details["images"][0]["categories"] == [ImageCategory.FRONT_VIEW.value]


def test_legacy_template_id_migrated() -> None:
    settings = TemplateProjectSettings.model_validate(
        {"template_id": "TEMPLATE_LEGACY_0001", "template_version": "2.0.0"}
    )
    assert settings.active_template_id == "TEMPLATE_LEGACY_0001"
    assert settings.template_version == "2.0.0"
    assert settings.template_identifier() == "TEMPLATE_LEGACY_0001"


def test_current_template_schema() -> None:
    settings = TemplateProjectSettings(
        active_template_id="TEMPLATE_BROADCAST_0001",
        template_version="1.0.0",
    )
    assert settings.template_identifier() == "TEMPLATE_BROADCAST_0001"
    assert settings.template_version_label() == "1.0.0"
    assert settings.audit_details() == "TEMPLATE_BROADCAST_0001 v1.0.0"


def test_missing_template_metadata_uses_placeholder(replay_service: ReplayService) -> None:
    manifest = ProjectManifest(
        project_name="No Template",
        club_name="Test FC",
        competition="League",
        season="2025/26",
        kit_type=KitType.HOME,
        output_folder="/tmp",
        author="Test",
    )
    document = ProjectDocument(manifest=manifest, template_settings=None)
    replay = replay_service.build_replay(document)
    template_step = next(s for s in replay.steps if s.stage == ReplayStageType.TEMPLATE_SELECTION)
    assert template_step.title == UNKNOWN_TEMPLATE_LABEL


def test_empty_template_id_uses_placeholder() -> None:
    settings = TemplateProjectSettings(active_template_id="")
    assert settings.template_identifier() == UNKNOWN_TEMPLATE_LABEL


def test_replay_template_step_current_schema(replay_service: ReplayService) -> None:
    manifest = ProjectManifest(
        project_name="Template Replay",
        club_name="Test FC",
        competition="League",
        season="2025/26",
        kit_type=KitType.HOME,
        output_folder="/tmp",
        author="Test",
    )
    document = ProjectDocument(
        manifest=manifest,
        template_settings=TemplateProjectSettings(
            active_template_id="TEMPLATE_BROADCAST_0001",
            template_version="1.0.0",
        ),
    )
    replay = replay_service.build_replay(document)
    step = next(s for s in replay.steps if s.stage == ReplayStageType.TEMPLATE_SELECTION)
    assert step.title == "TEMPLATE_BROADCAST_0001"
    assert step.summary == "1.0.0"


def test_audit_uses_template_settings_api() -> None:
    manifest = ProjectManifest(
        project_name="Template Audit",
        club_name="Test FC",
        competition="League",
        season="2025/26",
        kit_type=KitType.HOME,
        output_folder="/tmp",
        author="Test",
    )
    settings = TemplateProjectSettings(
        active_template_id="TEMPLATE_BROADCAST_0001",
        template_version="1.0.0",
    )
    document = ProjectDocument(manifest=manifest, template_settings=settings)
    assert settings.audit_details() == "TEMPLATE_BROADCAST_0001 v1.0.0"
    audit = ProductionAuditService()
    record = audit.build_chain(
        document,
        render_psd_path="/tmp/out.psd",
        render_png_path="/tmp/out.png",
        template_id=settings.template_identifier(),
        template_version=settings.template_version_label(),
    )
    template_link = next(link for link in record.chain if link.link_type == "Template")
    assert template_link.identifier == "TEMPLATE_BROADCAST_0001"
    assert template_link.version == "1.0.0"


def test_vision_analysis_replay_includes_template_without_warning(
    replay_service: ReplayService,
    vision_project: ProjectDocument,
) -> None:
    replay = replay_service.build_replay(vision_project)
    stages = [step.stage for step in replay.steps]
    assert ReplayStageType.VISION_ANALYSIS in stages
    assert ReplayStageType.TEMPLATE_SELECTION in stages
    template_step = next(s for s in replay.steps if s.stage == ReplayStageType.TEMPLATE_SELECTION)
    assert template_step.title == "TEMPLATE_BROADCAST_0001"
