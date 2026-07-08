"""Generated artwork records — persisted render outputs for a project."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, Field


class ArtworkRenderType(str, Enum):
    LIVE_PREVIEW = "live_preview"
    PRODUCTION_RENDER = "production_render"
    PRODUCTION_PSD = "production_psd"


class GeneratedArtworkRecord(BaseModel):
    """One rendered artwork output linked to a project."""

    artwork_id: str = Field(default_factory=lambda: uuid4().hex[:12])
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )
    render_type: ArtworkRenderType
    label: str = ""
    png_path: str
    psd_path: str = ""
    log_path: str = ""
    quality: str = ""
    width: int = 0
    height: int = 0


class GeneratedArtworkArchive(BaseModel):
    items: list[GeneratedArtworkRecord] = Field(default_factory=list)

    def add(self, record: GeneratedArtworkRecord) -> None:
        self.items.append(record)

    def latest(self) -> GeneratedArtworkRecord | None:
        return self.items[-1] if self.items else None

    def sorted_items(self) -> list[GeneratedArtworkRecord]:
        return sorted(self.items, key=lambda item: item.created_at, reverse=True)
