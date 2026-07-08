"""Regression tests — Vision Analysis → Review UI integration."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from models.design_specification import DesignSpecification
from models.project import KitType, ProjectDocument, ProjectManifest
from models.reference_image import ImageCategory, ReferenceImageManifest
from models.vision_analysis import VisionAnalysisArchive
from services.design_specification_service import DesignSpecificationService
from services.interpretation_service import InterpretationService
from services.reference_image_service import ReferenceImageService
from services.vision_analysis_service import VisionAnalysisService
from services.workspace_service import WorkspaceService
from services.catalogue_manager_service import CatalogueManagerService
from ui.widgets.preview_panel import PreviewPanel
from ui.widgets.vision_analysis_review import VisionAnalysisReviewPanel

pytestmark = pytest.mark.skipif(
    os.environ.get("GJS_SKIP_QT_TESTS") == "1",
    reason="Qt GUI tests disabled",
)


@pytest.fixture
def catalogue_manager() -> CatalogueManagerService:
    manager = CatalogueManagerService()
    manager.load()
    return manager


@pytest.fixture
def workspace(tmp_path: Path) -> WorkspaceService:
    return WorkspaceService(root=tmp_path / "workspace")


@pytest.fixture
def coventry_png(tmp_path: Path) -> Path:
    from PIL import Image

    img = Image.new("RGB", (640, 800), color=(245, 245, 245))
    pixels = img.load()
    for y in range(120, 700):
        for x in range(160, 480):
            pixels[x, y] = (105, 179, 231)
    path = tmp_path / "coventry_home_front.png"
    img.save(path, format="PNG")
    return path


@pytest.fixture
def sample_document() -> ProjectDocument:
    manifest = ProjectManifest(
        project_name="Review Integration Test",
        club_name="Coventry City",
        competition="Championship",
        season="2025/26",
        kit_type=KitType.HOME,
        output_folder="/tmp/out",
        author="Tester",
    )
    return ProjectDocument(
        manifest=manifest,
        reference_manifest=ReferenceImageManifest(),
        vision_analyses=VisionAnalysisArchive(),
        design_spec=DesignSpecification.from_manifest(manifest),
    )


@pytest.fixture
def review_stack(
    workspace: WorkspaceService,
    sample_document: ProjectDocument,
) -> tuple[VisionAnalysisReviewPanel, VisionAnalysisService, ReferenceImageService, ProjectDocument]:
    references = ReferenceImageService(workspace, application_version="1.0.0-rc.1")
    design = DesignSpecificationService(application_version="1.0.0-rc.1")
    vision = VisionAnalysisService(references, design, application_version="1.0.0-rc.1")
    interpretation = InterpretationService(design, application_version="1.0.0-rc.1")
    panel = VisionAnalysisReviewPanel()
    panel.set_services(vision, references, interpretation, design)
    panel.set_project(sample_document)
    return panel, vision, references, sample_document


def test_review_dropdown_empty_before_import(review_stack) -> None:
    panel, _, _, _ = review_stack
    assert panel._image_selector.count() == 0


def test_review_refresh_after_import_populates_dropdown(
    review_stack,
    coventry_png: Path,
) -> None:
    panel, _, references, document = review_stack
    references.import_files(document, [coventry_png], user="Tester", tags=[ImageCategory.FRONT_VIEW.value])
    panel.refresh()
    assert panel._image_selector.count() == 1
    assert panel._image_selector.currentIndex() == 0


def test_vision_analysis_populates_review_screen(
    review_stack,
    coventry_png: Path,
    qapp: QApplication,  # noqa: ARG001
) -> None:
    panel, _, references, document = review_stack
    imported = references.import_files(document, [coventry_png], user="Tester", tags=[ImageCategory.FRONT_VIEW.value])
    image_id = imported[0].image_id
    panel.run_analysis(image_id)

    assert panel._image_selector.count() == 1
    assert panel._current is not None
    assert panel._confidence_table.rowCount() > 0
    assert panel._measurements_table.rowCount() > 0
    assert panel._colour_grid.count() > 0
    assert panel._interpret_btn.isEnabled()
    pixmap = panel._canvas.pixmap()
    assert pixmap is not None and not pixmap.isNull()


def test_auto_select_single_analysed_image(
    review_stack,
    coventry_png: Path,
) -> None:
    panel, vision, references, document = review_stack
    imported = references.import_files(document, [coventry_png], user="Tester")
    image_id = imported[0].image_id
    vision.analyse_image(document, image_id, user="Tester")
    panel.refresh()
    assert panel._image_selector.currentData() == image_id
    assert panel._current is not None


def test_run_analysis_without_prior_refresh_still_loads_review(
    review_stack,
    coventry_png: Path,
) -> None:
    """Simulates analyse-from-reference before visiting Validation."""
    panel, _, references, document = review_stack
    imported = references.import_files(document, [coventry_png], user="Tester")
    image_id = imported[0].image_id
    assert panel._image_selector.count() == 0
    panel.run_analysis(image_id)
    assert panel._image_selector.count() == 1
    assert panel._current is not None
    assert panel._confidence_table.rowCount() > 0


def test_generate_interpretation_enabled_after_analysis(
    review_stack,
    coventry_png: Path,
) -> None:
    panel, _, references, document = review_stack
    imported = references.import_files(document, [coventry_png], user="Tester")
    panel.run_analysis(imported[0].image_id)
    assert panel._interpret_btn.isEnabled()


def test_canvas_repaints_without_hover(
    review_stack,
    coventry_png: Path,
    qapp: QApplication,
) -> None:
    panel, _, references, document = review_stack
    imported = references.import_files(document, [coventry_png], user="Tester")
    panel.show()
    panel.resize(1024, 768)
    qapp.processEvents()
    panel.run_analysis(imported[0].image_id)
    qapp.processEvents()
    pixmap = panel._canvas.pixmap()
    assert pixmap is not None and not pixmap.isNull()


def test_preview_missing_component_shows_field_name(
    catalogue_manager,
    sample_document: ProjectDocument,
    qapp: QApplication,  # noqa: ARG001
) -> None:
    from services.live_renderer_service import LiveRendererService

    renderer = LiveRendererService(catalogue_manager)
    result = renderer.render_document(sample_document)
    assert not result.success
    assert result.error is not None
    assert "material_style" in result.error.lower() or "Material Style" in result.error
    message = PreviewPanel._format_render_error(result.error)
    assert "Design Specification" in message


def test_component_assembler_empty_field_error_names_field(catalogue_manager) -> None:
    from services.rendering.component_assembler import ComponentAssembler
    from services.rendering.errors import RenderingError

    assembler = ComponentAssembler(catalogue_manager)
    with pytest.raises(RenderingError, match="material_style"):
        assembler.load_field_image("material_style", "", (64, 64))
