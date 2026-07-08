"""Production report generation."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from core.paths import REPORTS_DIR
from models.production import (
    CONFIDENCE_BAND_LABELS,
    ProductionDashboardStats,
    ProductionReport,
    ProductionReportType,
)
from models.production import OperatorMetrics
from services.logging_manager import get_logger
from services.production.queue_service import ProductionQueueService

logger = get_logger()


class ProductionReportService:
    """Generate production workflow reports."""

    def __init__(self, queue: ProductionQueueService, learning=None) -> None:
        self._queue = queue
        self._learning = learning

    def generate(
        self,
        report_type: ProductionReportType,
        *,
        dashboard: ProductionDashboardStats | None = None,
        metrics: OperatorMetrics | None = None,
        failed_jobs: list[dict[str, object]] | None = None,
        batch_summary=None,
        readiness_report=None,
        kb_report=None,
    ) -> ProductionReport:
        dashboard = dashboard or self._queue.dashboard_stats()
        metrics = metrics or OperatorMetrics()
        failed_jobs = failed_jobs or []

        if report_type == ProductionReportType.DAILY_PRODUCTION:
            return self._daily_production(dashboard, metrics)
        if report_type == ProductionReportType.CONFIDENCE_SUMMARY:
            return self._confidence_summary()
        if report_type == ProductionReportType.OPERATOR_ACTIVITY:
            return self._operator_activity(metrics)
        if report_type == ProductionReportType.RENDER_PERFORMANCE:
            return self._render_performance(dashboard, metrics)
        if report_type == ProductionReportType.LEARNING_SUMMARY:
            return self._learning_summary()
        if report_type == ProductionReportType.TOP_RULES:
            return self._top_rules()
        if report_type == ProductionReportType.RULE_EFFECTIVENESS:
            return self._rule_effectiveness()
        if report_type == ProductionReportType.LEARNING_GROWTH:
            return self._learning_growth()
        if report_type == ProductionReportType.BATCH_VALIDATION:
            return self._batch_validation(batch_summary)
        if report_type == ProductionReportType.RELEASE_READINESS:
            return self._release_readiness(readiness_report)
        if report_type == ProductionReportType.KB_VALIDATION:
            return self._kb_validation(kb_report)
        return self._failure_report(failed_jobs)

    def save_report(self, report: ProductionReport, path: Path | None = None) -> Path:
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        safe_type = report.report_type.name.lower()
        target = path or REPORTS_DIR / f"{safe_type}_{stamp}.json"
        target.write_text(json.dumps(report.model_dump(mode="json"), indent=2), encoding="utf-8")
        logger.info("Production report saved — {}", target.name)
        return target

    def _daily_production(
        self, dashboard: ProductionDashboardStats, metrics: OperatorMetrics
    ) -> ProductionReport:
        return ProductionReport(
            report_type=ProductionReportType.DAILY_PRODUCTION,
            title="Daily Production Report",
            summary={
                "awaiting_review": dashboard.awaiting_review,
                "ready_to_render": dashboard.ready_to_render,
                "rendering": dashboard.rendering,
                "completed": dashboard.completed,
                "failed": dashboard.failed,
                "queue_size": len(self._queue.items),
            },
            sections=[
                {"name": "Dashboard", "data": dashboard.model_dump(mode="json")},
                {"name": "Operator Metrics", "data": metrics.model_dump(mode="json")},
            ],
        )

    def _confidence_summary(self) -> ProductionReport:
        bands: dict[str, int] = {label: 0 for label in CONFIDENCE_BAND_LABELS.values()}
        confidences: list[float] = []
        for item in self._queue.items:
            label = CONFIDENCE_BAND_LABELS.get(item.confidence_band, item.confidence_band.value)
            bands[label] = bands.get(label, 0) + 1
            confidences.append(item.confidence)
        avg = round(sum(confidences) / len(confidences), 2) if confidences else 0.0
        return ProductionReport(
            report_type=ProductionReportType.CONFIDENCE_SUMMARY,
            title="Confidence Summary",
            summary={"average_confidence": avg, "total_items": len(self._queue.items)},
            sections=[{"name": "By Band", "data": bands}],
        )

    def _operator_activity(self, metrics: OperatorMetrics) -> ProductionReport:
        return ProductionReport(
            report_type=ProductionReportType.OPERATOR_ACTIVITY,
            title="Operator Activity",
            summary=metrics.model_dump(mode="json"),
            sections=[],
        )

    def _render_performance(
        self, dashboard: ProductionDashboardStats, metrics: OperatorMetrics
    ) -> ProductionReport:
        return ProductionReport(
            report_type=ProductionReportType.RENDER_PERFORMANCE,
            title="Render Performance",
            summary={
                "average_render_time_ms": metrics.average_render_time_ms,
                "renders_completed": metrics.renders_completed,
                "dashboard_average_render_ms": dashboard.average_render_time_ms,
            },
            sections=[],
        )

    def _failure_report(self, failed_jobs: list[dict[str, object]]) -> ProductionReport:
        return ProductionReport(
            report_type=ProductionReportType.FAILURE_REPORT,
            title="Failure Report",
            summary={"failure_count": len(failed_jobs)},
            sections=[{"name": "Failures", "data": failed_jobs}],
        )

    def _learning_summary(self) -> ProductionReport:
        stats = self._learning.analytics.dashboard_stats() if self._learning else None
        return ProductionReport(
            report_type=ProductionReportType.LEARNING_SUMMARY,
            title="Learning Summary",
            summary=stats.model_dump(mode="json") if stats else {},
            sections=[],
        )

    def _top_rules(self) -> ProductionReport:
        rules = []
        if self._learning:
            rules = sorted(
                self._learning.rules.rules,
                key=lambda r: r.usage_count,
                reverse=True,
            )[:10]
        return ProductionReport(
            report_type=ProductionReportType.TOP_RULES,
            title="Top Rules",
            summary={"count": len(rules)},
            sections=[{"name": "rules", "data": [r.model_dump(mode="json") for r in rules]}],
        )

    def _rule_effectiveness(self) -> ProductionReport:
        analytics = self._learning.analytics.all_rule_analytics() if self._learning else []
        return ProductionReport(
            report_type=ProductionReportType.RULE_EFFECTIVENESS,
            title="Rule Effectiveness",
            summary={"rules_analysed": len(analytics)},
            sections=[{"name": "analytics", "data": [a.model_dump(mode="json") for a in analytics]}],
        )

    def _learning_growth(self) -> ProductionReport:
        growth = self._learning.analytics.learning_growth() if self._learning else {}
        return ProductionReport(
            report_type=ProductionReportType.LEARNING_GROWTH,
            title="Learning Growth",
            summary=growth,
            sections=[],
        )

    def _batch_validation(self, batch_summary) -> ProductionReport:
        summary = batch_summary.model_dump(mode="json") if batch_summary else {}
        return ProductionReport(
            report_type=ProductionReportType.BATCH_VALIDATION,
            title="Batch Validation Report",
            summary={
                "mean_accuracy": summary.get("mean_accuracy", 0),
                "median_accuracy": summary.get("median_accuracy", 0),
                "project_count": summary.get("project_count", 0),
            },
            sections=[{"name": "full_summary", "data": summary}],
        )

    def _release_readiness(self, readiness_report) -> ProductionReport:
        data = readiness_report.model_dump(mode="json") if readiness_report else {}
        return ProductionReport(
            report_type=ProductionReportType.RELEASE_READINESS,
            title="Release Readiness Report",
            summary={
                "recommendation": data.get("recommendation", ""),
                "outstanding_issues": data.get("outstanding_issues", []),
            },
            sections=[{"name": "full_report", "data": data}],
        )

    def _kb_validation(self, kb_report) -> ProductionReport:
        data = kb_report.model_dump(mode="json") if kb_report else {}
        return ProductionReport(
            report_type=ProductionReportType.KB_VALIDATION,
            title="Knowledge Base Validation",
            summary={
                "never_triggered": len(data.get("never_triggered_rules", [])),
                "suggested_merges": len(data.get("suggested_merges", [])),
                "suggested_retirements": len(data.get("suggested_retirements", [])),
            },
            sections=[{"name": "full_report", "data": data}],
        )
