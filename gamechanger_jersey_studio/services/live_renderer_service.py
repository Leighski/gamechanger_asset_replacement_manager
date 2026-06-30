"""Live Renderer Service — project integration for the preview pipeline."""

from __future__ import annotations

from pathlib import Path

from models.design_specification import DesignSpecification
from models.project import ProjectDocument
from models.renderer import LIVE_RENDERER_VERSION, RendererSettings, RenderResult
from services.catalogue_manager_service import CatalogueManagerService
from services.logging_manager import get_logger
from services.rendering.engine import RenderingEngine
from services.rendering.render_queue import RenderQueue

RENDERER_SETTINGS_NAME = "renderer/settings.json"
logger = get_logger()


class LiveRendererService:
    """Orchestrate live preview rendering with project-scoped settings."""

    def __init__(self, catalogue: CatalogueManagerService) -> None:
        self._catalogue = catalogue
        self._engine = RenderingEngine(catalogue)
        self._queue = RenderQueue()

    @property
    def engine(self) -> RenderingEngine:
        return self._engine

    @property
    def queue(self) -> RenderQueue:
        return self._queue

    def ensure_settings(self, document: ProjectDocument) -> RendererSettings:
        if document.renderer_settings is None:
            document.renderer_settings = RendererSettings()
        return document.renderer_settings

    def update_settings(self, document: ProjectDocument, settings: RendererSettings) -> None:
        document.renderer_settings = settings
        document.mark_dirty()

    def render_spec(
        self,
        spec: DesignSpecification,
        settings: RendererSettings,
    ) -> RenderResult:
        token = self._queue.enqueue()

        def token_check() -> bool:
            return self._queue.is_current(token)

        return self._engine.render(spec, settings, token_check=token_check)

    def render_document(self, document: ProjectDocument) -> RenderResult:
        spec = document.design_spec
        if spec is None:
            from models.design_specification import DesignSpecification as DS

            spec = DS.from_manifest(document.manifest)
        settings = self.ensure_settings(document)
        return self.render_spec(spec, settings)

    def settings_path(self) -> str:
        return RENDERER_SETTINGS_NAME

    def version(self) -> str:
        return LIVE_RENDERER_VERSION

    def clear_cache(self) -> None:
        self._engine.cache.invalidate()
        logger.info("Preview cache cleared")

    def cache_disk_root(self, workspace_root: Path) -> Path:
        path = workspace_root / "preview_cache"
        path.mkdir(parents=True, exist_ok=True)
        return path
