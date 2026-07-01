"""Operator metrics — process improvement analytics only."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from models.interpretation import InterpretationArchive, OperatorDecision
from models.production import OperatorMetrics
from models.project import ProjectDocument
from services.logging_manager import get_logger

logger = get_logger()


@dataclass
class ReviewSession:
    started_at: float = field(default_factory=time.perf_counter)
    projects_reviewed: int = 0
    accepted: int = 0
    rejected: int = 0
    modified: int = 0


class OperatorMetricsService:
    """Track operator productivity metrics — never alters AI behaviour."""

    def __init__(self) -> None:
        self._session = ReviewSession()
        self._render_times_ms: list[float] = []
        self._review_durations_ms: list[float] = []

    def start_review(self) -> None:
        self._session = ReviewSession()

    def end_review(self) -> float:
        duration = (time.perf_counter() - self._session.started_at) * 1000.0
        self._review_durations_ms.append(duration)
        return duration

    def record_project_reviewed(self) -> None:
        self._session.projects_reviewed += 1

    def record_accept(self, count: int = 1) -> None:
        self._session.accepted += count

    def record_reject(self, count: int = 1) -> None:
        self._session.rejected += count

    def record_modify(self, count: int = 1) -> None:
        self._session.modified += count

    def record_render_time(self, duration_ms: float) -> None:
        self._render_times_ms.append(duration_ms)

    def compute_from_archive(self, archive: InterpretationArchive | None) -> OperatorMetrics:
        accepted = rejected = modified = 0
        if archive is not None:
            accepted = sum(1 for f in archive.feedback if f.decision == OperatorDecision.ACCEPTED)
            rejected = sum(1 for f in archive.feedback if f.decision == OperatorDecision.REJECTED)
            modified = sum(1 for f in archive.feedback if f.decision == OperatorDecision.MODIFIED)
        total = accepted + rejected + modified
        acceptance_rate = round(accepted / total * 100.0, 2) if total else 0.0
        modification_rate = round(modified / total * 100.0, 2) if total else 0.0
        avg_review = (
            round(sum(self._review_durations_ms) / len(self._review_durations_ms), 2)
            if self._review_durations_ms
            else 0.0
        )
        avg_render = (
            round(sum(self._render_times_ms) / len(self._render_times_ms), 2)
            if self._render_times_ms
            else 0.0
        )
        return OperatorMetrics(
            projects_reviewed=self._session.projects_reviewed,
            suggestions_accepted=accepted,
            suggestions_rejected=rejected,
            suggestions_modified=modified,
            average_review_time_ms=avg_review,
            acceptance_rate=acceptance_rate,
            modification_rate=modification_rate,
            manual_override_count=modified,
            renders_completed=len(self._render_times_ms),
            average_render_time_ms=avg_render,
        )

    def metrics(self) -> OperatorMetrics:
        return self.compute_from_archive(None)

    def aggregate_documents(self, documents: list[ProjectDocument]) -> OperatorMetrics:
        accepted = rejected = modified = 0
        for document in documents:
            archive = document.interpretation_results
            if archive is None:
                continue
            accepted += sum(1 for f in archive.feedback if f.decision == OperatorDecision.ACCEPTED)
            rejected += sum(1 for f in archive.feedback if f.decision == OperatorDecision.REJECTED)
            modified += sum(1 for f in archive.feedback if f.decision == OperatorDecision.MODIFIED)
        total = accepted + rejected + modified
        return OperatorMetrics(
            projects_reviewed=len(documents),
            suggestions_accepted=accepted,
            suggestions_rejected=rejected,
            suggestions_modified=modified,
            acceptance_rate=round(accepted / total * 100.0, 2) if total else 0.0,
            modification_rate=round(modified / total * 100.0, 2) if total else 0.0,
            manual_override_count=modified,
            renders_completed=len(self._render_times_ms),
            average_render_time_ms=(
                round(sum(self._render_times_ms) / len(self._render_times_ms), 2)
                if self._render_times_ms
                else 0.0
            ),
        )
