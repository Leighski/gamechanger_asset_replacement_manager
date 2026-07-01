"""Libraries panel — Component Library and PSD Templates."""

from __future__ import annotations

from PySide6.QtWidgets import QFrame, QTabWidget, QVBoxLayout

from services.catalogue_manager_service import CatalogueManagerService
from services.template_manager_service import TemplateManagerService
from ui.theme import Theme
from ui.widgets.catalogue_browser import CatalogueBrowserPanel
from ui.widgets.template_browser import TemplateBrowserPanel


class LibrariesPanel(QFrame):
    """Combined Libraries view with Components and PSD Templates tabs."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._tabs = QTabWidget()
        self._catalogue = CatalogueBrowserPanel(self)
        self._templates = TemplateBrowserPanel(self)
        self._tabs.addTab(self._catalogue, "Components")
        self._tabs.addTab(self._templates, "PSD Templates")
        self._tabs.setStyleSheet(f"QTabWidget::pane {{ border: none; background: {Theme.PANEL}; }}")
        layout.addWidget(self._tabs)

    def set_catalogue_manager(self, manager: CatalogueManagerService) -> None:
        self._catalogue.set_manager(manager)

    def set_template_manager(self, manager: TemplateManagerService) -> None:
        self._templates.set_manager(manager)
