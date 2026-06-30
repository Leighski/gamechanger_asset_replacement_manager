"""Interpretation Engine tests — AI-assisted Design Specification suggestions."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest
from PIL import Image

from models.interpretation import ConfidenceBand, InterpretationSuggestion, SuggestionStatus, confidence_band
from models.project import KitType, ProjectDocument, ProjectManifest
from models.reference_image import ReferenceImageManifest
from models.vision_analysis import VisionAnalysisArchive
from services.design_specification_service import DesignSpecificationService
from services.interpretation.confidence_evaluation import ConfidenceEvaluationService
from services.interpretation.prompt_builder import PromptBuilder
from services.interpretation.providers.offline import OfflineRuleProvider
from services.interpretation.providers.registry import ProviderRegistry
from services.interpretation.rule_engine import RuleEngine
from services.interpretation_service import INTERPRETATION_RESULTS_NAME, InterpretationService
from services.project_format import read_project_package, write_project_package
from services.projects_manager import ProjectsManager
from services.recent_projects_manager import RecentProjectsManager
from services.reference_image_service import ReferenceImageService
from services.settings_manager import SettingsManager
from services.vision.pipeline import VisionEngine
from services.workspace_service import WorkspaceService


@pytest.fixture
def coventry_png(tmp_path: Path) -> Path:
    img = Image.new("RGB", (640, 800), color=(245, 245, 245))
    pixels = img.load()
    for y in range(120, 700):
        for x in range(160, 480):
            pixels[x, y] = (105, 179, 231)
    path = tmp_path / "coventry_home_front.png"
    img.save(path, format="PNG")
    return path


@pytest.fixture
def vision_result(coventry_png: Path):
    return VisionEngine().analyse_image(
        image_id="coventry_demo",
        image_filename=coventry_png.name,
        image_bytes=coventry_png.read_bytes(),
    )


@pytest.fixture
def sample_document() -> ProjectDocument:
    manifest = ProjectManifest(
        project_name="Coventry Interpretation",
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
def interpretation_stack() -> tuple[InterpretationService, DesignSpecificationService]:
    design = DesignSpecificationService(application_version="1.0.0-alpha.7")
    interpretation = InterpretationService(design, application_version="1.0.0-alpha.7")
    return interpretation, design


def test_confidence_bands() -> None:
    assert confidence_band(96.0) == ConfidenceBand.HIGH
    assert confidence_band(85.0) == ConfidenceBand.MEDIUM
    assert confidence_band(72.0) == ConfidenceBand.LOW
    evaluator = ConfidenceEvaluationService()
    suggestion = evaluator.evaluate(
        InterpretationSuggestion(
            target_field="primary_colour",
            proposed_value="#69B3E7",
            confidence=75.0,
        )
    )
    assert evaluator.default_selected([suggestion]) == []


def test_prompt_generation_contains_measurements_no_images(
    sample_document: ProjectDocument,
    vision_result,
    interpretation_stack: tuple[InterpretationService, DesignSpecificationService],
) -> None:
    _, design = interpretation_stack
    spec = design.ensure_spec(sample_document)
    builder = PromptBuilder()
    prompt = builder.build(vision_result, spec, sample_document.manifest, design.catalogues)
    data = json.loads(prompt)
    assert "vision_measurements" in data
    assert "colours" in data["vision_measurements"]
    assert "image" not in prompt.lower() or "never analyse images" in prompt.lower()
    assert data["rule_suggestions"]


def test_offline_provider_parses_suggestions(
    sample_document: ProjectDocument,
    vision_result,
    interpretation_stack: tuple[InterpretationService, DesignSpecificationService],
) -> None:
    interpretation, design = interpretation_stack
    design.ensure_spec(sample_document)
    result = interpretation.interpret_analysis(sample_document, vision_result, user="Leigh")
    assert result.offline_mode
    assert result.ai_provider == "offline"
    assert len(result.suggestions) >= 1
    for suggestion in result.suggestions:
        assert suggestion.reasoning
        assert suggestion.confidence_band
        assert suggestion.target_field


def test_low_confidence_not_auto_selected(
    sample_document: ProjectDocument,
    vision_result,
    interpretation_stack: tuple[InterpretationService, DesignSpecificationService],
) -> None:
    interpretation, _ = interpretation_stack
    result = interpretation.interpret_analysis(sample_document, vision_result, user="Leigh")
    selected = interpretation.default_selected_ids(result)
    for suggestion in result.suggestions:
        if suggestion.suggestion_id in selected:
            assert suggestion.confidence_band != ConfidenceBand.LOW


def test_acceptance_updates_design_spec(
    sample_document: ProjectDocument,
    vision_result,
    interpretation_stack: tuple[InterpretationService, DesignSpecificationService],
) -> None:
    interpretation, design = interpretation_stack
    spec = design.ensure_spec(sample_document)
    result = interpretation.interpret_analysis(sample_document, vision_result, user="Leigh")
    colour_suggestion = next(s for s in result.suggestions if s.target_field == "primary_colour")
    interpretation.accept_suggestions(
        sample_document,
        result.interpretation_id,
        [colour_suggestion.suggestion_id],
        user="Leigh",
        edited_values={colour_suggestion.suggestion_id: colour_suggestion.proposed_value},
    )
    assert sample_document.design_spec.primary_colour == colour_suggestion.proposed_value
    updated = interpretation.archive.get(result.interpretation_id)
    assert updated is not None
    accepted = next(s for s in updated.suggestions if s.suggestion_id == colour_suggestion.suggestion_id)
    assert accepted.status == SuggestionStatus.ACCEPTED


def test_rejection_records_feedback(
    sample_document: ProjectDocument,
    vision_result,
    interpretation_stack: tuple[InterpretationService, DesignSpecificationService],
) -> None:
    interpretation, design = interpretation_stack
    design.ensure_spec(sample_document)
    result = interpretation.interpret_analysis(sample_document, vision_result, user="Leigh")
    suggestion = result.suggestions[0]
    interpretation.reject_suggestion(
        sample_document,
        result.interpretation_id,
        suggestion.suggestion_id,
        user="Leigh",
    )
    assert len(interpretation.archive.feedback) == 1
    assert interpretation.archive.feedback[0].decision.value == "Rejected"


def test_modified_acceptance(
    sample_document: ProjectDocument,
    vision_result,
    interpretation_stack: tuple[InterpretationService, DesignSpecificationService],
) -> None:
    interpretation, design = interpretation_stack
    design.ensure_spec(sample_document)
    result = interpretation.interpret_analysis(sample_document, vision_result, user="Leigh")
    suggestion = next(s for s in result.suggestions if s.target_field == "primary_colour")
    custom = "#AABBCC"
    interpretation.accept_suggestions(
        sample_document,
        result.interpretation_id,
        [suggestion.suggestion_id],
        user="Leigh",
        edited_values={suggestion.suggestion_id: custom},
    )
    assert sample_document.design_spec.primary_colour == custom
    updated = interpretation.archive.get(result.interpretation_id)
    accepted = next(s for s in updated.suggestions if s.suggestion_id == suggestion.suggestion_id)
    assert accepted.status == SuggestionStatus.MODIFIED


def test_validation_blocks_invalid_catalogue_value(
    sample_document: ProjectDocument,
    vision_result,
    interpretation_stack: tuple[InterpretationService, DesignSpecificationService],
) -> None:
    from services.interpretation_service import InterpretationError

    interpretation, design = interpretation_stack
    design.ensure_spec(sample_document)
    result = interpretation.interpret_analysis(sample_document, vision_result, user="Leigh")
    suggestion = next(s for s in result.suggestions if s.target_field == "collar_style")
    with pytest.raises(InterpretationError):
        interpretation.accept_suggestions(
            sample_document,
            result.interpretation_id,
            [suggestion.suggestion_id],
            user="Leigh",
            edited_values={suggestion.suggestion_id: "invalid-collar-id"},
        )


def test_provider_registry_offline_by_default() -> None:
    registry = ProviderRegistry()
    assert registry.is_offline_mode()
    provider = registry.get_provider()
    assert provider.provider_name == "offline"


def test_interpretation_persistence_in_gjs(
    sample_document: ProjectDocument,
    vision_result,
    interpretation_stack: tuple[InterpretationService, DesignSpecificationService],
    tmp_path: Path,
) -> None:
    interpretation, design = interpretation_stack
    design.ensure_spec(sample_document)
    result = interpretation.interpret_analysis(sample_document, vision_result, user="Leigh")
    sample_document.interpretation_results = interpretation.archive

    target = tmp_path / "coventry.gjs"
    write_project_package(sample_document, target, reference_blobs={})
    with zipfile.ZipFile(target) as zf:
        assert INTERPRETATION_RESULTS_NAME in zf.namelist()
        raw = json.loads(zf.read(INTERPRETATION_RESULTS_NAME))
    assert len(raw["interpretations"]) == 1
    assert raw["interpretations"][0]["interpretation_id"] == result.interpretation_id

    reloaded, _ = read_project_package(target)
    assert reloaded.interpretation_results is not None
    assert len(reloaded.interpretation_results.interpretations) == 1


def test_projects_manager_interpretation_integration(
    tmp_path: Path,
    coventry_png: Path,
    vision_result,
) -> None:
    settings = SettingsManager(path=tmp_path / "settings.json")
    settings.load()
    recent = RecentProjectsManager(settings)
    workspace = WorkspaceService(root=tmp_path / "workspace")
    manager = ProjectsManager(recent, workspace=workspace, application_version="1.0.0-alpha.7")
    from models.project import NewProjectRequest

    document = manager.new_project(
        NewProjectRequest(
            project_name="Interp Test",
            club_name="Coventry City",
            competition="Championship",
            season="2025/26",
            kit_type=KitType.HOME,
            output_folder=str(tmp_path / "out"),
            author="Leigh",
        )
    )
    refs = manager.reference_image_service
    refs.import_files(document, [coventry_png], user="Leigh")
    document.vision_analyses = VisionAnalysisArchive(analyses=[vision_result])
    result = manager.interpretation_service.interpret_analysis(document, vision_result, user="Leigh")
    assert result.suggestions
    manager.save_project()
    reloaded, _ = read_project_package(Path(document.file_path))
    assert reloaded.interpretation_results is not None

def test_rule_engine_validate_proposed_change() -> None:
    from models.design_specification import DesignSpecification
    from services.design_catalogue_service import load_catalogues

    engine = RuleEngine()
    spec = DesignSpecification()
    ok, _ = engine.validate_proposed_change(spec, "primary_colour", "#69B3E7", load_catalogues())
    assert ok
