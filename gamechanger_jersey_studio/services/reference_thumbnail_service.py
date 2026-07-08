"""Thumbnail generation for reference images — workspace only."""

from __future__ import annotations

import io
from pathlib import Path

from services.workspace_service import WorkspaceService

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    Image = None  # type: ignore[assignment,misc]

THUMBNAIL_SIZE = (240, 240)
THUMBNAIL_SUBDIR = "reference_thumbnails"


class ReferenceThumbnailService:
    """Generate and cache reference image thumbnails in the workspace."""

    def __init__(self, workspace: WorkspaceService) -> None:
        self._workspace = workspace

    def thumbnail_dir(self, project_id: str) -> Path:
        path = self._workspace.project_root(project_id) / THUMBNAIL_SUBDIR
        path.mkdir(parents=True, exist_ok=True)
        return path

    def thumbnail_path(self, project_id: str, image_id: str) -> Path:
        return self.thumbnail_dir(project_id) / f"{image_id}.png"

    def generate(self, project_id: str, image_id: str, image_bytes: bytes, *, orientation: int = 0) -> Path:
        target = self.thumbnail_path(project_id, image_id)
        if Image is None:  # pragma: no cover
            target.write_bytes(image_bytes)
            return target
        with Image.open(io.BytesIO(image_bytes)) as image:
            if orientation:
                image = image.rotate(-orientation, expand=True)
            image.thumbnail(THUMBNAIL_SIZE, Image.Resampling.LANCZOS)
            image.save(target, format="PNG")
        return target

    def remove(self, project_id: str, image_id: str) -> None:
        path = self.thumbnail_path(project_id, image_id)
        if path.is_file():
            path.unlink()

    def clear_project(self, project_id: str) -> None:
        directory = self.thumbnail_dir(project_id)
        if directory.is_dir():
            for file in directory.glob("*.png"):
                file.unlink()
