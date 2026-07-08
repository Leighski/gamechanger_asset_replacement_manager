"""Card container for grouped UI sections."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from gui.theme import Theme


class Card(QFrame):
    def __init__(
        self,
        title: str,
        subtitle: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setProperty("class", "card")
        self.setFrameShape(QFrame.Shape.StyledPanel)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(Theme.MARGIN, Theme.MARGIN, Theme.MARGIN, Theme.MARGIN)
        outer.setSpacing(Theme.SPACING)

        if title:
            title_lbl = QLabel(title)
            title_lbl.setProperty("class", "card-title")
            outer.addWidget(title_lbl)
        if subtitle:
            sub = QLabel(subtitle)
            sub.setProperty("class", "muted")
            sub.setWordWrap(True)
            outer.addWidget(sub)

        self.body = QWidget()
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(0, 0, 0, 0)
        self.body_layout.setSpacing(Theme.SPACING)
        outer.addWidget(self.body)

    def add_widget(self, widget: QWidget) -> None:
        self.body_layout.addWidget(widget)

    def add_layout(self, layout) -> None:
        self.body_layout.addLayout(layout)

    def add_stretch(self) -> None:
        self.body_layout.addStretch()
