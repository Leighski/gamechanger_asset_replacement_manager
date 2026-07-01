"""Comprehensive tests for the Production PSD Renderer subsystem."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from core.version import APP_VERSION
from models.design_specification import DesignSpecification, OutputProfile
from models.project import HistoryEventType, KitType, ProjectDocument, ProjectManifest
from models.psd_render import PIPELINE_STAGES, PSDRenderProgress, PSDRenderStage
from models.psd_template import TemplateProjectSettings
from services.catalogue_manager_service import CatalogueManagerService
from services.project_history_service import ProjectHistoryService
from services.psd_rendering.layer_colour_service import LayerColourService
from services.psd_rendering.layer_visibility_service import LayerVisibilityService
from services.psd_rendering.pattern_placement_service import PatternPlacementService
from services.psd_rendering.psd_export_service import PSDExportService
from services.psd_rendering.psd_render_service import PSDRenderService
from services.psd_rendering.psd_render_validator import PSDRenderValidator
from services.psd_rendering.render_queue import PSDRenderQueue
from services.psd_rendering.smart_object_render_service import SmartObjectRenderService
from services.psd_rendering.texture_placement_service import TexturePlacementService
from services.psd_renderer_service import PSDRendererService
from services.rendering.component_assembler import ComponentAssembler
from services.template_engine.manager import TemplateManager
from services.template_manager_service import TemplateManagerService


@pytest.fixture
def catalogue_manager() -> CatalogueManagerService:
    manager = CatalogueManagerService()
    manager.load()
    return manager


@pytest.fixture
def template_manager() -> TemplateManagerService:
    return TemplateManagerService()


@pytest.fixture
def manager(template_manager: TemplateManagerService) -> TemplateManager:
    return template_manager.manager


@pytest.fixture
def psd_renderer(
    template_manager: TemplateManagerService,
    catalogue_manager: CatalogueManagerService,
) -> PSDRenderService:
    return PSDRenderService(template_manager.manager, catalogue_manager)


@pytest.fixture
def coventry_spec() -> DesignSpecification:
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
    )


@pytest.fixture
def coventry_document(coventry_spec: DesignSpecification, tmp_path: Path) -> ProjectDocument:
    manifest = ProjectManifest(
        project_name="Coventry City Home 2026",
        club_name="Coventry City",
        competition="Championship",
        season="2025/26",
        kit_type=KitType.HOME,
        output_folder=str(tmp_path),
        author="Test",
    )
    return ProjectDocument(
        manifest=manifest,
        design_spec=coventry_spec,
        template_settings=TemplateProjectSettings(active_template_id="TEMPLATE_BROADCAST_0001"),
    )


def test_open_template_psd_through_engine(manager: TemplateManager) -> None:
    path = manager.open_template_psd("TEMPLATE_BROADCAST_0001")
    assert path.is_file()
    assert path.name == "gamechanger_broadcast_v1.psd"


def test_validator_skips_colour_fields_for_catalogue_lookup(
    manager: TemplateManager,
    catalogue_manager: CatalogueManagerService,
    coventry_spec: DesignSpecification,
) -> None:
    mappings = manager.publish_mappings("TEMPLATE_BROADCAST_0001")
    assert mappings is not None
    from psd_tools import PSDImage

    psd = PSDImage.open(manager.open_template_psd("TEMPLATE_BROADCAST_0001"))
    layer_index = {str(layer.name): layer for layer in psd.descendants()}
    assembler = ComponentAssembler(catalogue_manager)
    issues = PSDRenderValidator().validate(coventry_spec, mappings, assembler, layer_index)
    component_errors = [issue for issue in issues if issue.code == "component_not_found"]
    assert not component_errors


def test_validator_fails_missing_colour(
    manager: TemplateManager,
    catalogue_manager: CatalogueManagerService,
) -> None:
    mappings = manager.publish_mappings("TEMPLATE_BROADCAST_0001")
    assert mappings is not None
    spec = DesignSpecification(
        club="Test",
        primary_colour="",
        secondary_colour="#FFFFFF",
        sleeve_colour="#FFFFFF",
        collar_colour="#FFFFFF",
        trim_colour="#1C1C1C",
    )
    from psd_tools import PSDImage

    psd = PSDImage.open(manager.open_template_psd("TEMPLATE_BROADCAST_0001"))
    layer_index = {str(layer.name): layer for layer in psd.descendants()}
    issues = PSDRenderValidator().validate(spec, mappings, ComponentAssembler(catalogue_manager), layer_index)
    assert PSDRenderValidator.has_errors(issues)
    assert any(issue.code == "missing_colour" for issue in issues)


def test_validator_fails_missing_mapped_layer(
    manager: TemplateManager,
    catalogue_manager: CatalogueManagerService,
    coventry_spec: DesignSpecification,
) -> None:
    mappings = manager.publish_mappings("TEMPLATE_BROADCAST_0001")
    assert mappings is not None
    issues = PSDRenderValidator().validate(
        coventry_spec, mappings, ComponentAssembler(catalogue_manager), {}
    )
    assert any(issue.code == "mapped_layer_missing" for issue in issues)


def test_layer_colour_service_tints_pixels() -> None:
    service = LayerColourService()
    image = Image.new("RGBA", (10, 10), (200, 200, 200, 255))
    tinted = service.tint_image(image, "#FF0000")
    pixel = tinted.getpixel((5, 5))
    assert pixel[0] > pixel[2]


def test_pattern_placement_service_applies_scale_rotation_opacity() -> None:
    service = PatternPlacementService()
    pattern = Image.new("RGBA", (40, 40), (255, 255, 255, 255))
    result = service.build_pattern_image(
        pattern,
        hex_colour="#69B3E7",
        scale=0.5,
        rotation_degrees=45.0,
        opacity=0.5,
        canvas_size=(200, 250),
    )
    assert result.size == (200, 250)
    assert result.mode == "RGBA"


def test_texture_placement_service_blends_texture() -> None:
    service = TexturePlacementService()
    base = Image.new("RGBA", (50, 50), (100, 100, 100, 255))
    texture = Image.new("RGBA", (50, 50), (200, 200, 200, 128))
    result = service.apply_texture(base, texture)
    assert result.size == base.size
    assert result.getpixel((25, 25))[3] > 0


def test_smart_object_replace_layer_content() -> None:
    service = SmartObjectRenderService()
    replacement = Image.new("RGBA", (20, 20), (0, 128, 255, 255))

    class FakeLayer:
        def __init__(self) -> None:
            self.numpy = np.zeros((20, 20, 4), dtype=np.uint8)

    layer = FakeLayer()
    assert service.replace_layer_content(layer, replacement)
    assert layer.numpy[10, 10, 2] > layer.numpy[10, 10, 0]


def test_layer_visibility_service_hides_unmapped_variants(
    manager: TemplateManager,
    coventry_spec: DesignSpecification,
) -> None:
    mappings = manager.publish_mappings("TEMPLATE_BROADCAST_0001")
    assert mappings is not None
    from psd_tools import PSDImage

    psd = PSDImage.open(manager.open_template_psd("TEMPLATE_BROADCAST_0001"))
    visibility_path = manager.root / "broadcast_v1" / "layer_visibility.json"
    service = LayerVisibilityService()
    rules = service.load_rules(visibility_path)
    toggled = service.apply_visibility(psd, mappings, coventry_spec, visibility_rules=rules)
    assert any(entry.startswith("show:") for entry in toggled)


def test_export_service_writes_outputs(tmp_path: Path, manager: TemplateManager) -> None:
    from psd_tools import PSDImage
    from models.psd_render import PSDRenderLog, PSDRenderStageLog

    export = PSDExportService()
    output_dir = export.build_output_dir(str(tmp_path), "Export Test")
    psd = PSDImage.open(manager.open_template_psd("TEMPLATE_BROADCAST_0001"))
    psd_path = output_dir / "test_render.psd"
    png_path = output_dir / "test_preview.png"
    log_path = output_dir / "render_log.json"
    export.save_psd(psd, psd_path)
    export.save_png_preview(psd, png_path)
    log = PSDRenderLog(project_name="Export Test", success=True)
    log.stages.append(PSDRenderStageLog(stage=PSDRenderStage.SAVE, duration_ms=1.0))
    export.save_render_log(log, log_path)
    assert psd_path.is_file()
    assert png_path.is_file()
    assert json.loads(log_path.read_text(encoding="utf-8"))["success"] is True


def test_full_pipeline_render(
    psd_renderer: PSDRenderService,
    manager: TemplateManager,
    coventry_spec: DesignSpecification,
    tmp_path: Path,
) -> None:
    mappings = manager.publish_mappings("TEMPLATE_BROADCAST_0001")
    assert mappings is not None
    result = psd_renderer.render(
        coventry_spec,
        mappings,
        project_name="Coventry_Test",
        output_folder=str(tmp_path),
    )
    assert result.success, result.error
    assert Path(result.psd_path).is_file()
    assert Path(result.png_path).is_file()
    assert Path(result.log_path).is_file()
    assert len(result.log.stages) == len(PIPELINE_STAGES)
    assert result.log.colours_applied["primary_colour"] == "#69B3E7"
    assert result.log.patterns_applied
    assert result.log.textures_applied


def test_render_aborts_on_validation_failure(
    psd_renderer: PSDRenderService,
    manager: TemplateManager,
    tmp_path: Path,
) -> None:
    mappings = manager.publish_mappings("TEMPLATE_BROADCAST_0001")
    assert mappings is not None
    bad_spec = DesignSpecification(club="Bad", primary_colour="")
    result = psd_renderer.render(
        bad_spec,
        mappings,
        project_name="Bad",
        output_folder=str(tmp_path),
    )
    assert not result.success
    assert result.log.errors


def test_progress_callback_receives_stage_updates(
    psd_renderer: PSDRenderService,
    manager: TemplateManager,
    coventry_spec: DesignSpecification,
    tmp_path: Path,
) -> None:
    mappings = manager.publish_mappings("TEMPLATE_BROADCAST_0001")
    assert mappings is not None
    updates: list[PSDRenderProgress] = []

    def on_progress(progress: PSDRenderProgress) -> None:
        updates.append(progress.model_copy(deep=True))

    result = psd_renderer.render(
        coventry_spec,
        mappings,
        project_name="Progress",
        output_folder=str(tmp_path),
        progress_callback=on_progress,
    )
    assert result.success
    assert updates
    assert updates[0].current_stage == PSDRenderStage.OPEN_PSD
    assert updates[-1].current_stage == PSDRenderStage.SAVE


def test_render_queue_processes_sequentially(coventry_document: ProjectDocument) -> None:
    queue = PSDRenderQueue()
    second = coventry_document.model_copy(deep=True)
    second.manifest.project_name = "Second Project"
    job1 = queue.enqueue(coventry_document)
    job2 = queue.enqueue(second)
    assert queue.size == 2
    first = queue.dequeue()
    assert first is not None
    assert first.project_name == "Coventry City Home 2026"
    assert queue.dequeue() is not None
    assert queue.dequeue() is None


def test_psd_renderer_records_history(
    template_manager: TemplateManagerService,
    catalogue_manager: CatalogueManagerService,
    coventry_document: ProjectDocument,
) -> None:
    history = ProjectHistoryService()
    renderer = PSDRendererService(
        template_manager,
        catalogue_manager,
        history,
        application_version=APP_VERSION,
    )
    result = renderer.render_document(coventry_document, user="Test")
    assert result.success
    events = [entry.event for entry in coventry_document.history.entries]
    assert HistoryEventType.RENDER_STARTED in events
    assert HistoryEventType.RENDER_COMPLETED in events
    assert HistoryEventType.PSD_SAVED in events
    assert HistoryEventType.PNG_GENERATED in events


def test_psd_renderer_queue_integration(
    template_manager: TemplateManagerService,
    catalogue_manager: CatalogueManagerService,
    coventry_document: ProjectDocument,
) -> None:
    history = ProjectHistoryService()
    renderer = PSDRendererService(
        template_manager,
        catalogue_manager,
        history,
        application_version=APP_VERSION,
    )
    renderer.queue.enqueue(coventry_document)
    results = renderer.process_queue(user="Test")
    assert len(results) == 1
    assert results[0].success
