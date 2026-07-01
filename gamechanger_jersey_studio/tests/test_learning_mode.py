"""Comprehensive tests for Learning Mode."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from models.interpretation import InterpretationSuggestion, SuggestionStatus
from models.learning import (
    LearningRule,
    LearningRuleCategory,
    LearningRuleStatus,
    RecommendedAction,
    TriggerConditions,
)
from models.project import KitType, ProjectDocument, ProjectManifest
from services.learning.event_service import LearningEventService
from services.learning.knowledge_base_service import KnowledgeBaseService
from services.learning.rule_engine import LearningRuleEngine
from services.learning.rule_service import LearningRuleService
from services.learning_manager_service import LearningManagerService
from services.project_format import read_project_package, write_project_package


@pytest.fixture
def kb_path(tmp_path: Path) -> Path:
    return tmp_path / "knowledge_base.json"


@pytest.fixture
def learning_manager(kb_path: Path) -> LearningManagerService:
    kb = KnowledgeBaseService(kb_path)
    kb.load()
    manager = LearningManagerService.__new__(LearningManagerService)
    manager._kb = kb
    manager._events = LearningEventService(kb)
    manager._rules = LearningRuleService(kb, manager._events)
    manager._engine = LearningRuleEngine(kb)
    from services.learning.analytics_service import LearningAnalyticsService

    manager._analytics = LearningAnalyticsService(kb, manager._events)
    return manager


@pytest.fixture
def sample_document(tmp_path: Path) -> ProjectDocument:
    manifest = ProjectManifest(
        project_name="Coventry Home",
        club_name="Coventry City",
        competition="Championship",
        season="2025/26",
        kit_type=KitType.HOME,
        output_folder=str(tmp_path),
        author="Test",
    )
    return ProjectDocument(manifest=manifest, file_path=str(tmp_path / "test.gjs"))


def test_learning_event_recorded(learning_manager: LearningManagerService, sample_document: ProjectDocument) -> None:
    event = learning_manager.events.record_correction(
        sample_document,
        target_field="collar_style",
        original_ai_value="crew",
        final_operator_value="v-neck",
        confidence=88.0,
        operator="Test",
    )
    assert event.club == "Coventry City"
    assert event.target_field == "collar_style"
    assert len(learning_manager.events.events) == 1


def test_rule_crud(learning_manager: LearningManagerService) -> None:
    rule = LearningRule(
        title="Coventry v-neck collar",
        category=LearningRuleCategory.COLLAR,
        triggers=TriggerConditions(club="Coventry City", field_name="collar_style"),
        action=RecommendedAction(target_field="collar_style", recommended_value="v-neck"),
        created_by="Test",
        status=LearningRuleStatus.DRAFT,
    )
    created = learning_manager.rules.create(rule)
    assert created.rule_id
    fetched = learning_manager.rules.get(created.rule_id)
    assert fetched is not None
    learning_manager.approve_rule(created.rule_id)
    assert learning_manager.rules.get(created.rule_id).status == LearningRuleStatus.APPROVED
    learning_manager.disable_rule(created.rule_id)
    assert learning_manager.rules.get(created.rule_id).status == LearningRuleStatus.DISABLED


def test_rule_engine_advisory_only(learning_manager: LearningManagerService, sample_document: ProjectDocument) -> None:
    rule = LearningRule(
        title="Coventry collar",
        triggers=TriggerConditions(club="Coventry City", field_name="collar_style"),
        action=RecommendedAction(
            target_field="collar_style",
            recommended_value="v-neck",
            advisory_note="Historical preference",
            confidence_boost=5.0,
        ),
        status=LearningRuleStatus.APPROVED,
        created_by="Test",
    )
    learning_manager.rules.create(rule)
    suggestion = InterpretationSuggestion(
        target_field="collar_style",
        current_value="crew",
        proposed_value="crew",
        confidence=80.0,
    )
    recs = learning_manager.engine.evaluate(sample_document, [suggestion])
    assert len(recs) == 1
    assert "Learning Recommendation" in recs[0].message
    boosted, _ = learning_manager.evaluate_for_interpretation(sample_document, [suggestion])
    assert boosted[0].confidence == 85.0


def test_pattern_detection_suggests_rule(
    learning_manager: LearningManagerService, sample_document: ProjectDocument
) -> None:
    for _ in range(3):
        learning_manager.events.record_correction(
            sample_document,
            target_field="collar_style",
            original_ai_value="crew",
            final_operator_value="v-neck",
            confidence=85.0,
            operator="Test",
        )
    prompts = learning_manager.rules.detect_rule_suggestions()
    assert len(prompts) >= 1
    assert "Coventry" in prompts[0].message


def test_knowledge_base_import_export(learning_manager: LearningManagerService, tmp_path: Path) -> None:
    rule = LearningRule(
        title="Export test",
        triggers=TriggerConditions(field_name="pattern"),
        action=RecommendedAction(target_field="pattern", recommended_value="hoops"),
        created_by="Test",
    )
    learning_manager.rules.create(rule)
    export_path = tmp_path / "export.json"
    learning_manager.export_knowledge_base(export_path)
    assert export_path.is_file()
    kb2_path = tmp_path / "kb2.json"
    kb2 = KnowledgeBaseService(kb2_path)
    kb2.load()
    kb2.import_from(export_path, merge=False)
    assert len(kb2.knowledge.rules) == 1


def test_learning_record_persisted_in_gjs(tmp_path: Path, sample_document: ProjectDocument) -> None:
    from models.learning import LearningProjectRecord

    sample_document.learning_record = LearningProjectRecord(rules_applied=["LR_TEST"])
    path = tmp_path / "learning_test.gjs"
    write_project_package(sample_document, path)
    reloaded, _ = read_project_package(path)
    assert reloaded.learning_record is not None
    assert "LR_TEST" in reloaded.learning_record.rules_applied


def test_rule_search(learning_manager: LearningManagerService) -> None:
    learning_manager.rules.create(
        LearningRule(
            title="Coventry hoops",
            triggers=TriggerConditions(club="Coventry City"),
            action=RecommendedAction(target_field="pattern", recommended_value="hoops"),
            category=LearningRuleCategory.PATTERN,
            created_by="Test",
        )
    )
    results = learning_manager.rules.search("Coventry")
    assert len(results) == 1
    results = learning_manager.rules.search(category=LearningRuleCategory.PATTERN)
    assert len(results) == 1


def test_analytics_dashboard(learning_manager: LearningManagerService, sample_document: ProjectDocument) -> None:
    learning_manager.events.record_correction(
        sample_document,
        target_field="primary_colour",
        original_ai_value="#FFFFFF",
        final_operator_value="#69B3E7",
        confidence=90.0,
        operator="Test",
    )
    stats = learning_manager.analytics.dashboard_stats()
    assert stats.total_events == 1


def test_rule_enable_disable(learning_manager: LearningManagerService) -> None:
    rule = learning_manager.rules.create(
        LearningRule(
            title="Toggle",
            triggers=TriggerConditions(),
            action=RecommendedAction(target_field="trim_style", recommended_value="TRIM_0001"),
            created_by="Test",
        )
    )
    learning_manager.approve_rule(rule.rule_id)
    assert learning_manager.rules.get(rule.rule_id).status == LearningRuleStatus.APPROVED
    learning_manager.disable_rule(rule.rule_id)
    assert learning_manager.rules.get(rule.rule_id).status == LearningRuleStatus.DISABLED
