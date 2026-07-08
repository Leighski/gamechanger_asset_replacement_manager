"""Project event history."""

from __future__ import annotations

from models.project import HistoryEventType, ProjectDocument, ProjectHistoryEntry


class ProjectHistoryService:
    def record(
        self,
        document: ProjectDocument,
        event: HistoryEventType,
        *,
        application_version: str,
        user: str,
        details: str = "",
    ) -> ProjectHistoryEntry:
        entry = ProjectHistoryEntry.create(
            event,
            application_version=application_version,
            user=user,
            details=details,
        )
        document.history.append(entry)
        document.mark_dirty()
        return entry
