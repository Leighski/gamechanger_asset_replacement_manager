"""Runtime workspace for temporary files (never saved into .gjs)."""

from __future__ import annotations

import shutil
from pathlib import Path

from core.paths import WORKSPACE_DIR

WORKSPACE_SUBDIRS = (
    "preview_cache",
    "thumbnails",
    "reference_thumbnails",
    "vision_cache",
    "temp_renders",
    "undo",
    "recovery",
)


class WorkspaceService:
    """Manage per-project runtime workspace folders."""

    def __init__(self, root: Path | None = None) -> None:
        self._root = root or WORKSPACE_DIR
        self._root.mkdir(parents=True, exist_ok=True)

    @property
    def root(self) -> Path:
        return self._root

    def project_root(self, project_id: str) -> Path:
        return self._root / project_id

    def ensure_project_workspace(self, project_id: str) -> Path:
        root = self.project_root(project_id)
        for name in WORKSPACE_SUBDIRS:
            (root / name).mkdir(parents=True, exist_ok=True)
        return root

    def recovery_path(self, project_id: str) -> Path:
        return self.project_root(project_id) / "recovery" / "autosave.gjs"

    def thumbnail_path(self, project_id: str) -> Path:
        return self.project_root(project_id) / "thumbnails" / "project.png"

    def clear_recovery(self, project_id: str) -> None:
        path = self.recovery_path(project_id)
        if path.is_file():
            path.unlink()

    def remove_project_workspace(self, project_id: str) -> None:
        root = self.project_root(project_id)
        if root.is_dir():
            shutil.rmtree(root, ignore_errors=True)

    def list_recovery_files(self) -> list[Path]:
        results: list[Path] = []
        if not self._root.is_dir():
            return results
        for project_dir in self._root.iterdir():
            if not project_dir.is_dir():
                continue
            recovery = project_dir / "recovery" / "autosave.gjs"
            if recovery.is_file():
                results.append(recovery)
        return sorted(results)
