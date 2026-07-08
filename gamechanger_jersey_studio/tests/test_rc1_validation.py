"""Comprehensive tests for RC1 production validation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image

from models.design_specification import DesignSpecification, OutputProfile
from models.learning import (
    LearningRule,
    LearningRuleCategory,
    LearningRuleStatus,
    RecommendedAction,
    TriggerConditions,
)
from models.project import HistoryEventType, KitType, ProjectDocument, ProjectHistory, ProjectHistoryEntry, ProjectManifest
from models.validation import (
    AccuracyCategory,
    BenchmarkLibrary,
    BenchmarkProject,
    ReplayStageType,
    ReleaseRecommendation,
    StressTestScenario,
)
from services.learning.knowledge_base_service import KnowledgeBaseService
from services.learning_manager_service import LearningManagerService
from services.production.accuracy_service import AccuracyService
from services.production.batch_validation_service import BatchValidationService
from services.production.benchmark_service import BenchmarkService
from services.production.comparison_service import ComparisonService
from services.production.kb_validation_service import KnowledgeBaseValidationService
from services.production.readiness_service import ReadinessService
from services.production.replay_service import ReplayService
from services.production.stress_test_service import StressTestService
from services.production_manager_service import ProductionManagerService
from services.settings_manager import SettingsManager
from services.template_manager_service import TemplateManagerService


@pytest.fixture
def settings_manager(tmp_path: Path) -> SettingsManager:
    manager = SettingsManager(tmp_path / "settings.json")
    manager.load()
    return manager


@pytest.fixture
def production_manager(settings_manager: SettingsManager) -> ProductionManagerService:
    return ProductionManagerService(settings_manager, TemplateManagerService())


@pytest.fixture
def sample_spec() -> DesignSpecification:
    return DesignSpecification(
        club="Coventry City",
        competition="Championship",
        season="2025/26",
        primary_colour="#69B3E7",
        secondary_colour="#FFFFFF",
        collar_style="v-neck",
        pattern="hoops",
        sleeve_style="short",
        trim_style="TRIM_0001",
        output_profile=OutputProfile.GAMECHANGER_BROADCAST,
    )


@pytest.fixture
def sample_document(tmp_path: Path, sample_spec: DesignSpecification) -> ProjectDocument:
    manifest = ProjectManifest(
        project_name="Coventry Home",
        club_name="Coventry City",
        competition="Championship",
        season="2025/26",
        kit_type=KitType.HOME,
        output_folder=str(tmp_path),
        author="Test",
    )
    return ProjectDocument(manifest=manifest, design_spec=sample_spec, file_path=str(tmp_path / "test.gjs"))


def _make_png(path: Path, color: tuple[int, int, int]) -> None:
    Image.new("RGB", (64, 64), color).save(path)


# --- AccuracyService ---


def test_accuracy_perfect_match(sample_spec: DesignSpecification) -> None:
    report = AccuracyService().score(sample_spec, sample_spec, project_name="Test")
    assert report.overall.score == 100.0
    assert report.overall.confidence > 0


def test_accuracy_colour_mismatch(sample_spec: DesignSpecification) -> None:
    generated = DesignSpecification.model_validate(sample_spec.model_dump())
    generated.primary_colour = "#000000"
    report = AccuracyService().score(sample_spec, generated)
    colour = next(c for c in report.categories if c.category == AccuracyCategory.COLOUR)
    assert colour.score < 100.0
    assert colour.confidence < 100.0


def test_accuracy_pattern_category(sample_spec: DesignSpecification) -> None:
    generated = DesignSpecification.model_validate(sample_spec.model_dump())
    generated.pattern = "stripes"
    report = AccuracyService().score(sample_spec, generated)
    pattern = next(c for c in report.categories if c.category == AccuracyCategory.PATTERN)
    assert pattern.matched_fields < pattern.total_fields


def test_accuracy_collar_category(sample_spec: DesignSpecification) -> None:
    generated = DesignSpecification.model_validate(sample_spec.model_dump())
    generated.collar_style = "crew"
    report = AccuracyService().score(sample_spec, generated)
    collar = next(c for c in report.categories if c.category == AccuracyCategory.COLLAR)
    assert collar.score == 50.0


def test_accuracy_trim_category(sample_spec: DesignSpecification) -> None:
    generated = DesignSpecification.model_validate(sample_spec.model_dump())
    generated.trim_style = ""
    report = AccuracyService().score(sample_spec, generated)
    trim = next(c for c in report.categories if c.category == AccuracyCategory.TRIM)
    assert trim.score < 100.0


def test_accuracy_sleeve_category(sample_spec: DesignSpecification) -> None:
    generated = DesignSpecification.model_validate(sample_spec.model_dump())
    generated.sleeve_style = "long"
    report = AccuracyService().score(sample_spec, generated)
    sleeve = next(c for c in report.categories if c.category == AccuracyCategory.SLEEVE)
    assert sleeve.score < 100.0


def test_accuracy_template_category(sample_spec: DesignSpecification) -> None:
    generated = DesignSpecification.model_validate(sample_spec.model_dump())
    generated.output_profile = OutputProfile.AUTHENTIC
    report = AccuracyService().score(sample_spec, generated)
    template = next(c for c in report.categories if c.category == AccuracyCategory.TEMPLATE)
    assert template.score == 0.0


def test_accuracy_overall_is_average(sample_spec: DesignSpecification) -> None:
    generated = DesignSpecification.model_validate(sample_spec.model_dump())
    generated.collar_style = "crew"
    report = AccuracyService().score(sample_spec, generated)
    assert report.overall.category == AccuracyCategory.OVERALL


def test_detect_missing_components() -> None:
    spec = DesignSpecification()
    missing = AccuracyService().detect_missing_components(spec)
    assert "Collar component" in missing
    assert "Pattern component" in missing


def test_float_field_tolerance(sample_spec: DesignSpecification) -> None:
    generated = DesignSpecification.model_validate(sample_spec.model_dump())
    generated.pattern_scale = sample_spec.pattern_scale + 0.005
    report = AccuracyService().score(sample_spec, generated)
    pattern = next(c for c in report.categories if c.category == AccuracyCategory.PATTERN)
    assert pattern.score == 100.0


# --- ComparisonService ---


def test_pixel_comparison_identical(tmp_path: Path) -> None:
    a = tmp_path / "a.png"
    b = tmp_path / "b.png"
    _make_png(a, (255, 0, 0))
    _make_png(b, (255, 0, 0))
    result = ComparisonService().compare_images(a, b)
    assert result.accuracy_percent == 100.0
    assert result.total_pixels == 64 * 64


def test_pixel_comparison_different(tmp_path: Path) -> None:
    a = tmp_path / "a.png"
    b = tmp_path / "b.png"
    _make_png(a, (255, 0, 0))
    _make_png(b, (0, 0, 255))
    result = ComparisonService().compare_images(a, b)
    assert result.accuracy_percent == 0.0


def test_pixel_diff_overlay_created(tmp_path: Path) -> None:
    a = tmp_path / "a.png"
    b = tmp_path / "b.png"
    diff = tmp_path / "diff.png"
    _make_png(a, (255, 0, 0))
    _make_png(b, (0, 255, 0))
    result = ComparisonService().compare_images(a, b, diff_output_path=diff)
    assert result.diff_overlay_path
    assert diff.is_file()


def test_visual_comparison_result(tmp_path: Path) -> None:
    a = tmp_path / "a.png"
    b = tmp_path / "b.png"
    _make_png(a, (10, 10, 10))
    _make_png(b, (10, 10, 10))
    visual = ComparisonService().build_visual_comparison(str(a), str(b))
    assert visual.before_path == str(a)
    assert visual.pixel is not None


def test_compare_missing_files() -> None:
    result = ComparisonService().compare_images("/nonexistent/a.png", "/nonexistent/b.png")
    assert result.total_pixels == 0


def test_psd_layer_comparison_missing() -> None:
    layers = ComparisonService().compare_psd_layers("/none.psd", "/none.psd")
    assert layers == []


# --- ReplayService ---


def test_replay_empty_document(sample_document: ProjectDocument) -> None:
    replay = ReplayService().build_replay(sample_document)
    assert replay.project_name == "Coventry Home"
    assert any(s.stage == ReplayStageType.DESIGN_SPECIFICATION for s in replay.steps)


def test_replay_step_forward_backward(sample_document: ProjectDocument) -> None:
    service = ReplayService()
    replay = service.build_replay(sample_document)
    if len(replay.steps) < 2:
        replay.steps.append(replay.steps[0])
        replay.steps[1].step_index = 1
    replay = service.step_forward(replay)
    assert replay.current_step == 1
    replay = service.step_backward(replay)
    assert replay.current_step == 0


def test_replay_current_step(sample_document: ProjectDocument) -> None:
    service = ReplayService()
    replay = service.build_replay(sample_document)
    step = service.current_step(replay)
    assert step is not None


def test_replay_includes_history_render(sample_document: ProjectDocument) -> None:
    sample_document.history = ProjectHistory(
        entries=[
            ProjectHistoryEntry.create(
                HistoryEventType.RENDER_COMPLETED,
                application_version="1.0.0-rc.1",
                user="Test",
                details='{"psd": "out.psd"}',
            )
        ]
    )
    replay = ReplayService().build_replay(sample_document)
    assert any(s.stage == ReplayStageType.PSD_RENDERING for s in replay.steps)


# --- BenchmarkService ---


def test_benchmark_load_empty(tmp_path: Path) -> None:
    svc = BenchmarkService(tmp_path / "bench.json")
    library = svc.load()
    assert library.projects == []


def test_benchmark_add_and_save(tmp_path: Path, sample_spec: DesignSpecification) -> None:
    path = tmp_path / "bench.json"
    svc = BenchmarkService(path)
    svc.load()
    project = BenchmarkProject(project_name="Test", club="Coventry City", expected_spec=sample_spec)
    svc.add_project(project)
    svc.save()
    assert path.is_file()
    reloaded = BenchmarkService(path).load()
    assert len(reloaded.projects) == 1


def test_benchmark_remove(tmp_path: Path) -> None:
    svc = BenchmarkService(tmp_path / "bench.json")
    svc.load()
    project = BenchmarkProject(project_name="X", club="Y")
    svc.add_project(project)
    assert svc.remove_project(project.benchmark_id)


def test_benchmark_import_export(tmp_path: Path, sample_spec: DesignSpecification) -> None:
    path = tmp_path / "bench.json"
    svc = BenchmarkService(path)
    svc.load()
    svc.add_project(BenchmarkProject(project_name="A", club="B", expected_spec=sample_spec))
    export = tmp_path / "export.json"
    svc.export_library(export)
    svc2 = BenchmarkService(tmp_path / "bench2.json")
    svc2.load()
    svc2.import_library(export)
    assert len(svc2.library.projects) == 1


# --- BatchValidationService ---


def test_batch_validate_library(sample_spec: DesignSpecification) -> None:
    expected = sample_spec
    generated = DesignSpecification.model_validate(sample_spec.model_dump())
    generated.collar_style = "crew"
    library = BenchmarkLibrary(
        projects=[
            BenchmarkProject(
                project_name="A",
                expected_spec=expected,
                generated_spec=generated,
            )
        ]
    )
    summary = BatchValidationService().validate_library(library)
    assert summary.project_count == 1
    assert summary.mean_accuracy < 100.0


def test_batch_validation_median(tmp_path: Path, sample_spec: DesignSpecification) -> None:
    projects = []
    for i in range(3):
        gen = DesignSpecification.model_validate(sample_spec.model_dump())
        if i:
            gen.pattern = "stripes"
        projects.append(
            BenchmarkProject(project_name=f"P{i}", expected_spec=sample_spec, generated_spec=gen)
        )
    summary = BatchValidationService().validate_library(BenchmarkLibrary(projects=projects))
    assert summary.median_accuracy > 0


def test_batch_validation_save(tmp_path: Path, sample_spec: DesignSpecification) -> None:
    library = BenchmarkLibrary(
        projects=[BenchmarkProject(project_name="T", expected_spec=sample_spec, generated_spec=sample_spec)]
    )
    summary = BatchValidationService().validate_library(library)
    path = BatchValidationService().save_summary(summary, tmp_path / "summary.json")
    assert path.is_file()


def test_batch_most_corrected_fields(sample_spec: DesignSpecification) -> None:
    gen = DesignSpecification.model_validate(sample_spec.model_dump())
    gen.collar_style = "crew"
    gen.pattern = "stripes"
    library = BenchmarkLibrary(
        projects=[BenchmarkProject(project_name="T", expected_spec=sample_spec, generated_spec=gen)]
    )
    summary = BatchValidationService().validate_library(library)
    assert len(summary.most_corrected_fields) >= 1


# --- KnowledgeBaseValidationService ---


@pytest.fixture
def kb_service(tmp_path: Path) -> KnowledgeBaseService:
    kb = KnowledgeBaseService(tmp_path / "kb.json")
    kb.load()
    return kb


def test_kb_never_triggered_rules(kb_service: KnowledgeBaseService) -> None:
    kb_service.knowledge.rules.append(
        LearningRule(
            rule_id="LR_NEVER",
            title="Never used",
            triggers=TriggerConditions(),
            action=RecommendedAction(target_field="collar_style", recommended_value="v-neck"),
            status=LearningRuleStatus.APPROVED,
            created_by="Test",
        )
    )
    report = KnowledgeBaseValidationService(kb_service).analyse()
    assert "LR_NEVER" in report.never_triggered_rules


def test_kb_most_effective_rules(kb_service: KnowledgeBaseService) -> None:
    kb_service.knowledge.rules.append(
        LearningRule(
            rule_id="LR_GOOD",
            title="Good rule",
            triggers=TriggerConditions(),
            action=RecommendedAction(target_field="pattern", recommended_value="hoops"),
            status=LearningRuleStatus.APPROVED,
            usage_count=10,
            accepted_count=8,
            created_by="Test",
        )
    )
    report = KnowledgeBaseValidationService(kb_service).analyse()
    assert len(report.most_effective_rules) == 1


def test_kb_suggested_merges(kb_service: KnowledgeBaseService) -> None:
    for i in range(2):
        kb_service.knowledge.rules.append(
            LearningRule(
                rule_id=f"LR_{i}",
                title=f"Rule {i}",
                triggers=TriggerConditions(club="Coventry City", field_name="collar_style"),
                action=RecommendedAction(target_field="collar_style", recommended_value="v-neck"),
                status=LearningRuleStatus.APPROVED,
                created_by="Test",
            )
        )
    report = KnowledgeBaseValidationService(kb_service).analyse()
    assert len(report.suggested_merges) >= 1


def test_kb_does_not_modify_rules(kb_service: KnowledgeBaseService) -> None:
    rule = LearningRule(
        title="Immutable",
        triggers=TriggerConditions(),
        action=RecommendedAction(target_field="trim_style", recommended_value="x"),
        status=LearningRuleStatus.APPROVED,
        created_by="Test",
    )
    kb_service.knowledge.rules.append(rule)
    before = len(kb_service.knowledge.rules)
    KnowledgeBaseValidationService(kb_service).analyse()
    assert len(kb_service.knowledge.rules) == before


# --- StressTestService ---


def test_stress_consecutive_renders() -> None:
    result = StressTestService().run_consecutive_renders(lambda: None, count=10)
    assert result.scenario == StressTestScenario.CONSECUTIVE_RENDERS
    assert result.success_count == 10


def test_stress_lightweight_suite() -> None:
    report = StressTestService().run_lightweight_suite()
    assert len(report.scenarios) >= 4
    assert report.all_consistent


def test_stress_failure_counted() -> None:
    count = {"n": 0}

    def fail_twice() -> None:
        count["n"] += 1
        if count["n"] <= 2:
            raise RuntimeError("fail")

    result = StressTestService().run_consecutive_renders(fail_twice, count=5)
    assert result.failure_count == 2


# --- ReadinessService ---


def test_readiness_ready_when_clean() -> None:
    report = ReadinessService().generate(test_total=200, test_passed=200)
    assert report.recommendation == ReleaseRecommendation.READY


def test_readiness_not_ready_on_test_failures() -> None:
    report = ReadinessService().generate(test_total=200, test_passed=195)
    assert report.recommendation == ReleaseRecommendation.NOT_READY


def test_readiness_conditional_on_low_accuracy(sample_spec: DesignSpecification) -> None:
    from models.validation import BatchValidationSummary

    batch = BatchValidationSummary(mean_accuracy=75.0, project_count=5)
    report = ReadinessService().generate(test_total=200, test_passed=200, batch_summary=batch)
    assert report.recommendation == ReleaseRecommendation.CONDITIONAL


def test_readiness_save(tmp_path: Path) -> None:
    report = ReadinessService().generate(test_total=10, test_passed=10)
    path = ReadinessService().save(report, tmp_path / "readiness.json")
    data = json.loads(path.read_text())
    assert "test_summary" in data


# --- ProductionManagerService integration ---


def test_production_manager_has_validation_services(production_manager: ProductionManagerService) -> None:
    assert production_manager.accuracy is not None
    assert production_manager.replay is not None
    assert production_manager.benchmarks is not None
    assert production_manager.batch_validation is not None
    assert production_manager.stress is not None
    assert production_manager.readiness is not None


def test_production_manager_kb_validation_after_learning(
    production_manager: ProductionManagerService, tmp_path: Path
) -> None:
    kb = KnowledgeBaseService(tmp_path / "kb.json")
    kb.load()
    manager = LearningManagerService.__new__(LearningManagerService)
    manager._kb = kb
    from services.learning.event_service import LearningEventService
    from services.learning.rule_service import LearningRuleService
    from services.learning.rule_engine import LearningRuleEngine
    from services.learning.analytics_service import LearningAnalyticsService

    manager._events = LearningEventService(kb)
    manager._rules = LearningRuleService(kb, manager._events)
    manager._engine = LearningRuleEngine(kb)
    manager._analytics = LearningAnalyticsService(kb, manager._events)
    production_manager.set_learning_manager(manager)
    assert production_manager.kb_validation is not None


def test_report_batch_validation(production_manager: ProductionManagerService, sample_spec: DesignSpecification) -> None:
    from models.production import ProductionReportType
    from models.validation import BatchValidationSummary

    summary = BatchValidationSummary(mean_accuracy=92.0, project_count=3)
    report = production_manager.reports.generate(
        ProductionReportType.BATCH_VALIDATION,
        batch_summary=summary,
    )
    assert report.title == "Batch Validation Report"


def test_report_release_readiness(production_manager: ProductionManagerService) -> None:
    from models.production import ProductionReportType

    readiness = ReadinessService().generate(test_total=200, test_passed=200)
    report = production_manager.reports.generate(
        ProductionReportType.RELEASE_READINESS,
        readiness_report=readiness,
    )
    assert "Release Readiness" in report.title


def test_report_kb_validation(production_manager: ProductionManagerService, tmp_path: Path) -> None:
    from models.production import ProductionReportType
    from models.validation import KnowledgeBaseValidationReport

    kb = KnowledgeBaseService(tmp_path / "kb.json")
    kb.load()
    production_manager.set_learning_manager(_minimal_learning(kb))
    kb_report = production_manager.kb_validation.analyse()
    report = production_manager.reports.generate(
        ProductionReportType.KB_VALIDATION,
        kb_report=kb_report,
    )
    assert report.report_type == ProductionReportType.KB_VALIDATION


def _minimal_learning(kb: KnowledgeBaseService) -> LearningManagerService:
    from services.learning.event_service import LearningEventService
    from services.learning.rule_service import LearningRuleService
    from services.learning.rule_engine import LearningRuleEngine
    from services.learning.analytics_service import LearningAnalyticsService

    manager = LearningManagerService.__new__(LearningManagerService)
    manager._kb = kb
    manager._events = LearningEventService(kb)
    manager._rules = LearningRuleService(kb, manager._events)
    manager._engine = LearningRuleEngine(kb)
    manager._analytics = LearningAnalyticsService(kb, manager._events)
    return manager


# --- Model validation ---


def test_benchmark_project_defaults() -> None:
    project = BenchmarkProject(project_name="Test")
    assert project.benchmark_id.startswith("BM_")


def test_validation_asset_bundle() -> None:
    from models.validation import ValidationAssetBundle

    bundle = ValidationAssetBundle(reference_images=["a.png"], png_preview_path="b.png")
    assert len(bundle.reference_images) == 1


def test_release_recommendation_enum() -> None:
    assert ReleaseRecommendation.READY.value == "Ready for RC1"
