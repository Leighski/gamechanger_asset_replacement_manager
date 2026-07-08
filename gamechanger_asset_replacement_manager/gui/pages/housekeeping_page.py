"""Iconik Housekeeping audit UI — read-only library diagnostics."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QTabWidget,
    QToolBox,
    QVBoxLayout,
    QWidget,
)

from gui.theme import Theme
from gui.widgets.card import Card
from gui.widgets.data_table import ICON_ERR, ICON_OK, ICON_WARN, DataTable
from gui.widgets.stat_card import StatCard
from models.housekeeping import (
    DuplicateGroup,
    HousekeepingAuditResult,
    HousekeepingProgress,
    OrphanAssetRecord,
)
from services.paths import REPORTS_DIR

DUPLICATE_COLUMNS = ["Group Key", "Count", "Asset IDs", "Titles"]
ORPHAN_COLUMNS = [
    "Asset ID",
    "Title",
    "Status",
    "Orphan Reasons",
    "File Set",
    "Storage Key",
    "Metadata",
]

TAB_KEYS = {
    "housekeeping": 0,
    "hk_filename": 1,
    "hk_storage": 2,
    "hk_title": 3,
    "hk_orphan": 4,
    "hk_reports": 5,
}


class HousekeepingPage(QWidget):
    """Housekeeping audit page with summary stats and category tables."""

    start_audit = Signal()
    cancel_audit = Signal()
    open_reports_dir = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._result: HousekeepingAuditResult | None = None
        self._report_paths: dict[str, Path] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(Theme.MARGIN, Theme.MARGIN, Theme.MARGIN, Theme.MARGIN)
        root.setSpacing(Theme.MARGIN)

        header = Card(
            "Iconik Housekeeping",
            "Audit the entire Iconik library for duplicate filenames, storage keys, titles, "
            "and orphan assets. This phase is read-only — no assets are modified.",
        )
        btn_row = QHBoxLayout()
        self._run_btn = QPushButton("Run Full Library Audit")
        self._run_btn.setProperty("class", "primary")
        self._run_btn.setMinimumHeight(44)
        self._run_btn.clicked.connect(self.start_audit.emit)
        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setProperty("class", "danger")
        self._cancel_btn.setEnabled(False)
        self._cancel_btn.clicked.connect(self.cancel_audit.emit)
        btn_row.addWidget(self._run_btn)
        btn_row.addWidget(self._cancel_btn)
        btn_row.addStretch()
        header.add_layout(btn_row)

        self._progress_label = QLabel("Run an audit to scan the Iconik library.")
        self._progress_label.setWordWrap(True)
        self._progress_label.setProperty("class", "muted")
        header.add_widget(self._progress_label)

        self._warnings_label = QLabel("")
        self._warnings_label.setWordWrap(True)
        self._warnings_label.setStyleSheet(f"color: {Theme.WARNING};")
        self._warnings_label.setVisible(False)
        header.add_widget(self._warnings_label)

        self._progress = QProgressBar()
        self._progress.setFormat("%p%")
        self._progress.setVisible(False)
        header.add_widget(self._progress)

        stats = QGridLayout()
        stats.setSpacing(16)
        self._stat_scanned = StatCard("Total Assets Scanned", "—", accent=Theme.ACCENT)
        self._stat_filename = StatCard("Duplicate Filenames", "—", accent=Theme.WARNING)
        self._stat_storage = StatCard("Duplicate Storage Keys", "—", accent=Theme.WARNING)
        self._stat_title = StatCard("Duplicate Titles", "—", accent=Theme.WARNING)
        self._stat_orphan = StatCard("Orphan Assets", "—", accent=Theme.ERROR)
        stat_cards = (
            self._stat_scanned,
            self._stat_filename,
            self._stat_storage,
            self._stat_title,
            self._stat_orphan,
        )
        for index, stat_card in enumerate(stat_cards):
            stat_card.setMinimumWidth(160)
            stats.addWidget(stat_card, index // 3, index % 3)
        header.add_layout(stats)
        root.addWidget(header)

        self._tabs = QTabWidget()
        self._overview_toolbox = self._build_overview_tab()
        self._filename_table = DataTable(DUPLICATE_COLUMNS, mono_columns={0, 2})
        self._storage_table = DataTable(DUPLICATE_COLUMNS, mono_columns={0, 2})
        self._title_table = DataTable(DUPLICATE_COLUMNS, mono_columns={0, 2})
        self._orphan_table = DataTable(ORPHAN_COLUMNS, mono_columns={0, 4, 5})
        self._reports_panel = self._build_reports_tab()

        self._tabs.addTab(self._overview_toolbox, "Overview")
        self._tabs.addTab(self._wrap_table(self._filename_table), "Duplicate Filename Audit")
        self._tabs.addTab(self._wrap_table(self._storage_table), "Duplicate Storage Audit")
        self._tabs.addTab(self._wrap_table(self._title_table), "Duplicate Title Audit")
        self._tabs.addTab(self._wrap_table(self._orphan_table), "Orphan Asset Audit")
        self._tabs.addTab(self._reports_panel, "Reports")
        root.addWidget(self._tabs, stretch=1)

    def _wrap_table(self, table: DataTable) -> QWidget:
        wrap = QWidget()
        lay = QVBoxLayout(wrap)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(table)
        return wrap

    def _build_overview_tab(self) -> QToolBox:
        toolbox = QToolBox()
        self._overview_filename = DataTable(DUPLICATE_COLUMNS, mono_columns={0, 2})
        self._overview_storage = DataTable(DUPLICATE_COLUMNS, mono_columns={0, 2})
        self._overview_title = DataTable(DUPLICATE_COLUMNS, mono_columns={0, 2})
        self._overview_orphan = DataTable(ORPHAN_COLUMNS, mono_columns={0, 4, 5})
        toolbox.addItem(self._wrap_table(self._overview_filename), "Duplicate Filename Audit")
        toolbox.addItem(self._wrap_table(self._overview_storage), "Duplicate Storage Audit")
        toolbox.addItem(self._wrap_table(self._overview_title), "Duplicate Title Audit")
        toolbox.addItem(self._wrap_table(self._overview_orphan), "Orphan Asset Audit")
        return toolbox

    def _build_reports_tab(self) -> QWidget:
        panel = QWidget()
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(Theme.MARGIN, Theme.MARGIN, Theme.MARGIN, Theme.MARGIN)
        info = QLabel(
            f"Reports are written to:\n{REPORTS_DIR}\n\n"
            "Exports: duplicate_filename_audit.xlsx, duplicate_storage_audit.xlsx, "
            "duplicate_title_audit.xlsx, orphan_asset_audit.xlsx, iconik_housekeeping_report.xlsx"
        )
        info.setWordWrap(True)
        lay.addWidget(info)
        self._report_status = QLabel("No audit reports generated yet.")
        self._report_status.setWordWrap(True)
        self._report_status.setProperty("class", "muted")
        lay.addWidget(self._report_status)
        open_btn = QPushButton("Open Reports Folder")
        open_btn.setProperty("class", "ghost")
        open_btn.clicked.connect(self.open_reports_dir.emit)
        lay.addWidget(open_btn)
        lay.addStretch()
        return panel

    def go_to_tab(self, key: str) -> None:
        index = TAB_KEYS.get(key, 0)
        self._tabs.setCurrentIndex(index)

    def set_busy(self, busy: bool) -> None:
        self._run_btn.setEnabled(not busy)
        self._cancel_btn.setEnabled(busy)
        self._progress.setVisible(busy)

    def update_progress(self, progress: HousekeepingProgress) -> None:
        total = max(progress.total, 1)
        self._progress.setMaximum(total)
        self._progress.setValue(min(progress.current, total))
        if progress.message:
            self._progress_label.setText(progress.message)
        else:
            phase = progress.phase.replace("_", " ").title()
            self._progress_label.setText(f"{phase}: {progress.current} / {progress.total}")

    def apply_result(
        self,
        result: HousekeepingAuditResult,
        report_paths: dict[str, Path] | None = None,
    ) -> None:
        self._result = result
        self._report_paths = report_paths or {}
        self._stat_scanned.set_value(str(result.total_scanned))
        self._stat_filename.set_value(str(len(result.duplicate_filename_groups)))
        self._stat_storage.set_value(str(len(result.duplicate_storage_groups)))
        self._stat_title.set_value(str(len(result.duplicate_title_groups)))
        self._stat_orphan.set_value(str(len(result.orphan_assets)))

        self._populate_duplicate_table(self._filename_table, result.duplicate_filename_groups)
        self._populate_duplicate_table(self._storage_table, result.duplicate_storage_groups)
        self._populate_duplicate_table(self._title_table, result.duplicate_title_groups)
        self._populate_orphan_table(self._orphan_table, result.orphan_assets)
        self._populate_duplicate_table(self._overview_filename, result.duplicate_filename_groups)
        self._populate_duplicate_table(self._overview_storage, result.duplicate_storage_groups)
        self._populate_duplicate_table(self._overview_title, result.duplicate_title_groups)
        self._populate_orphan_table(self._overview_orphan, result.orphan_assets)

        self._update_toolbox_labels(result)
        self._update_report_status(result, self._report_paths)
        self._update_warnings(result)

        if result.cancelled:
            self._progress_label.setText("Audit cancelled — partial results shown.")
        elif result.error:
            self._progress_label.setText(f"Audit failed: {result.error}")
        elif result.warnings:
            self._progress_label.setText(
                f"Audit complete with warnings — {result.total_scanned} assets scanned."
            )
        else:
            self._progress_label.setText(
                f"Audit complete — {result.total_scanned} assets scanned."
            )
        self._progress.setVisible(False)

    def _update_warnings(self, result: HousekeepingAuditResult) -> None:
        if result.warnings:
            self._warnings_label.setText("Warnings:\n• " + "\n• ".join(result.warnings))
            self._warnings_label.setVisible(True)
        else:
            self._warnings_label.clear()
            self._warnings_label.setVisible(False)

    def _update_toolbox_labels(self, result: HousekeepingAuditResult) -> None:
        self._overview_toolbox.setItemText(0, f"Duplicate Filename Audit ({len(result.duplicate_filename_groups)})")
        self._overview_toolbox.setItemText(1, f"Duplicate Storage Audit ({len(result.duplicate_storage_groups)})")
        self._overview_toolbox.setItemText(2, f"Duplicate Title Audit ({len(result.duplicate_title_groups)})")
        self._overview_toolbox.setItemText(3, f"Orphan Asset Audit ({len(result.orphan_assets)})")

    def _update_report_status(
        self,
        result: HousekeepingAuditResult,
        paths: dict[str, Path],
    ) -> None:
        if not paths:
            if result.error:
                self._report_status.setText(f"No reports written: {result.error}")
            elif result.cancelled:
                self._report_status.setText("Audit cancelled before reports were generated.")
            else:
                self._report_status.setText("No reports generated yet.")
            return
        lines = ["Latest reports:"]
        for label, path in paths.items():
            lines.append(f"  • {label}: {path.name}")
        self._report_status.setText("\n".join(lines))

    @staticmethod
    def _populate_duplicate_table(table: DataTable, groups: list[DuplicateGroup]) -> None:
        table.clear()
        for group in groups:
            icon = ICON_ERR if group.count > 2 else ICON_WARN
            table.append_row(
                [
                    "",
                    group.group_key,
                    str(group.count),
                    ", ".join(group.asset_ids),
                    " | ".join(group.titles),
                ],
                status_icon=icon,
            )

    @staticmethod
    def _populate_orphan_table(table: DataTable, orphans: list[OrphanAssetRecord]) -> None:
        table.clear()
        for orphan in orphans:
            table.append_row(
                [
                    "",
                    orphan.asset_id,
                    orphan.title or "—",
                    orphan.status or "—",
                    ", ".join(orphan.orphan_reasons),
                    orphan.file_set_name or orphan.file_set_id or "—",
                    orphan.storage_key or "—",
                    orphan.metadata_status or "—",
                ],
                status_icon=ICON_ERR,
            )
