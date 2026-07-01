"""Tests for the PSD Template Engine."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest
from PIL import Image

from models.project import KitType, ProjectDocument, ProjectManifest
from models.psd_template import LayerMappingSet, PSDTemplate, TemplateProjectSettings, TemplateStatus
from services.project_format import read_project_package, write_project_package
from services.template_engine.anchor_points import AnchorPointService
from services.template_engine.layer_mapping import LayerMappingService
from services.template_engine.manager import TemplateManager
from services.template_engine.smart_objects import SmartObjectService
from services.template_engine.validator import TemplateValidator
from services.template_manager_service import TEMPLATE_SETTINGS_NAME, TemplateManagerService


@pytest.fixture
def template_manager() -> TemplateManagerService:
    return TemplateManagerService()


@pytest.fixture
def manager() -> TemplateManager:
    service = TemplateManagerService()
    return service.manager


def test_template_registry_loads_broadcast_template(manager: TemplateManager) -> None:
    templates = manager.list_templates()
    assert len(templates) >= 1
    template = manager.get_template("TEMPLATE_BROADCAST_0001")
    assert template is not None
    assert template.name == "Gamechanger Broadcast v1"
    assert template.status == TemplateStatus.CERTIFIED


def test_analysis_loaded_from_config(manager: TemplateManager) -> None:
    analysis = manager.analysis("TEMPLATE_BROADCAST_0001")
    assert analysis is not None
    assert analysis.layer_count == 11
    assert analysis.smart_object_count == 2
    assert analysis.canvas_width == 2400


def test_layer_mappings_configurable(manager: TemplateManager) -> None:
    mappings = manager.mappings("TEMPLATE_BROADCAST_0001")
    assert mappings is not None
    primary = mappings.for_field("primary_colour")
    assert len(primary) == 1
    assert primary[0].psd_layer_name == "Base Shirt"


def test_anchor_points_loaded(manager: TemplateManager) -> None:
    anchors = manager.anchors("TEMPLATE_BROADCAST_0001")
    assert anchors is not None
    roles = {anchor.role for anchor in anchors.anchors}
    assert "collar" in roles
    assert "badge" in roles
    assert "number" in roles


def test_smart_object_index(manager: TemplateManager) -> None:
    analysis = manager.analysis("TEMPLATE_BROADCAST_0001")
    assert analysis is not None
    service = SmartObjectService()
    records = service.index(analysis)
    assert len(records) == 2
    collar = service.find_by_name(analysis, "Collar Smart Object")
    assert collar is not None
    assert collar.smart_object_id == "SO0001"


def test_template_validation_passes(manager: TemplateManager) -> None:
    report = manager.validation("TEMPLATE_BROADCAST_0001")
    assert report is not None
    assert report.valid
    assert report.mapping_count >= 8


def test_publish_mappings(manager: TemplateManager) -> None:
    published = manager.publish_mappings("TEMPLATE_BROADCAST_0001")
    assert published is not None
    assert published.template_id == "TEMPLATE_BROADCAST_0001"
    assert len(published.mappings) >= 8
    assert len(published.anchors) == 8


def test_layer_mapping_service_round_trip(tmp_path: Path) -> None:
    service = LayerMappingService()
    mapping_set = LayerMappingSet(
        template_id="TEST",
        mappings=[],
    )
    path = tmp_path / "layer_mappings.json"
    service.save(mapping_set, path)
    loaded = service.load(path)
    assert loaded.template_id == "TEST"


def test_anchor_service_required_roles(manager: TemplateManager) -> None:
    anchors = manager.anchors("TEMPLATE_BROADCAST_0001")
    assert anchors is not None
    missing = AnchorPointService().validate_required(anchors, ["collar", "badge", "missing_role"])
    assert "missing_role" in missing
    assert "collar" not in missing


def test_psd_loader_analyses_minimal_psd(tmp_path: Path) -> None:
    from services.template_engine.psd_loader import PSDTemplateLoader

    try:
        from psd_tools import PSDImage
        from psd_tools.api.layers import PixelLayer
    except ImportError:
        pytest.skip("psd-tools not available")

    psd = PSDImage.new(mode="RGB", size=(100, 120))
    layer = PixelLayer.frompil(Image.new("RGBA", (100, 120), (255, 0, 0, 255)), psd)
    layer.name = "Base Shirt"
    psd.append(layer)
    path = tmp_path / "mini.psd"
    psd.save(path)

    loader = PSDTemplateLoader()
    report = loader.analyse("TEST_TEMPLATE", path)
    assert report.layer_count >= 1
    assert report.canvas_width == 100


def test_project_template_settings_persist(tmp_path: Path) -> None:
    manifest = ProjectManifest(
        project_name="Template Test",
        club_name="Coventry City",
        competition="Championship",
        season="2025/26",
        kit_type=KitType.HOME,
        output_folder=str(tmp_path),
        author="Test",
    )
    document = ProjectDocument(
        manifest=manifest,
        template_settings=TemplateProjectSettings(active_template_id="TEMPLATE_BROADCAST_0001"),
    )
    target = tmp_path / "template_test.gjs"
    write_project_package(document, target)
    reloaded, _ = read_project_package(target)
    assert reloaded.template_settings is not None
    assert reloaded.template_settings.active_template_id == "TEMPLATE_BROADCAST_0001"
    with zipfile.ZipFile(target) as zf:
        assert TEMPLATE_SETTINGS_NAME in zf.namelist()


def test_template_manager_service_active_template(template_manager: TemplateManagerService) -> None:
    manifest = ProjectManifest(
        project_name="Template Test",
        club_name="Coventry City",
        competition="Championship",
        season="2025/26",
        kit_type=KitType.HOME,
        output_folder="/tmp",
        author="Test",
    )
    document = ProjectDocument(manifest=manifest)
    template_id = template_manager.active_template_id(document)
    assert template_id == "TEMPLATE_BROADCAST_0001"
    published = template_manager.published_mappings(document)
    assert published is not None
    assert published.template_id == "TEMPLATE_BROADCAST_0001"


def test_validator_flags_missing_layer(manager: TemplateManager) -> None:
    template = manager.get_template("TEMPLATE_BROADCAST_0001")
    analysis = manager.analysis("TEMPLATE_BROADCAST_0001")
    mappings = manager.mappings("TEMPLATE_BROADCAST_0001")
    anchors = manager.anchors("TEMPLATE_BROADCAST_0001")
    assert template and analysis and mappings and anchors
    bad_mappings = mappings.model_copy(deep=True)
    bad_mappings.mappings[0].psd_layer_name = "Nonexistent Layer XYZ"
    report = TemplateValidator().validate(template, analysis, bad_mappings, anchors)
    assert not report.valid
    assert any(issue.code == "required_layer_missing" for issue in report.issues)
