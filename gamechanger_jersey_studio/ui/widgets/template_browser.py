"""Template Browser — browse registered PSD templates."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from services.template_manager_service import TemplateManagerService
from ui.icons import icon
from ui.theme import Theme
from ui.typography import Typography
from ui.widgets.template_card import TemplateCard
from ui.widgets.template_inspector import TemplateInspectorDialog


class TemplateBrowserPanel(QFrame):
    """Browse PSD templates registered with the Template Engine."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._manager: TemplateManagerService | None = None
        root = QVBoxLayout(self)
        root.setContentsMargins(Theme.SPACING_XL, Theme.SPACING_XL, Theme.SPACING_XL, Theme.SPACING_XL)
        root.setSpacing(Theme.SPACING_MD)

        header = QHBoxLayout()
        glyph = QLabel()
        glyph.setPixmap(icon("libraries", color=Theme.ACCENT, size=20).pixmap(20, 20))
        title_block = QVBoxLayout()
        title = QLabel("PSD Templates")
        title.setFont(Typography.heading())
        subtitle = QLabel("Gamechanger Photoshop templates — mapping layer between Studio and PSD")
        subtitle.setProperty("muted", True)
        subtitle.setFont(Typography.caption())
        title_block.addWidget(title)
        title_block.addWidget(subtitle)
        header.addWidget(glyph)
        header.addLayout(title_block)
        header.addStretch(1)
        self._summary = QLabel("0 templates")
        self._summary.setProperty("muted", True)
        self._reload_btn = QPushButton("Reload")
        self._reload_btn.clicked.connect(self._reload)
        header.addWidget(self._summary)
        header.addWidget(self._reload_btn)
        root.addLayout(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._grid_host = QWidget()
        self._grid = QGridLayout(self._grid_host)
        self._grid.setSpacing(Theme.SPACING_MD)
        scroll.setWidget(self._grid_host)
        root.addWidget(scroll, stretch=1)

    def set_manager(self, manager: TemplateManagerService) -> None:
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

        templates = self._manager.manager.list_templates()
        load_ms = self._manager.manager.last_load_ms
        self._summary.setText(f"{len(templates)} template(s) · loaded in {load_ms:.1f}ms")

        for index, template in enumerate(templates):
            card = TemplateCard()
            validation = self._manager.manager.validation(template.template_id)
            card.set_template(template, self._manager.manager.preview_path(template), validation)
            card.activated.connect(self._open_inspector)
            row, col = divmod(index, 3)
            self._grid.addWidget(card, row, col)

    def _open_inspector(self, template_id: str) -> None:
        if self._manager is None:
            return
        template = self._manager.manager.get_template(template_id)
        if template is None:
            return
        dialog = TemplateInspectorDialog(template, self._manager, self)
        dialog.exec()
