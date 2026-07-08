"""Template Manager Service — project integration for PSD templates."""

from __future__ import annotations

from pathlib import Path

from models.project import ProjectDocument
from models.psd_template import PublishedTemplateMappings, TemplateProjectSettings
from services.logging_manager import get_logger
from services.template_engine.manager import TemplateManager

TEMPLATE_SETTINGS_NAME = "template/settings.json"
logger = get_logger()


class TemplateManagerService:
    """Expose template engine to application and render pipeline."""

    def __init__(self, templates_root: Path | None = None) -> None:
        self._manager = TemplateManager(templates_root)
        self._manager.load()

    @property
    def manager(self) -> TemplateManager:
        return self._manager

    def reload(self) -> None:
        self._manager.reload()

    def ensure_settings(self, document: ProjectDocument) -> TemplateProjectSettings:
        if document.template_settings is None:
            document.template_settings = TemplateProjectSettings()
        return document.template_settings

    def set_active_template(self, document: ProjectDocument, template_id: str) -> None:
        settings = self.ensure_settings(document)
        settings.active_template_id = template_id
        document.template_settings = settings
        document.mark_dirty()
        self._manager.select_template(template_id)

    def active_template_id(self, document: ProjectDocument) -> str:
        settings = document.template_settings
        build_profile = document.manifest.build_profile
        return self._manager.active_template_id(settings, build_profile)

    def published_mappings(self, document: ProjectDocument) -> PublishedTemplateMappings | None:
        template_id = self.active_template_id(document)
        return self._manager.publish_mappings(template_id)

    def settings_path(self) -> str:
        return TEMPLATE_SETTINGS_NAME
