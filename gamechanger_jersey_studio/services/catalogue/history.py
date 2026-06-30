"""Catalogue operation history."""

from __future__ import annotations

import json
from pathlib import Path

from models.component_catalogue import CatalogueHistoryEntry, CatalogueHistoryEventType


class CatalogueHistoryService:
    """Track catalogue component lifecycle events."""

    def __init__(self, path: Path | None = None) -> None:
        from core.paths import COMPONENT_LIBRARY_DIR

        self._path = path or (COMPONENT_LIBRARY_DIR / "catalogue_history.json")
        self._entries: list[CatalogueHistoryEntry] = []

    @property
    def entries(self) -> list[CatalogueHistoryEntry]:
        return list(self._entries)

    def load(self) -> None:
        if not self._path.is_file():
            self._entries = []
            return
        data = json.loads(self._path.read_text(encoding="utf-8"))
        self._entries = [CatalogueHistoryEntry.model_validate(item) for item in data.get("entries", [])]

    def save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"entries": [entry.model_dump(mode="json") for entry in self._entries]}
        self._path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def record(
        self,
        event: CatalogueHistoryEventType,
        *,
        component_id: str = "",
        category: str = "",
        details: str = "",
        user: str = "",
    ) -> CatalogueHistoryEntry:
        entry = CatalogueHistoryEntry(
            event=event,
            component_id=component_id,
            category=category,
            details=details,
            user=user,
        )
        self._entries.append(entry)
        return entry
