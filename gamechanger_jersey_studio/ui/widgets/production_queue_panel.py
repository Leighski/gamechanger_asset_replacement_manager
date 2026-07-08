"""Production Queue panel — pending interpretations with bulk review."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from models.production import CONFIDENCE_BAND_LABELS, ProductionQueueItem, ProductionQueueStatus
from services.interpretation_service import InterpretationService
from services.production_manager_service import ProductionManagerService
from services.projects_manager import ProjectsManager
from ui.theme import Theme
from ui.typography import Typography
from ui.widgets.suggestion_diff_viewer import SuggestionDiffViewer


class ProductionQueuePanel(QFrame):
    """Cross-project production suggestion queue."""

    batch_render_requested = Signal(list)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._projects: ProjectsManager | None = None
        self._production: ProductionManagerService | None = None
        self._interpretation: InterpretationService | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(Theme.SPACING_LG, Theme.SPACING_LG, Theme.SPACING_LG, Theme.SPACING_LG)
        layout.setSpacing(Theme.SPACING_MD)

        heading = QLabel("Production Queue")
        heading.setFont(Typography.heading())
        layout.addWidget(heading)

        filters = QHBoxLayout()
        self._filter_confidence = QComboBox()
        self._filter_confidence.addItem("All confidence", "")
        for label in CONFIDENCE_BAND_LABELS.values():
            self._filter_confidence.addItem(label, label)
        self._filter_season = QComboBox()
        self._filter_season.setEditable(True)
        self._filter_season.addItem("All seasons", "")
        self._filter_status = QComboBox()
        for status in ProductionQueueStatus:
            self._filter_status.addItem(status.value, status.value)
        self._filter_status.insertItem(0, "All statuses", "")
        for combo in (self._filter_confidence, self._filter_season, self._filter_status):
            filters.addWidget(combo)
            combo.currentIndexChanged.connect(self._apply_filters)
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh)
        filters.addWidget(refresh_btn)
        filters.addStretch(1)
        layout.addLayout(filters)

        actions = QHBoxLayout()
        self._btn_accept_trusted = QPushButton("Accept All Trusted")
        self._btn_reject_low = QPushButton("Reject All Low Confidence")
        self._btn_accept_selected = QPushButton("Accept Selected")
        self._btn_reject_selected = QPushButton("Reject Selected")
        self._btn_export = QPushButton("Export Queue")
        self._btn_batch_render = QPushButton("Batch Render Approved")
        for btn in (
            self._btn_accept_trusted,
            self._btn_reject_low,
            self._btn_accept_selected,
            self._btn_reject_selected,
            self._btn_export,
            self._btn_batch_render,
        ):
            actions.addWidget(btn)
        actions.addStretch(1)
        layout.addLayout(actions)

        splitter = QSplitter(Qt.Orientation.Vertical)
        self._table = QTableWidget(0, 8)
        self._table.setHorizontalHeaderLabels(
            ["Project", "Club", "Confidence", "Status", "Template", "Operator", "Last Modified", "Pending"]
        )
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self._table.itemSelectionChanged.connect(self._on_selection_changed)
        splitter.addWidget(self._table)

        self._diff_viewer = SuggestionDiffViewer()
        splitter.addWidget(self._diff_viewer)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter, stretch=1)

        self._btn_accept_trusted.clicked.connect(self._accept_all_trusted)
        self._btn_reject_low.clicked.connect(self._reject_all_low)
        self._btn_accept_selected.clicked.connect(self._accept_selected)
        self._btn_reject_selected.clicked.connect(self._reject_selected)
        self._btn_export.clicked.connect(self._export_queue)
        self._btn_batch_render.clicked.connect(self._request_batch_render)

    def set_services(self, projects: ProjectsManager) -> None:
        self._projects = projects
        self._production = projects.production_manager
        self._interpretation = projects.interpretation_service

    def refresh(self) -> None:
        if self._production is None:
            return
        self._production.refresh_queue_from_recent()
        self._populate_table(self._production.queue.items)

    def _populate_table(self, items: list[ProductionQueueItem]) -> None:
        self._table.setRowCount(len(items))
        for row, item in enumerate(items):
            band_label = CONFIDENCE_BAND_LABELS.get(item.confidence_band, item.confidence_band.value)
            values = [
                item.project_name,
                item.club,
                f"{item.confidence:.0f}% ({band_label})",
                item.status.value,
                item.template_id,
                item.operator or "—",
                item.last_modified[:16] if item.last_modified else "—",
                str(item.pending_suggestion_count),
            ]
            for col, value in enumerate(values):
                cell = QTableWidgetItem(value)
                cell.setData(Qt.ItemDataRole.UserRole, item.item_id)
                self._table.setItem(row, col, cell)

    def _apply_filters(self) -> None:
        if self._production is None:
            return
        band_label = self._filter_confidence.currentData()
        season = self._filter_season.currentText().strip()
        status_label = self._filter_status.currentData()
        status = None
        if status_label:
            for s in ProductionQueueStatus:
                if s.value == status_label:
                    status = s
                    break
        band = None
        if band_label:
            for b, label in CONFIDENCE_BAND_LABELS.items():
                if label == band_label:
                    band = b.value
                    break
        items = self._production.queue.filter_items(
            confidence_band=band,
            season=season if season and season != "All seasons" else None,
            status=status,
        )
        self._populate_table(items)

    def _selected_items(self) -> list[ProductionQueueItem]:
        if self._production is None:
            return []
        selected_ids = set()
        for item in self._table.selectedItems():
            selected_ids.add(item.data(Qt.ItemDataRole.UserRole))
        return [item for item in self._production.queue.items if item.item_id in selected_ids]

    def _on_selection_changed(self) -> None:
        if self._production is None:
            return
        items = self._selected_items()
        if not items:
            self._diff_viewer.set_diffs([])
            return
        diffs = self._production.bulk_review.build_diffs(items[0])
        self._diff_viewer.set_diffs(diffs)

    def _accept_all_trusted(self) -> None:
        if self._production is None or self._interpretation is None:
            return
        result = self._production.bulk_review.accept_all_trusted(self._interpretation)
        QMessageBox.information(
            self,
            "Bulk Review",
            f"Accepted {result.accepted} trusted suggestion(s).",
        )
        self.refresh()

    def _reject_all_low(self) -> None:
        if self._production is None or self._interpretation is None:
            return
        result = self._production.bulk_review.reject_all_low_confidence(self._interpretation)
        QMessageBox.information(
            self,
            "Bulk Review",
            f"Rejected {result.rejected} low-confidence suggestion(s).",
        )
        self.refresh()

    def _accept_selected(self) -> None:
        if self._production is None or self._interpretation is None:
            return
        items = self._selected_items()
        if not items:
            return
        suggestion_ids: list[str] = []
        for item in items:
            suggestion_ids.extend(item.suggestion_ids)
        result = self._production.bulk_review.accept_selected(
            self._interpretation, items, suggestion_ids
        )
        QMessageBox.information(self, "Bulk Review", f"Accepted {result.accepted} suggestion(s).")
        self.refresh()

    def _reject_selected(self) -> None:
        if self._production is None or self._interpretation is None:
            return
        items = self._selected_items()
        if not items:
            return
        suggestion_ids: list[str] = []
        for item in items:
            suggestion_ids.extend(item.suggestion_ids)
        result = self._production.bulk_review.reject_selected(
            self._interpretation, items, suggestion_ids
        )
        QMessageBox.information(self, "Bulk Review", f"Rejected {result.rejected} suggestion(s).")
        self.refresh()

    def _export_queue(self) -> None:
        if self._production is None:
            return
        from core.paths import REPORTS_DIR

        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        path = REPORTS_DIR / "production_queue_export.json"
        path.write_text(self._production.queue.export_queue_json(), encoding="utf-8")
        QMessageBox.information(self, "Export Queue", f"Queue exported to:\n{path}")

    def _request_batch_render(self) -> None:
        if self._production is None:
            return
        ready = [
            item
            for item in self._production.queue.items
            if item.status == ProductionQueueStatus.READY_TO_RENDER
        ]
        if not ready:
            QMessageBox.warning(self, "Batch Render", "No projects are ready to render.")
            return
        self.batch_render_requested.emit(ready)
