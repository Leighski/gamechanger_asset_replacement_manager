"""Comprehensive tests for GJS-012 production workflow."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.version import APP_VERSION
from models.interpretation import ConfidenceBand, InterpretationArchive, InterpretationResult, InterpretationSuggestion, SuggestionStatus, confidence_band
from models.production import BatchRenderJobStatus, ConfidenceThresholds, ProductionQueueStatus
from models.project import HistoryEventType, KitType, ProjectDocument, ProjectManifest
from models.psd_template import TemplateProjectSettings
from services.production.audit_service import ProductionAuditService
from services.production.bulk_review_service import BulkReviewService
from services.production.confidence_service import ProductionConfidenceService
from services.production.metrics_service import OperatorMetricsService
from services.production.queue_service import ProductionQueueService
from services.production.report_service import ProductionReportService
from services.production_manager_service import ProductionManagerService
from services.project_format import write_project_package
from services.psd_rendering.render_queue import PSDRenderQueue
from services.settings_manager import SettingsManager
from services.template_manager_service import TemplateManagerService


@pytest.fixture
def settings_manager(tmp_path: Path) -> SettingsManager:
    manager = SettingsManager(tmp_path / "settings.json")
    manager.load()
    return manager


@pytest.fixture
def production_manager(settings_manager: SettingsManager) -> ProductionManagerService:
    templates = TemplateManagerService()
    return ProductionManagerService(settings_manager, templates)


def test_confidence_threshold_defaults() -> None:
    thresholds = ConfidenceThresholds()
    assert thresholds.trusted_min == 95.0
    assert thresholds.review_min == 85.0
    assert thresholds.band_for(96.0) == ConfidenceBand.HIGH
    assert thresholds.band_for(90.0) == ConfidenceBand.MEDIUM
    assert thresholds.band_for(70.0) == ConfidenceBand.LOW


def test_confidence_band_function_matches_defaults() -> None:
    assert confidence_band(96.0) == ConfidenceBand.HIGH
    assert confidence_band(85.0) == ConfidenceBand.MEDIUM
    assert confidence_band(72.0) == ConfidenceBand.LOW


def test_custom_confidence_thresholds() -> None:
    thresholds = ConfidenceThresholds(trusted_min=98.0, review_min=90.0)
    service = ProductionConfidenceService(thresholds)
    assert service.band_for(97.0) == ConfidenceBand.MEDIUM
    assert service.band_label(ConfidenceBand.HIGH) == "Trusted"


def test_settings_persist_confidence_thresholds(settings_manager: SettingsManager) -> None:
    settings_manager.update(confidence_thresholds=ConfidenceThresholds(trusted_min=92.0, review_min=88.0))
    reloaded = SettingsManager(settings_manager.path)
    reloaded.load()
    assert reloaded.settings.confidence_thresholds.trusted_min == 92.0
    assert reloaded.settings.confidence_thresholds.review_min == 88.0


def test_production_queue_from_project(tmp_path: Path, production_manager: ProductionManagerService) -> None:
    manifest = ProjectManifest(
        project_name="Queue Test",
        club_name="Coventry City",
        competition="Championship",
        season="2025/26",
        kit_type=KitType.HOME,
        output_folder=str(tmp_path),
        author="Test",
    )
    suggestion = InterpretationSuggestion(
        target_field="primary_colour",
        current_value="#FFFFFF",
        proposed_value="#69B3E7",
        confidence=96.0,
        confidence_band=ConfidenceBand.HIGH,
    )
    interpretation = InterpretationResult(
        analysis_id="analysis-1",
        suggestions=[suggestion],
    )
    document = ProjectDocument(
        manifest=manifest,
        interpretation_results=InterpretationArchive(interpretations=[interpretation]),
        template_settings=TemplateProjectSettings(active_template_id="TEMPLATE_BROADCAST_0001"),
    )
    path = tmp_path / "queue_test.gjs"
    write_project_package(document, path)

    items = production_manager.queue.refresh_from_paths([path])
    assert len(items) == 1
    assert items[0].club == "Coventry City"
    assert items[0].pending_suggestion_count == 1
    assert items[0].status == ProductionQueueStatus.PENDING_REVIEW


def test_queue_filters(production_manager: ProductionManagerService) -> None:
    from models.production import ProductionQueueItem

    production_manager.queue._items = [
        ProductionQueueItem(
            item_id="1",
            project_path="/tmp/a.gjs",
            project_name="A",
            club="Club A",
            season="2024/25",
            competition="League",
            interpretation_id="i1",
            confidence=96.0,
            confidence_band=ConfidenceBand.HIGH,
            status=ProductionQueueStatus.PENDING_REVIEW,
            template_id="TEMPLATE_BROADCAST_0001",
        ),
        ProductionQueueItem(
            item_id="2",
            project_path="/tmp/b.gjs",
            project_name="B",
            club="Club B",
            season="2025/26",
            competition="Cup",
            interpretation_id="i2",
            confidence=70.0,
            confidence_band=ConfidenceBand.LOW,
            status=ProductionQueueStatus.PENDING_REVIEW,
            template_id="TEMPLATE_BROADCAST_0001",
        ),
    ]
    filtered = production_manager.queue.filter_items(season="2024")
    assert len(filtered) == 1
    assert filtered[0].project_name == "A"


def test_bulk_review_builds_diffs(production_manager: ProductionManagerService, tmp_path: Path) -> None:
    from models.production import ProductionQueueItem

    item = ProductionQueueItem(
        item_id="x",
        project_path="/nonexistent.gjs",
        interpretation_id="missing",
    )
    assert production_manager.bulk_review.build_diffs(item) == []


def test_render_queue_pause_cancel(tmp_path: Path) -> None:
    manifest = ProjectManifest(
        project_name="Pause Test",
        club_name="Test",
        competition="League",
        season="2025/26",
        kit_type=KitType.HOME,
        output_folder=str(tmp_path),
        author="Test",
    )
    document = ProjectDocument(manifest=manifest)
    queue = PSDRenderQueue()
    queue.enqueue(document)
    queue.start_batch()
    queue.pause()
    assert queue.is_paused()
    assert queue.dequeue() is None
    queue.resume()
    job = queue.dequeue()
    assert job is not None
    queue.cancel()
    assert queue.is_cancelled()


def test_audit_chain_builds_links(tmp_path: Path) -> None:
    manifest = ProjectManifest(
        project_name="Audit Test",
        club_name="Test FC",
        competition="League",
        season="2025/26",
        kit_type=KitType.HOME,
        output_folder=str(tmp_path),
        author="Test",
    )
    document = ProjectDocument(manifest=manifest, file_path=str(tmp_path / "audit.gjs"))
    audit = ProductionAuditService()
    record = audit.build_chain(
        document,
        render_psd_path=str(tmp_path / "out.psd"),
        render_png_path=str(tmp_path / "out.png"),
        template_id="TEMPLATE_BROADCAST_0001",
        template_version="1.0.0",
    )
    link_types = {link.link_type for link in record.chain}
    assert "Design Specification" in link_types
    assert "Template" in link_types
    assert "Renderer" in link_types
    assert "PSD Output" in link_types


def test_operator_metrics(production_manager: ProductionManagerService) -> None:
    metrics = production_manager.metrics
    metrics.start_review()
    metrics.record_accept(3)
    metrics.record_reject(1)
    metrics.record_render_time(1000.0)
    metrics.end_review()
    result = metrics.metrics()
    assert result.renders_completed == 1
    assert result.average_render_time_ms == 1000.0


def test_production_reports(production_manager: ProductionManagerService) -> None:
    from models.production import ProductionReportType

    report = production_manager.reports.generate(ProductionReportType.DAILY_PRODUCTION)
    assert report.title == "Daily Production Report"
    path = production_manager.reports.save_report(report)
    assert path.is_file()
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["report_type"] == ProductionReportType.DAILY_PRODUCTION.value


def test_production_manager_updates_thresholds(production_manager: ProductionManagerService) -> None:
    production_manager.update_thresholds(ConfidenceThresholds(trusted_min=94.0, review_min=86.0))
    assert production_manager.confidence.thresholds.trusted_min == 94.0
