"""Batch validation across benchmark libraries."""

from __future__ import annotations

import json
import statistics
from collections import Counter
from pathlib import Path

from core.paths import VALIDATION_REPORTS_DIR
from models.design_specification import DesignSpecification
from models.project import ProjectDocument
from models.validation import AccuracyReport, BatchValidationSummary, BenchmarkLibrary, BenchmarkProject
from services.logging_manager import get_logger
from services.production.accuracy_service import AccuracyService
from services.production.metrics_service import OperatorMetricsService
from services.project_format import read_project_package

logger = get_logger()


class BatchValidationService:
    """Validate benchmark libraries and produce aggregate reports."""

    def __init__(
        self,
        accuracy: AccuracyService | None = None,
        metrics: OperatorMetricsService | None = None,
    ) -> None:
        self._accuracy = accuracy or AccuracyService()
        self._metrics = metrics or OperatorMetricsService()

    def validate_project(self, project: BenchmarkProject) -> AccuracyReport:
        expected = project.expected_spec
        generated = project.generated_spec
        if expected is None or generated is None:
            if project.gjs_project_path:
                try:
                    doc, _ = read_project_package(Path(project.gjs_project_path))
                    generated = doc.design_spec or DesignSpecification.from_manifest(doc.manifest)
                except Exception as exc:
                    logger.warning("Could not load GJS project — {}", exc)
                    generated = generated or DesignSpecification()
            else:
                generated = generated or DesignSpecification()
            expected = expected or DesignSpecification()

        missing = self._accuracy.detect_missing_components(generated)
        report = self._accuracy.score(
            expected,
            generated,
            project_name=project.project_name,
            missing_components=missing,
        )
        project.accuracy = report
        return report

    def validate_library(
        self,
        library: BenchmarkLibrary,
        *,
        documents: list[ProjectDocument] | None = None,
    ) -> BatchValidationSummary:
        reports: list[AccuracyReport] = []
        field_corrections: Counter[str] = Counter()
        all_missing: Counter[str] = Counter()

        for project in library.projects:
            report = self.validate_project(project)
            reports.append(report)
            for cat in report.categories:
                for detail in cat.details:
                    field = detail.split(":")[0] if ":" in detail else detail
                    field_corrections[field] += 1
            for comp in report.missing_catalogue_components:
                all_missing[comp] += 1

        scores = [r.overall.score for r in reports]
        mean_acc = round(statistics.mean(scores), 2) if scores else 0.0
        median_acc = round(statistics.median(scores), 2) if scores else 0.0

        docs = documents or []
        metrics = self._metrics.aggregate_documents(docs) if docs else self._metrics.metrics()

        learning_effectiveness = 0.0
        if docs:
            applied = sum(len(d.learning_record.rules_applied) for d in docs if d.learning_record)
            accepted = sum(
                len(d.learning_record.recommendations_accepted) for d in docs if d.learning_record
            )
            if applied:
                learning_effectiveness = round(accepted / applied * 100.0, 2)

        return BatchValidationSummary(
            library_name=library.name,
            project_count=len(reports),
            mean_accuracy=mean_acc,
            median_accuracy=median_acc,
            ai_acceptance_rate=metrics.acceptance_rate,
            learning_rule_effectiveness=learning_effectiveness,
            average_review_time_ms=metrics.average_review_time_ms,
            average_render_time_ms=metrics.average_render_time_ms,
            most_corrected_fields=[f for f, _ in field_corrections.most_common(5)],
            missing_catalogue_components=[c for c, _ in all_missing.most_common(10)],
            per_project=reports,
        )

    def save_summary(self, summary: BatchValidationSummary, path: Path | None = None) -> Path:
        VALIDATION_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        target = path or VALIDATION_REPORTS_DIR / "batch_validation_summary.json"
        target.write_text(json.dumps(summary.model_dump(mode="json"), indent=2), encoding="utf-8")
        logger.info("Batch validation report saved — {}", target.name)
        return target
