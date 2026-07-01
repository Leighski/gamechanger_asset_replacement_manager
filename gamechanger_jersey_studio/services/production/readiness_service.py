"""Release readiness report generation."""

from __future__ import annotations

import json
from pathlib import Path

from core.paths import VALIDATION_REPORTS_DIR
from core.version import APP_VERSION, BUILD_NUMBER
from models.validation import (
    BatchValidationSummary,
    KnowledgeBaseValidationReport,
    RC1_VALIDATION_VERSION,
    ReleaseReadinessReport,
    ReleaseRecommendation,
    StressTestReport,
)
from services.logging_manager import get_logger

logger = get_logger()


class ReadinessService:
    """Aggregate RC1 validation results into a release readiness report."""

    def generate(
        self,
        *,
        test_total: int = 0,
        test_passed: int = 0,
        batch_summary: BatchValidationSummary | None = None,
        stress_report: StressTestReport | None = None,
        kb_report: KnowledgeBaseValidationReport | None = None,
        performance: dict[str, object] | None = None,
        outstanding_issues: list[str] | None = None,
    ) -> ReleaseReadinessReport:
        issues = list(outstanding_issues or [])
        test_summary = {
            "total": test_total,
            "passed": test_passed,
            "failed": test_total - test_passed,
            "pass_rate": round(test_passed / test_total * 100.0, 2) if test_total else 0.0,
        }

        accuracy_summary: dict[str, object] = {}
        if batch_summary:
            accuracy_summary = {
                "mean_accuracy": batch_summary.mean_accuracy,
                "median_accuracy": batch_summary.median_accuracy,
                "project_count": batch_summary.project_count,
                "ai_acceptance_rate": batch_summary.ai_acceptance_rate,
                "most_corrected_fields": batch_summary.most_corrected_fields,
            }
            if batch_summary.mean_accuracy < 80.0:
                issues.append(f"Mean accuracy below 80% ({batch_summary.mean_accuracy}%)")

        stability_summary: dict[str, object] = {}
        if stress_report:
            stability_summary = {
                "all_consistent": stress_report.all_consistent,
                "scenarios": [s.model_dump(mode="json") for s in stress_report.scenarios],
            }
            if not stress_report.all_consistent:
                issues.append("Stress test reported inconsistent render performance")

        if test_summary["failed"] > 0:
            issues.append(f"{test_summary['failed']} automated test(s) failing")

        recommendation = self._recommend(test_summary, accuracy_summary, stability_summary, issues)

        return ReleaseReadinessReport(
            version=RC1_VALIDATION_VERSION,
            test_summary=test_summary,
            performance_summary=performance or {"app_version": APP_VERSION, "build": BUILD_NUMBER},
            accuracy_summary=accuracy_summary,
            stability_summary=stability_summary,
            outstanding_issues=issues,
            recommendation=recommendation,
        )

    def save(self, report: ReleaseReadinessReport, path: Path | None = None) -> Path:
        VALIDATION_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        target = path or VALIDATION_REPORTS_DIR / "release_readiness_report.json"
        target.write_text(json.dumps(report.model_dump(mode="json"), indent=2), encoding="utf-8")
        logger.info("Release readiness report saved — {}", target.name)
        return target

    def _recommend(
        self,
        test_summary: dict[str, object],
        accuracy_summary: dict[str, object],
        stability_summary: dict[str, object],
        issues: list[str],
    ) -> ReleaseRecommendation:
        if test_summary.get("failed", 0):
            return ReleaseRecommendation.NOT_READY
        if len(issues) > 2:
            return ReleaseRecommendation.NOT_READY
        if issues:
            return ReleaseRecommendation.CONDITIONAL
        mean_acc = accuracy_summary.get("mean_accuracy", 100.0)
        if isinstance(mean_acc, (int, float)) and mean_acc < 85.0:
            return ReleaseRecommendation.CONDITIONAL
        if stability_summary.get("all_consistent") is False:
            return ReleaseRecommendation.CONDITIONAL
        return ReleaseRecommendation.READY
