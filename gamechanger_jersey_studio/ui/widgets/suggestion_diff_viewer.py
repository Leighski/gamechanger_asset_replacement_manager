"""Visual difference viewer — highlight only fields that would change."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from models.production import CONFIDENCE_BAND_LABELS, SuggestionDiff
from ui.theme import Theme
from ui.typography import Typography


class _DiffRow(QFrame):
    def __init__(self, diff: SuggestionDiff, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("panel")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(Theme.SPACING_MD, Theme.SPACING_SM, Theme.SPACING_MD, Theme.SPACING_SM)

        field = QLabel(diff.field_name)
        field.setFont(Typography.body())
        field.setMinimumWidth(140)

        before = QLabel(diff.current_value or "—")
        before.setStyleSheet(f"color: {Theme.TEXT_MUTED};")
        before.setWordWrap(True)

        arrow = QLabel("→")
        arrow.setStyleSheet(f"color: {Theme.TEXT_MUTED};")

        after = QLabel(diff.proposed_value)
        after.setStyleSheet(f"color: {Theme.ACCENT}; font-weight: 600;")
        after.setWordWrap(True)

        band_colour = {
            "Trusted": "#2ECC71",
            "Review": "#F39C12",
            "Manual Review Required": "#E74C3C",
        }.get(diff.band_label, Theme.TEXT_MUTED)
        conf = QLabel(f"{diff.confidence:.0f}% — {diff.band_label}")
        conf.setStyleSheet(f"color: {band_colour};")
        conf.setMinimumWidth(160)

        layout.addWidget(field)
        layout.addWidget(before, stretch=1)
        layout.addWidget(arrow)
        layout.addWidget(after, stretch=1)
        layout.addWidget(conf)


class SuggestionDiffViewer(QScrollArea):
    """Show before/after values for pending AI suggestions only."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        container = QWidget()
        self._layout = QVBoxLayout(container)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(Theme.SPACING_SM)
        self._empty = QLabel("Select a queue item to review suggested changes.")
        self._empty.setProperty("muted", True)
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._layout.addWidget(self._empty)
        self._layout.addStretch(1)
        self.setWidget(container)

    def set_diffs(self, diffs: list[SuggestionDiff]) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        if not diffs:
            empty = QLabel("No pending field changes.")
            empty.setProperty("muted", True)
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._layout.addWidget(empty)
            self._layout.addStretch(1)
            return
        header = QLabel(f"{len(diffs)} field(s) would change")
        header.setFont(Typography.subheading())
        self._layout.addWidget(header)
        for diff in diffs:
            self._layout.addWidget(_DiffRow(diff))
        self._layout.addStretch(1)
