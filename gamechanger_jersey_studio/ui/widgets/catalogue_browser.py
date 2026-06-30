"""Catalogue Browser — search, filter, and browse the Component Library."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from models.component_catalogue import ComponentCategory, ComponentStatus
from services.catalogue.search import SortMode
from services.catalogue_manager_service import CatalogueManagerService
from ui.icons import icon
from ui.theme import Theme
from ui.typography import Typography
from ui.widgets.component_card import ComponentCard
from ui.widgets.component_viewer import ComponentViewerDialog


class CatalogueBrowserPanel(QFrame):
    """Professional catalogue browser with search, filter, sort, and preview."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._manager: CatalogueManagerService | None = None
        self._cards: list[ComponentCard] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(Theme.SPACING_XL, Theme.SPACING_XL, Theme.SPACING_XL, Theme.SPACING_XL)
        root.setSpacing(Theme.SPACING_MD)

        header = QHBoxLayout()
        glyph = QLabel()
        glyph.setPixmap(icon("libraries", color=Theme.ACCENT, size=20).pixmap(20, 20))
        title_block = QVBoxLayout()
        title = QLabel("Component Library")
        title.setFont(Typography.heading())
        subtitle = QLabel("Certified Gamechanger design components — permanent catalogue source")
        subtitle.setProperty("muted", True)
        subtitle.setFont(Typography.caption())
        title_block.addWidget(title)
        title_block.addWidget(subtitle)
        header.addWidget(glyph)
        header.addLayout(title_block)
        header.addStretch(1)
        self._summary = QLabel("0 components")
        self._summary.setProperty("muted", True)
        header.addWidget(self._summary)
        root.addLayout(header)

        filters = QHBoxLayout()
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search components…")
        self._search.textChanged.connect(self._refresh)
        self._category = QComboBox()
        self._category.addItem("All Categories", "")
        for category in ComponentCategory:
            self._category.addItem(category.value.replace("_", " ").title(), category.value)
        self._category.currentIndexChanged.connect(self._refresh)
        self._status = QComboBox()
        self._status.addItem("All Statuses", "")
        for status in ComponentStatus:
            self._status.addItem(status.value, status.value)
        self._status.currentIndexChanged.connect(self._refresh)
        self._sort = QComboBox()
        self._sort.addItem("Name (A–Z)", SortMode.NAME_ASC.value)
        self._sort.addItem("Name (Z–A)", SortMode.NAME_DESC.value)
        self._sort.addItem("Recently Modified", SortMode.MODIFIED_DESC.value)
        self._sort.addItem("Status", SortMode.STATUS.value)
        self._sort.currentIndexChanged.connect(self._refresh)
        self._tag_filter = QLineEdit()
        self._tag_filter.setPlaceholderText("Tag filter (comma-separated)")
        self._tag_filter.textChanged.connect(self._refresh)
        self._reload_btn = QPushButton("Reload")
        self._reload_btn.clicked.connect(self._reload)
        for widget in (self._search, self._category, self._status, self._sort, self._tag_filter, self._reload_btn):
            filters.addWidget(widget)
        root.addLayout(filters)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._grid_host = QWidget()
        self._grid = QGridLayout(self._grid_host)
        self._grid.setSpacing(Theme.SPACING_MD)
        scroll.setWidget(self._grid_host)
        root.addWidget(scroll, stretch=1)

    def set_manager(self, manager: CatalogueManagerService) -> None:
        self._manager = manager
        self._refresh()

    def _reload(self) -> None:
        if self._manager is None:
            return
        self._manager.reload()
        self._refresh()

    def _refresh(self) -> None:
        if self._manager is None:
            return
        while self._grid.count():
            item = self._grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._cards.clear()

        category_value = self._category.currentData()
        category = ComponentCategory(category_value) if category_value else None
        status_value = self._status.currentData()
        status = ComponentStatus(status_value) if status_value else None
        tags = [tag.strip() for tag in self._tag_filter.text().split(",") if tag.strip()]
        sort = SortMode(self._sort.currentData())

        components = self._manager.search(
            self._search.text(),
            category=category,
            tags=tags or None,
            status=status,
            sort=sort,
        )
        load_ms = self._manager.last_load_ms
        self._summary.setText(f"{len(components)} component(s) · loaded in {load_ms:.1f}ms")

        for index, component in enumerate(components):
            card = ComponentCard()
            card.set_component(component, self._manager.preview_path(component))
            card.activated.connect(self._open_viewer)
            row, col = divmod(index, 3)
            self._grid.addWidget(card, row, col)
            self._cards.append(card)

    def _open_viewer(self, component_id: str, category: str) -> None:
        if self._manager is None:
            return
        component = self._manager.get_component(category, component_id)
        if component is None:
            return
        dialog = ComponentViewerDialog(component, self._manager, self)
        dialog.exec()
