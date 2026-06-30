"""Application settings and persisted state models."""

from __future__ import annotations

from pydantic import BaseModel, Field


class WindowGeometry(BaseModel):
    width: int = Field(default=1440, ge=400, le=10000)
    height: int = Field(default=900, ge=300, le=10000)
    x: int = Field(default=100)
    y: int = Field(default=100)
    maximised: bool = False


class RecentProjectEntry(BaseModel):
    path: str
    name: str = ""
    club: str = ""
    season: str = ""
    last_opened: str = ""


class AppSettings(BaseModel):
    theme: str = "dark"
    window: WindowGeometry = Field(default_factory=WindowGeometry)
    autosave_interval_minutes: int = Field(default=5, ge=1, le=120)
    default_project_folder: str = ""
    recent_projects: list[RecentProjectEntry] = Field(default_factory=list)
