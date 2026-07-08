"""Live Renderer Service — project integration for the preview pipeline."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from models.design_specification import DesignSpecification
from models.project import ProjectDocument
from models.psd_template import PublishedTemplateMappings
from models.renderer import LIVE_RENDERER_VERSION, RendererSettings, RenderResult
from services.catalogue_manager_service import CatalogueManagerService
from services.logging_manager import get_logger
from services.rendering.engine import RenderingEngine
from services.rendering.render_queue import RenderQueue

if TYPE_CHECKING:
    from services.template_manager_service import TemplateManagerService

RENDERER_SETTINGS_NAME = "renderer/settings.json"
logger = get_logger()


class LiveRendererService:
    """Orchestrate live preview rendering with project-scoped settings."""

    def __init__(self, catalogue: CatalogueManagerService) -> None:
        self._catalogue = catalogue
        self._engine = RenderingEngine(catalogue)
        self._queue = RenderQueue()
        self._templates: TemplateManagerService | None = None

    def set_template_manager(self, manager: TemplateManagerService) -> None:
        self._templates = manager

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
        *,
        template_mappings: PublishedTemplateMappings | None = None,
    ) -> RenderResult:
        token = self._queue.enqueue()

        def token_check() -> bool:
            return self._queue.is_current(token)

        return self._engine.render(
            spec,
            settings,
            token_check=token_check,
            template_mappings=template_mappings,
        )

    def render_document(self, document: ProjectDocument) -> RenderResult:
        spec = document.design_spec
        if spec is None:
            from models.design_specification import DesignSpecification as DS

            spec = DS.from_manifest(document.manifest)
        settings = self.ensure_settings(document)
        mappings = None
        if self._templates is not None:
            mappings = self._templates.published_mappings(document)
            if mappings is not None:
                logger.debug(
                    "Rendering against template mappings — template={}",
                    mappings.template_id,
                )
        return self.render_spec(spec, settings, template_mappings=mappings)

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
