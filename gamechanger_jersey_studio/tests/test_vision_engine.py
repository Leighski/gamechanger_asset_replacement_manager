"""Vision Engine Phase 1 — image analysis foundation tests."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from models.project import KitType, NewProjectRequest, ProjectDocument, ProjectManifest
from models.reference_image import AnalysisStatus, ImageCategory, ReferenceImageManifest
from models.vision_analysis import VisionAnalysisArchive
from services.project_format import read_project_package, write_project_package
from services.projects_manager import ProjectsManager
from services.recent_projects_manager import RecentProjectsManager
from services.reference_image_service import ReferenceImageService
from services.settings_manager import SettingsManager
from services.vision.confidence import (
    clamp_confidence,
    combine_confidences,
    confidence_from_sample_size,
    confidence_from_variance,
)
from services.vision.image_loader import ImageLoader
from services.vision.image_normalisation import ImageNormaliser
from services.vision.colour_analysis import ColourAnalyser
from services.vision.region_detection import RegionDetector
from services.vision.pipeline import VisionEngine
from services.vision.shirt_detection import ShirtDetector
from services.vision.background_removal import BackgroundRemover
from services.vision_analysis_service import VISION_ANALYSES_NAME, VisionAnalysisService
from services.design_specification_service import DesignSpecificationService
from services.workspace_service import WorkspaceService


@pytest.fixture
def workspace(tmp_path: Path) -> WorkspaceService:
    return WorkspaceService(root=tmp_path / "workspace")


@pytest.fixture
def coventry_png(tmp_path: Path) -> Path:
    """Coventry-style sky blue kit with white trim bands."""
    img = Image.new("RGB", (640, 800), color=(245, 245, 245))
    pixels = img.load()
    for y in range(120, 700):
        for x in range(160, 480):
            pixels[x, y] = (105, 179, 231)
    for y in range(680, 720):
        for x in range(160, 480):
            pixels[x, y] = (245, 245, 245)
    for y in range(100, 140):
        for x in range(220, 420):
            pixels[x, y] = (245, 245, 245)
    path = tmp_path / "coventry_home_front.png"
    img.save(path, format="PNG")
    return path


@pytest.fixture
def sample_document() -> ProjectDocument:
    manifest = ProjectManifest(
        project_name="Coventry Vision Test",
        club_name="Coventry City",
        competition="Championship",
        season="2025/26",
        kit_type=KitType.HOME,
        output_folder="/tmp/out",
        author="Leigh",
    )
    return ProjectDocument(
        manifest=manifest,
        reference_manifest=ReferenceImageManifest(),
        vision_analyses=VisionAnalysisArchive(),
    )


@pytest.fixture
def vision_stack(workspace: WorkspaceService) -> tuple[VisionAnalysisService, ReferenceImageService]:
    references = ReferenceImageService(workspace, application_version="1.0.0-alpha.6")
    design = DesignSpecificationService(application_version="1.0.0-alpha.6")
    vision = VisionAnalysisService(references, design, application_version="1.0.0-alpha.6")
    return vision, references


def test_image_loader_exif_and_dimensions(coventry_png: Path) -> None:
    data = coventry_png.read_bytes()
    loaded = ImageLoader().load(data)
    assert loaded.width == 640
    assert loaded.height == 800
    assert loaded.pixels.shape == (800, 640, 3)
    assert loaded.pixels.dtype == np.uint8


def test_normalisation_produces_srgb_working_copy(coventry_png: Path) -> None:
    loaded = ImageLoader().load(coventry_png.read_bytes())
    normalised = ImageNormaliser().normalise(loaded)
    assert normalised.colour_space == "sRGB"
    assert normalised.pixels is not loaded.pixels
    assert normalised.width == loaded.width


def test_confidence_helpers() -> None:
    assert clamp_confidence(150.0) == 100.0
    assert confidence_from_sample_size(0) == 0.0
    assert confidence_from_sample_size(500) >= 95.0
    assert confidence_from_variance(0.0) == 99.0
    combined = combine_confidences(90.0, 88.0, 92.0)
    assert 80.0 <= combined <= 100.0


def test_colour_analysis_returns_six_colours_with_confidence(coventry_png: Path) -> None:
    loaded = ImageLoader().load(coventry_png.read_bytes())
    normalised = ImageNormaliser().normalise(loaded)
    shirt = ShirtDetector().detect(normalised)
    mask = BackgroundRemover().segment(shirt)
    colours = ColourAnalyser().analyse(shirt, mask)
    assert len(colours) == 6
    for colour in colours:
        assert 0.0 <= colour.confidence <= 100.0
        assert colour.channels.hex_value.startswith("#")
        assert len(colour.channels.rgb) == 3
    primary = colours[0]
    assert primary.name == "Primary Colour"
    assert primary.catalogue_match in ("Sky Blue", "White", "Navy", "Red", "Black", "Gold")


def test_region_detection_returns_named_regions(coventry_png: Path) -> None:
    loaded = ImageLoader().load(coventry_png.read_bytes())
    shirt = ShirtDetector().detect(ImageNormaliser().normalise(loaded))
    regions = RegionDetector().detect(shirt)
    names = {region.name for region in regions}
    assert "Collar" in names
    assert "Body" in names
    assert "Trim" in names
    for region in regions:
        assert len(region.points) == 4
        assert 0.0 <= region.confidence <= 100.0


def test_pipeline_full_analysis(coventry_png: Path) -> None:
    result = VisionEngine().analyse_image(
        image_id="img_test",
        image_filename=coventry_png.name,
        image_bytes=coventry_png.read_bytes(),
    )
    assert result.status == AnalysisStatus.COMPLETE
    assert result.shirt_detection is not None
    assert len(result.colours) == 6
    assert result.shapes is not None
    assert result.patterns is not None
    assert result.performance is not None
    assert result.performance.processing_time_ms >= 0
    assert result.confidence_summary
    assert all(0.0 <= value <= 100.0 for value in result.confidence_summary.values())
    assert len(result.suggested_mappings) >= 1


def test_analysis_persistence_in_gjs(
    sample_document: ProjectDocument,
    coventry_png: Path,
    vision_stack: tuple[VisionAnalysisService, ReferenceImageService],
    tmp_path: Path,
) -> None:
    vision, references = vision_stack
    imported = references.import_files(
        sample_document,
        [coventry_png],
        user="Leigh",
        tags=[ImageCategory.FRONT_VIEW.value],
    )
    image_id = imported[0].image_id
    result = vision.analyse_image(sample_document, image_id, user="Leigh")
    sample_document.vision_analyses = vision.archive

    target = tmp_path / "coventry.gjs"
    write_project_package(sample_document, target, reference_blobs=references.byte_store)
    with zipfile.ZipFile(target) as zf:
        assert VISION_ANALYSES_NAME in zf.namelist()
        raw = json.loads(zf.read(VISION_ANALYSES_NAME))
    assert len(raw["analyses"]) == 1
    assert raw["analyses"][0]["analysis_id"] == result.analysis_id

    reloaded, blobs = read_project_package(target)
    assert reloaded.vision_analyses is not None
    assert len(reloaded.vision_analyses.analyses) == 1
    assert blobs


def test_multiple_analyses_per_image_history(
    sample_document: ProjectDocument,
    coventry_png: Path,
    vision_stack: tuple[VisionAnalysisService, ReferenceImageService],
) -> None:
    vision, references = vision_stack
    imported = references.import_files(sample_document, [coventry_png], user="Leigh")
    image_id = imported[0].image_id
    first = vision.analyse_image(sample_document, image_id, user="Leigh")
    second = vision.analyse_image(sample_document, image_id, user="Leigh")
    assert first.analysis_id != second.analysis_id
    assert len(vision.analyses_for_image(image_id)) == 2
    assert vision.latest_for_image(image_id).analysis_id == second.analysis_id


def test_accept_mappings_updates_design_spec_only_after_approval(
    sample_document: ProjectDocument,
    coventry_png: Path,
    vision_stack: tuple[VisionAnalysisService, ReferenceImageService],
) -> None:
    vision, references = vision_stack
    from models.design_specification import DesignSpecification

    sample_document.design_spec = DesignSpecification.from_manifest(sample_document.manifest)
    imported = references.import_files(sample_document, [coventry_png], user="Leigh")
    image_id = imported[0].image_id
    result = vision.analyse_image(sample_document, image_id, user="Leigh")
    original_primary = sample_document.design_spec.primary_colour
    accepted = vision.accept_mappings(
        sample_document,
        result.analysis_id,
        None,
        user="Leigh",
        accept_all=True,
    )
    assert accepted
    assert sample_document.design_spec.primary_colour != original_primary


def test_projects_manager_vision_service(tmp_path: Path, coventry_png: Path) -> None:
    settings = SettingsManager(path=tmp_path / "settings.json")
    settings.load()
    recent = RecentProjectsManager(settings)
    workspace = WorkspaceService(root=tmp_path / "workspace")
    manager = ProjectsManager(recent, workspace=workspace, application_version="1.0.0-alpha.6")
    request = NewProjectRequest(
        project_name="Vision Integration",
        club_name="Coventry City",
        competition="Championship",
        season="2025/26",
        kit_type=KitType.HOME,
        output_folder=str(tmp_path / "out"),
        author="Leigh",
    )
    document = manager.new_project(request)
    refs = manager.reference_image_service
    refs.import_files(document, [coventry_png], user="Leigh")
    image_id = refs.manifest.images[0].image_id
    result = manager.vision_analysis_service.analyse_image(document, image_id, user="Leigh")
    assert result.analysis_id
    manager.save_project()
    path = Path(document.file_path)
    reloaded, _ = read_project_package(path)
    assert reloaded.vision_analyses is not None
    assert len(reloaded.vision_analyses.analyses) == 1
