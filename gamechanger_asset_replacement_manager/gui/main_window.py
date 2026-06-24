"""Main application window — polished operational UI."""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QObject, Qt, QThread, QTimer, Slot
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app import SELECT_FOLDER_PLACEHOLDER
from gui.duplicate_resolution_dialog import DuplicateResolutionDialog
from gui.pages.housekeeping_page import HousekeepingPage, TAB_KEYS as HK_TAB_KEYS
from gui.resolution_preview_dialog import ResolutionPreviewDialog
from gui.theme import Theme, apply_theme
from gui.widgets.card import Card
from gui.widgets.dashboard_header import DashboardHeader
from gui.widgets.data_table import ICON_ERR, ICON_OK, ICON_SKIP, ICON_WARN, DataTable
from gui.widgets.file_browse_line_edit import FileBrowseLineEdit
from gui.widgets.path_drop_line_edit import PathDropLineEdit
from gui.widgets.sidebar import Sidebar
from gui.widgets.stat_card import StatCard
from gui.widgets.upload_panel import UploadProgressPanel
from gui.workers import (
    DualReplacementWorker,
    GovernanceWorker,
    HousekeepingWorker,
    PreflightWorker,
    ScanWorker,
    UploadWorker,
    run_in_thread,
)
from models.discovery import DiscoveryResult, PreflightRow, PreflightStatus, SanitisationOptions, S3Status
from models.upload import AuditRecord, UploadAction, UploadJob, UploadSummary
from models.validation import ValidationResult, ValidatedFile
from services.bulk_governance_service import all_replace_candidates_verified, compute_governance_stats
from services.catalogue_service import CatalogueService
from services.paths import REPORTS_DIR
from services.preflight_validator import PreflightValidator
from services.report_service import ReportService
from services.s3_service import S3Service
from services.settings_service import SettingsService
from services.asset_resolution_service import AssetResolutionResult, GovernanceStatus
from services.dual_replacement_service import DualReplacementOutcome, DualReplacementService
from services.housekeeping_report_service import HousekeepingReportService
from services.housekeeping_service import HousekeepingService
from services.iconik_verification import IconikVerificationService
from services.upload_engine import UploadEngine

logger = logging.getLogger(__name__)

PREFLIGHT_COLUMNS = [
    "Status",
    "Filename",
    "Cleaned Filename",
    "Cat. S3",
    "Resolved Iconik S3 Key",
    "S3 Exists",
    "Local Size",
    "S3 Size",
    "Action",
    "Governance",
    "Asset ID",
    "File Set ID",
    "Resolution",
    "Metadata",
    "Warnings",
    "Message",
]
SANITISE_COLUMNS = ["Status", "Original Filename", "Clean Filename", "Issues"]
HOUSEKEEPING_KEYS = frozenset(HK_TAB_KEYS.keys())


def _format_bytes(n: int | None) -> str:
    if n is None:
        return "—"
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.1f} KB"
    return f"{n / (1024 * 1024):.1f} MB"


def _status_icon_for_preflight(row: PreflightRow) -> str:
    if row.status == PreflightStatus.ERROR:
        return ICON_ERR
    if (
        row.governance_status
        and row.governance_status != GovernanceStatus.VERIFIED.value
    ):
        return ICON_ERR
    if row.status == PreflightStatus.WARNING:
        return ICON_WARN
    if row.status == PreflightStatus.SKIP and not row.governance_status:
        return ICON_SKIP
    if row.governance_status == GovernanceStatus.VERIFIED.value:
        if row.s3_status == S3Status.MISSING.value:
            return ICON_WARN
        return ICON_OK
    if row.catalogue_s3_exists or row.s3_exists:
        return ICON_WARN
    return ICON_WARN


def _status_icon_for_sanitise(excluded: bool, issues: list) -> str:
    if excluded:
        return ICON_SKIP
    if any(getattr(i, "value", str(i)) in ("duplicate_name", "invalid_extension") for i in issues):
        return ICON_ERR
    if issues:
        return ICON_WARN
    return ICON_OK


class MainWindow(QWidget):
    """Root content widget hosted inside QMainWindow shell."""

    def __init__(self) -> None:
        super().__init__()
        self._settings = SettingsService()
        self._catalogues = CatalogueService()
        self._s3 = self._build_s3_client()
        self._preflight = PreflightValidator(self._s3)
        self._upload_engine = UploadEngine(self._s3, max_workers=self._settings.upload_max_workers())
        self._reports = ReportService()
        self._housekeeping_reports = HousekeepingReportService()
        self._housekeeping_service: HousekeepingService | None = None

        self._discovery: DiscoveryResult | None = None
        self._preflight_rows: list[PreflightRow] = []
        self._validated_files: list[ValidatedFile] = []
        self._upload_jobs: list[UploadJob] = []
        self._summary = UploadSummary()
        self._audit_records: list[AuditRecord] = []
        self._active_thread: QThread | None = None
        self._active_worker: QObject | None = None
        self._validation_complete = False
        self._governance_complete = False
        self._resolution_results: list[AssetResolutionResult] = []
        self._ready_state = "IDLE"

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._header = DashboardHeader()
        root.addWidget(self._header)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        self._sidebar = Sidebar()
        self._sidebar.page_changed.connect(self._on_page_changed)
        self._sidebar.settings_button().clicked.connect(self._open_settings)
        body.addWidget(self._sidebar)

        self._stack = QStackedWidget()
        self._page_index: dict[str, int] = {}
        self._build_pages()
        self._housekeeping_page.start_audit.connect(self._start_housekeeping_audit)
        self._housekeeping_page.cancel_audit.connect(self._cancel_housekeeping_audit)
        self._housekeeping_page.open_reports_dir.connect(self._open_reports_folder)
        scroll_wrap = QScrollArea()
        scroll_wrap.setWidgetResizable(True)
        scroll_wrap.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll_wrap.setWidget(self._stack)
        body.addWidget(scroll_wrap, stretch=1)
        root.addLayout(body)

        self._load_initial_state()
        self._refresh_header()

    def _build_pages(self) -> None:
        self._housekeeping_page = HousekeepingPage()
        pages = [
            ("source", self._page_source()),
            ("catalogue", self._page_catalogue()),
            ("validation", self._page_validation()),
            ("preview", self._page_preview()),
            ("upload", self._page_upload()),
            ("reports", self._page_reports()),
            ("housekeeping", self._housekeeping_page),
        ]
        for key, widget in pages:
            self._page_index[key] = self._stack.count()
            self._stack.addWidget(widget)

    def _scroll_page(self, inner: QWidget) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(Theme.MARGIN, Theme.MARGIN, Theme.MARGIN, Theme.MARGIN)
        lay.setSpacing(Theme.MARGIN)
        lay.addWidget(inner)
        lay.addStretch()
        return page

    def _page_source(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(Theme.MARGIN, Theme.MARGIN, Theme.MARGIN, Theme.MARGIN)
        layout.setSpacing(Theme.MARGIN)

        source_card = Card(
            "Source Files",
            "Select the local folder containing replacement media. Drag-and-drop supported.",
        )
        preset_row = QHBoxLayout()
        preset_row.addWidget(QLabel("Preset"))
        self._preset_combo = QComboBox()
        self._preset_combo.currentTextChanged.connect(self._on_preset_selected)
        preset_row.addWidget(self._preset_combo, stretch=1)
        manage_btn = QPushButton("Manage…")
        manage_btn.clicked.connect(self._manage_presets_from_source)
        preset_row.addWidget(manage_btn)
        source_card.add_layout(preset_row)

        self._source_path = PathDropLineEdit()
        self._source_path.path_changed.connect(self._on_source_path_changed)
        source_card.add_widget(self._source_path)

        self._source_status = QLabel("No replacement source folder selected.")
        self._source_status.setWordWrap(True)
        self._source_status.setStyleSheet(f"color: {Theme.ERROR}; font-weight: 500;")
        source_card.add_widget(self._source_status)

        scan_row = QHBoxLayout()
        self._scan_btn = QPushButton("Scan Folder")
        self._scan_btn.setProperty("class", "primary")
        self._scan_btn.setMinimumHeight(44)
        self._scan_btn.clicked.connect(self._start_scan)
        scan_row.addWidget(self._scan_btn)
        scan_row.addStretch()
        source_card.add_layout(scan_row)
        layout.addWidget(source_card)

        direct_card = Card(
            "Direct ENGP / CFX Replacement",
            "Replace one or both paired assets in a single operation with Iconik verification.",
        )
        engp_row = QHBoxLayout()
        engp_row.addWidget(QLabel("ENGP Replacement File:"))
        self._engp_file_path = FileBrowseLineEdit(file_filter="ENGP masters (*_ENGP.mp4)")
        self._engp_file_path.path_changed.connect(self._on_engp_file_changed)
        engp_row.addWidget(self._engp_file_path, stretch=1)
        direct_card.add_layout(engp_row)

        cfx_row = QHBoxLayout()
        cfx_row.addWidget(QLabel("CFX Replacement File:"))
        self._cfx_file_path = FileBrowseLineEdit(file_filter="CFX video (*_CFX.mp4)")
        self._cfx_file_path.path_changed.connect(self._on_cfx_file_changed)
        cfx_row.addWidget(self._cfx_file_path, stretch=1)
        direct_card.add_layout(cfx_row)

        self._preserve_iconik_ids = QCheckBox("Preserve Existing Iconik Asset IDs (Recommended)")
        self._preserve_iconik_ids.setChecked(self._settings.preserve_iconik_asset_ids())
        self._preserve_iconik_ids.setToolTip(
            "When enabled, the application attempts to replace media inside the "
            "existing Iconik asset/file set before falling back to storage scan replacement."
        )
        self._preserve_iconik_ids.stateChanged.connect(self._save_preserve_iconik_pref)
        direct_card.add_widget(self._preserve_iconik_ids)

        direct_btn_row = QHBoxLayout()
        self._dual_replace_btn = QPushButton("Replace Selected Files")
        self._dual_replace_btn.setProperty("class", "primary")
        self._dual_replace_btn.setMinimumHeight(44)
        self._dual_replace_btn.clicked.connect(self._start_dual_replacement)
        direct_btn_row.addWidget(self._dual_replace_btn)
        direct_btn_row.addStretch()
        direct_card.add_layout(direct_btn_row)

        self._dual_replace_status = QLabel("Select ENGP and/or CFX replacement files (both optional).")
        self._dual_replace_status.setWordWrap(True)
        self._dual_replace_status.setProperty("class", "muted")
        direct_card.add_widget(self._dual_replace_status)

        self._resolution_governance_label = QLabel("Asset resolution: not yet run.")
        self._resolution_governance_label.setWordWrap(True)
        self._resolution_governance_label.setProperty("class", "muted")
        direct_card.add_widget(self._resolution_governance_label)
        layout.addWidget(direct_card)

        sanit_card = Card(
            "Filename Sanitisation",
            "Review how filenames will be cleaned before upload.",
        )
        opts = self._settings.sanitisation_options()
        grid = QGridLayout()
        self._opt_apple = QCheckBox("Remove AppleDouble files (._*)")
        self._opt_apple.setChecked(opts.remove_apple_double)
        self._opt_trail = QCheckBox("Remove trailing spaces")
        self._opt_trail.setChecked(opts.remove_trailing_spaces)
        self._opt_dup = QCheckBox("Remove duplicate spaces")
        self._opt_dup.setChecked(opts.remove_duplicate_spaces)
        self._opt_inv = QCheckBox("Remove invisible characters")
        self._opt_inv.setChecked(opts.remove_invisible_characters)
        self._opt_ext = QCheckBox("Standardise extension case (.MP4 → .mp4)")
        self._opt_ext.setChecked(opts.standardise_extension_case)
        checks = [self._opt_apple, self._opt_trail, self._opt_dup, self._opt_inv, self._opt_ext]
        for i, cb in enumerate(checks):
            cb.stateChanged.connect(self._save_sanitisation_options)
            grid.addWidget(cb, i // 2, i % 2)
        sanit_card.add_layout(grid)

        self._sanitise_table = DataTable(SANITISE_COLUMNS, mono_columns={1, 2})
        sanit_card.add_widget(self._sanitise_table)
        layout.addWidget(sanit_card)
        layout.addStretch()
        return page

    def _page_catalogue(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(Theme.MARGIN, Theme.MARGIN, Theme.MARGIN, Theme.MARGIN)

        card = Card(
            "Catalogue Destination",
            "Choose the production library. Files are validated and uploaded under this S3 prefix.",
        )
        form = QFormLayout()
        form.setSpacing(14)
        self._catalogue_combo = QComboBox()
        self._catalogue_combo.setMinimumHeight(40)
        for name in self._catalogues.names():
            self._catalogue_combo.addItem(name)
        self._catalogue_combo.currentTextChanged.connect(self._on_catalogue_changed)
        form.addRow("Catalogue:", self._catalogue_combo)

        self._s3_path_label = QLabel()
        self._s3_path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._s3_path_label.setWordWrap(True)
        self._s3_path_label.setStyleSheet(
            f"font-family: {Theme.FONT_MONO}; font-size: 12px; color: {Theme.TEXT_SECONDARY};"
        )
        form.addRow("S3 path:", self._s3_path_label)

        self._test_s3_btn = QPushButton("Test S3 Connection")
        self._test_s3_btn.setProperty("class", "primary")
        self._test_s3_btn.clicked.connect(self._test_s3)
        form.addRow("", self._test_s3_btn)
        card.add_layout(form)
        layout.addWidget(card)
        layout.addStretch()
        return page

    def _page_validation(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(Theme.MARGIN, Theme.MARGIN, Theme.MARGIN, Theme.MARGIN)

        card = Card(
            "Pre-flight Validation",
            "Each file is checked against S3, then Iconik asset governance for upload candidates.",
        )
        row = QHBoxLayout()
        self._validate_btn = QPushButton("Run Pre-flight Validation")
        self._validate_btn.setProperty("class", "primary")
        self._validate_btn.setMinimumHeight(44)
        self._validate_btn.clicked.connect(self._start_preflight)
        row.addWidget(self._validate_btn)
        row.addStretch()
        card.add_layout(row)

        self._preflight_table = DataTable(PREFLIGHT_COLUMNS, mono_columns={1, 2})
        card.add_widget(self._preflight_table)
        layout.addWidget(card)
        return page

    def _page_preview(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(Theme.MARGIN, Theme.MARGIN, Theme.MARGIN, Theme.MARGIN)

        card = Card(
            "Upload Preview",
            "Review the replacement plan before starting the upload.",
        )
        stats = QGridLayout()
        stats.setSpacing(16)
        self._stat_gov_verified = StatCard("Governance Verified", "—", accent=Theme.SUCCESS)
        self._stat_gov_not_found = StatCard("Governance Not Found", "—", accent=Theme.WARNING)
        self._stat_gov_duplicate = StatCard("Governance Duplicate", "—", accent=Theme.WARNING)
        self._stat_gov_errors = StatCard("Governance Errors", "—", accent=Theme.ERROR)
        self._stat_s3_missing = StatCard("S3 Missing", "—", accent=Theme.WARNING)
        self._stat_ready = StatCard("Ready To Replace", "—", accent=Theme.SUCCESS)
        stat_cards = (
            self._stat_gov_verified,
            self._stat_gov_not_found,
            self._stat_gov_duplicate,
            self._stat_gov_errors,
            self._stat_s3_missing,
            self._stat_ready,
        )
        for index, stat_card in enumerate(stat_cards):
            stat_card.setMinimumWidth(160)
            stats.addWidget(stat_card, index // 3, index % 3)
        card.add_layout(stats)

        self._preview_detail = QLabel(
            "Run a folder scan and pre-flight validation to see the upload plan."
        )
        self._preview_detail.setWordWrap(True)
        self._preview_detail.setProperty("class", "muted")
        card.add_widget(self._preview_detail)

        go_row = QHBoxLayout()
        self._go_upload_btn = QPushButton("Continue to Upload →")
        self._go_upload_btn.setProperty("class", "primary")
        self._go_upload_btn.clicked.connect(lambda: self._sidebar.go_to("upload"))
        go_row.addStretch()
        go_row.addWidget(self._go_upload_btn)
        card.add_layout(go_row)
        layout.addWidget(card)
        layout.addStretch()
        return page

    def _page_upload(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(Theme.MARGIN, Theme.MARGIN, Theme.MARGIN, Theme.MARGIN)

        card = Card("Upload Execution", "Threaded S3 replacements with live progress.")
        btn_row = QHBoxLayout()
        self._upload_btn = QPushButton("Start Upload")
        self._upload_btn.setProperty("class", "primary")
        self._upload_btn.setMinimumHeight(48)
        self._upload_btn.clicked.connect(self._start_upload)
        self._cancel_upload_btn = QPushButton("Cancel")
        self._cancel_upload_btn.setProperty("class", "danger")
        self._cancel_upload_btn.setEnabled(False)
        self._cancel_upload_btn.clicked.connect(self._cancel_upload)
        btn_row.addWidget(self._upload_btn)
        btn_row.addWidget(self._cancel_upload_btn)
        btn_row.addStretch()
        card.add_layout(btn_row)

        self._upload_panel = UploadProgressPanel()
        card.add_widget(self._upload_panel)
        layout.addWidget(card)
        layout.addStretch()
        return page

    def _page_reports(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(Theme.MARGIN, Theme.MARGIN, Theme.MARGIN, Theme.MARGIN)

        card = Card("Audit Reports", "CSV and Excel exports for every upload run.")
        info = QLabel(
            f"Reports directory:\n{REPORTS_DIR}\n\n"
            "Latest files: replacement_report.csv, replacement_audit.xlsx"
        )
        info.setWordWrap(True)
        card.add_widget(info)

        open_btn = QPushButton("Open Reports Folder")
        open_btn.setProperty("class", "primary")
        open_btn.clicked.connect(self._open_reports_folder)
        card.add_widget(open_btn)

        self._last_report_label = QLabel("Last report: —")
        self._last_report_label.setWordWrap(True)
        self._last_report_label.setStyleSheet(
            f"font-family: {Theme.FONT_MONO}; font-size: 11px; color: {Theme.TEXT_SECONDARY};"
        )
        card.add_widget(self._last_report_label)
        layout.addWidget(card)
        layout.addStretch()
        return page

    def _build_s3_client(self) -> S3Service:
        aws = self._settings.aws
        return S3Service(
            region=aws.get("aws_region") or str(self._settings.user.get("aws_region", "eu-west-1")),
            access_key_id=aws.get("aws_access_key_id", ""),
            secret_access_key=aws.get("aws_secret_access_key", ""),
            session_token=aws.get("aws_session_token", ""),
        )

    def _aws_profile_label(self) -> str:
        try:
            cat = self._resolve_catalogue()
            return cat.location.bucket
        except ValueError:
            return "—"

    def _refresh_header(self) -> None:
        files = self._discovery.media_count if self._discovery else 0
        if self._summary.files_scanned:
            files = self._summary.files_scanned
        self._header.update_status(
            aws_profile=self._aws_profile_label(),
            catalogue=self._catalogue_combo.currentText() or "—",
            files_count=files,
            ready_state=self._ready_state,
        )

    def _on_page_changed(self, key: str) -> None:
        if key in HOUSEKEEPING_KEYS:
            self._stack.setCurrentIndex(self._page_index["housekeeping"])
            self._housekeeping_page.go_to_tab(key)
            return
        idx = self._page_index.get(key, 0)
        self._stack.setCurrentIndex(idx)

    def _start_housekeeping_audit(self) -> None:
        if self._active_thread is not None:
            return
        iconik = self._build_iconik_service()
        if not iconik.configured():
            QMessageBox.warning(
                self,
                "Iconik Not Configured",
                "Configure Iconik App ID, Auth Token, and Storage ID in Preferences "
                "before running a housekeeping audit.",
            )
            return

        self._housekeeping_service = HousekeepingService(iconik)
        self._housekeeping_page.set_busy(True)
        self._ready_state = "SCANNING"
        self._refresh_header()

        worker = HousekeepingWorker(self._housekeeping_service, self._housekeeping_reports)
        thread = run_in_thread(worker, self)
        worker.progress.connect(
            self._housekeeping_page.update_progress,
            Qt.ConnectionType.QueuedConnection,
        )
        worker.finished.connect(
            self._on_housekeeping_finished,
            Qt.ConnectionType.QueuedConnection,
        )
        worker.finished.connect(thread.quit)
        worker.failed.connect(
            lambda e: self._on_worker_failed(e, "Housekeeping"),
            Qt.ConnectionType.QueuedConnection,
        )
        worker.failed.connect(thread.quit)
        thread.finished.connect(self._clear_active_worker)
        thread.finished.connect(thread.deleteLater)
        self._active_worker = worker
        self._active_thread = thread
        thread.start()

    def _cancel_housekeeping_audit(self) -> None:
        if self._housekeeping_service:
            self._housekeeping_service.cancel()

    @Slot(object)
    def _on_housekeeping_finished(self, payload: object) -> None:
        result, paths = payload
        self._housekeeping_page.set_busy(False)
        self._housekeeping_page.apply_result(result, paths)
        self._active_thread = None
        self._active_worker = None
        self._ready_state = "READY" if not result.error and not result.warnings else "WARNING"
        self._refresh_header()
        if result.error:
            QMessageBox.critical(self, "Housekeeping Audit", result.error)
        elif result.cancelled:
            QMessageBox.information(
                self,
                "Housekeeping Audit",
                f"Audit cancelled. Partial scan: {result.total_scanned} asset(s).",
            )
        else:
            warning_text = ""
            if result.warnings:
                warning_text = "\n\nWarnings:\n• " + "\n• ".join(result.warnings)
            scan = result.scan_summary
            duration_text = "n/a"
            if scan and scan.scan_duration_seconds:
                duration_text = f"{scan.scan_duration_seconds:.1f}s"
            duplicates_found = (
                len(result.duplicate_filename_groups)
                + len(result.duplicate_storage_groups)
                + len(result.duplicate_title_groups)
            )
            paths_text = "\n".join(f"  • {path}" for path in paths.values()) if paths else "  (none)"
            QMessageBox.information(
                self,
                "Housekeeping Audit",
                f"Scan duration: {duration_text}\n"
                f"Assets scanned: {result.total_scanned}\n"
                f"Duplicates found: {duplicates_found}\n"
                f"  — Filename groups: {len(result.duplicate_filename_groups)}\n"
                f"  — Storage groups: {len(result.duplicate_storage_groups)}\n"
                f"  — Title groups: {len(result.duplicate_title_groups)}\n"
                f"Orphan assets: {len(result.orphan_assets)}"
                f"{warning_text}\n\n"
                f"Reports:\n{paths_text}",
            )

    def _open_settings(self) -> None:
        dlg = SettingsDialog(self._settings, on_aws_saved=self._reload_aws, parent=self)
        dlg.exec()
        self._reload_presets()

    def _reload_aws(self) -> None:
        self._s3 = self._build_s3_client()
        self._preflight = PreflightValidator(self._s3)
        self._upload_engine = UploadEngine(
            self._s3,
            max_workers=self._settings.upload_max_workers(),
        )
        self._refresh_header()
        QMessageBox.information(self, "AWS", "Credentials updated.")

    def _load_initial_state(self) -> None:
        self._reload_presets()
        folder = self._settings.source_folder()
        if folder and folder != SELECT_FOLDER_PLACEHOLDER:
            self._source_path.set_path(folder)
        last = self._settings.last_catalogue()
        idx = self._catalogue_combo.findText(last)
        if idx >= 0:
            self._catalogue_combo.setCurrentIndex(idx)
        self._on_catalogue_changed(self._catalogue_combo.currentText())
        engp = self._settings.replacement_engp_file()
        cfx = self._settings.replacement_cfx_file()
        if engp:
            self._engp_file_path.set_path(engp)
        if cfx:
            self._cfx_file_path.set_path(cfx)
        self._refresh_dual_replace_status()
        self._refresh_source_status()
        self._update_action_states()

    def _reload_presets(self) -> None:
        self._preset_combo.blockSignals(True)
        self._preset_combo.clear()
        self._preset_combo.addItem("(none)")
        for name in sorted(self._settings.presets.keys()):
            self._preset_combo.addItem(name)
        self._preset_combo.blockSignals(False)

    def _current_sanitisation_options(self) -> SanitisationOptions:
        return SanitisationOptions(
            remove_apple_double=self._opt_apple.isChecked(),
            remove_trailing_spaces=self._opt_trail.isChecked(),
            remove_duplicate_spaces=self._opt_dup.isChecked(),
            remove_invisible_characters=self._opt_inv.isChecked(),
            standardise_extension_case=self._opt_ext.isChecked(),
        )

    def _save_sanitisation_options(self) -> None:
        self._settings.set_sanitisation_options(self._current_sanitisation_options())

    def _save_preserve_iconik_pref(self) -> None:
        self._settings.set_preserve_iconik_asset_ids(self._preserve_iconik_ids.isChecked())

    def _manage_presets_from_source(self) -> None:
        from gui.preset_dialog import PresetManagerDialog

        dlg = PresetManagerDialog(self._settings.presets, self)
        if dlg.exec():
            self._settings.save_presets(dlg.presets())
            self._reload_presets()

    def _on_preset_selected(self, name: str) -> None:
        if name == "(none)" or not name:
            return
        path = self._settings.presets.get(name, "")
        if path and path != SELECT_FOLDER_PLACEHOLDER:
            self._source_path.set_path(path)

    def _on_source_path_changed(self, path: str) -> None:
        self._settings.set_source_folder(path)
        self._refresh_source_status()
        self._update_action_states()

    def _refresh_source_status(self) -> None:
        if not self._settings.is_valid_source_folder():
            self._source_status.setText("No replacement source folder selected.")
            self._source_status.setStyleSheet(f"color: {Theme.ERROR}; font-weight: 500;")
            self._ready_state = "IDLE"
        else:
            self._source_status.setText(f"✓  {self._source_path.path()}")
            self._source_status.setStyleSheet(f"color: {Theme.SUCCESS}; font-weight: 500;")
            self._ready_state = "READY" if self._upload_jobs else "IDLE"
        self._refresh_header()

    def _build_iconik_service(self) -> IconikVerificationService:
        return IconikVerificationService(
            base_url=self._settings.iconik_base_url(),
            app_id=self._settings.iconik_app_id(),
            auth_token=self._settings.iconik_auth_token(),
            storage_id=self._settings.iconik_storage_id(),
        )

    def _on_engp_file_changed(self, path: str) -> None:
        self._settings.set_replacement_engp_file(path)
        self._refresh_dual_replace_status()
        self._update_action_states()

    def _on_cfx_file_changed(self, path: str) -> None:
        self._settings.set_replacement_cfx_file(path)
        self._refresh_dual_replace_status()
        self._update_action_states()

    def _refresh_dual_replace_status(self) -> None:
        engp = self._engp_file_path.path()
        cfx = self._cfx_file_path.path()
        if not engp and not cfx:
            self._dual_replace_status.setText(
                "Select ENGP and/or CFX replacement files (both optional)."
            )
            return
        parts = []
        if engp:
            parts.append(f"ENGP: {Path(engp).name}")
        if cfx:
            parts.append(f"CFX: {Path(cfx).name}")
        self._dual_replace_status.setText(" · ".join(parts))

    def _update_action_states(self) -> None:
        valid = self._settings.is_valid_source_folder()
        busy = self._active_thread is not None
        dual_ready = bool(self._engp_file_path.path().strip() or self._cfx_file_path.path().strip())
        self._dual_replace_btn.setEnabled(dual_ready and not busy)
        self._scan_btn.setEnabled(valid and not busy)
        self._validate_btn.setEnabled(
            valid and self._discovery is not None and not busy
        )
        can_upload = (
            self._validation_complete
            and self._governance_complete
            and all_replace_candidates_verified(self._preflight_rows)
            and bool(self._upload_jobs)
            and any(j.action == UploadAction.REPLACE for j in self._upload_jobs)
        )
        self._upload_btn.setEnabled(can_upload and not busy)
        self._go_upload_btn.setEnabled(
            self._validation_complete and self._governance_complete and not busy
        )

    def _on_catalogue_changed(self, name: str) -> None:
        self._settings.set_last_catalogue(name)
        try:
            cat = self._catalogues.resolve(name, custom_s3_path=self._settings.custom_s3_path())
            self._s3_path_label.setText(cat.s3_path)
        except ValueError as exc:
            self._s3_path_label.setText(str(exc))
        self._refresh_header()

    def _resolve_catalogue(self):
        return self._catalogues.resolve(
            self._catalogue_combo.currentText(),
            custom_s3_path=self._settings.custom_s3_path(),
        )

    def _start_scan(self) -> None:
        source = Path(self._source_path.path())
        self._validation_complete = False
        self._validated_files = []
        self._scan_btn.setEnabled(False)
        self._ready_state = "SCANNING"
        self._refresh_header()
        worker = ScanWorker(source, self._current_sanitisation_options())
        thread = run_in_thread(worker, self)
        worker.finished.connect(
            self._on_scan_finished,
            Qt.ConnectionType.QueuedConnection,
        )
        worker.finished.connect(thread.quit)
        worker.failed.connect(
            lambda e: self._on_worker_failed(e, "Scan"),
            Qt.ConnectionType.QueuedConnection,
        )
        worker.failed.connect(thread.quit)
        thread.finished.connect(self._clear_active_worker)
        thread.finished.connect(thread.deleteLater)
        self._active_worker = worker
        self._active_thread = thread
        thread.start()

    @Slot(object)
    def _on_scan_finished(self, result: DiscoveryResult) -> None:
        self._discovery = result
        self._populate_sanitise_table(result)
        self._preflight_rows = []
        self._validated_files = []
        self._upload_jobs = []
        self._resolution_results = []
        self._validation_complete = False
        self._governance_complete = False
        self._preflight_table.clear()
        self._summary = UploadSummary(files_scanned=result.media_count)
        self._update_preview(self._summary)
        self._active_thread = None
        self._active_worker = None
        self._update_action_states()
        self._refresh_header()
        self._sidebar.go_to("validation")
        # Chain: scan → pre-flight validation → preview (no manual step required)
        QTimer.singleShot(0, self._start_preflight)

    def _clear_active_worker(self) -> None:
        self._active_thread = None
        self._active_worker = None
        self._update_action_states()

    def _populate_sanitise_table(self, result: DiscoveryResult) -> None:
        self._sanitise_table.clear()
        for item in result.files:
            if not item.clean_filename and not item.excluded:
                continue
            issues = ", ".join(x.value for x in item.issues) if item.issues else "—"
            icon = _status_icon_for_sanitise(item.excluded, item.issues)
            self._sanitise_table.append_row(
                [
                    "",
                    item.original_filename,
                    item.clean_filename or "(excluded)",
                    issues,
                ],
                status_icon=icon,
            )

    def _start_preflight(self) -> None:
        if not self._discovery:
            return
        if self._active_thread is not None:
            return
        try:
            catalogue = self._resolve_catalogue()
        except ValueError as exc:
            QMessageBox.warning(self, "Catalogue", str(exc))
            return

        self._validation_complete = False
        self._governance_complete = False
        self._validate_btn.setEnabled(False)
        self._go_upload_btn.setEnabled(False)
        self._ready_state = "VALIDATING"
        self._refresh_header()
        worker = PreflightWorker(
            self._preflight,
            self._discovery,
            catalogue,
            replace_existing_only=self._settings.safety_replace_existing_only(),
        )
        thread = run_in_thread(worker, self)
        worker.finished.connect(
            self._on_preflight_finished,
            Qt.ConnectionType.QueuedConnection,
        )
        worker.finished.connect(thread.quit)
        worker.failed.connect(
            lambda e: self._on_worker_failed(e, "Pre-flight"),
            Qt.ConnectionType.QueuedConnection,
        )
        worker.failed.connect(thread.quit)
        thread.finished.connect(self._clear_active_worker)
        thread.finished.connect(thread.deleteLater)
        self._active_worker = worker
        self._active_thread = thread
        thread.start()

    @Slot(object)
    def _on_preflight_finished(self, payload: ValidationResult) -> None:
        self._active_thread = None
        self._active_worker = None
        self._apply_validation_result(payload)
        self._ready_state = "VALIDATING"
        self._refresh_header()
        QTimer.singleShot(0, lambda: self._start_governance(payload))

    def _start_governance(self, preflight_payload: ValidationResult) -> None:
        if not self._discovery:
            return
        if self._active_thread is not None:
            return
        try:
            catalogue = self._resolve_catalogue()
        except ValueError as exc:
            QMessageBox.warning(self, "Catalogue", str(exc))
            return

        iconik = self._build_iconik_service()
        self._ready_state = "VALIDATING"
        self._refresh_header()
        worker = GovernanceWorker(
            rows=list(preflight_payload.rows),
            discovery=self._discovery,
            catalogue=catalogue,
            iconik=iconik,
            s3=self._s3,
            preflight_payload=preflight_payload,
        )
        thread = run_in_thread(worker, self)
        worker.finished.connect(
            self._on_governance_finished,
            Qt.ConnectionType.QueuedConnection,
        )
        worker.finished.connect(thread.quit)
        worker.failed.connect(
            lambda e: self._on_worker_failed(e, "Governance"),
            Qt.ConnectionType.QueuedConnection,
        )
        worker.failed.connect(thread.quit)
        thread.finished.connect(self._clear_active_worker)
        thread.finished.connect(thread.deleteLater)
        self._active_worker = worker
        self._active_thread = thread
        thread.start()

    @Slot(object)
    def _on_governance_finished(self, payload: ValidationResult) -> None:
        self._apply_validation_result(payload)
        self._active_thread = None
        self._active_worker = None
        self._validation_complete = True
        self._governance_complete = payload.governance_complete

        duplicates = [
            r for r in payload.resolution_results if r.status == GovernanceStatus.DUPLICATE
        ]
        if duplicates:
            DuplicateResolutionDialog(duplicates, self).exec()

        if payload.summary.governance_blocked:
            self._ready_state = "WARNING"
        elif payload.summary.validation_errors:
            self._ready_state = "WARNING"
        elif payload.summary.files_to_replace:
            self._ready_state = "READY"
        else:
            self._ready_state = "WARNING"

        self._validate_btn.setEnabled(True)
        self._update_action_states()
        self._refresh_header()
        self._sidebar.go_to("preview")

        blocked_msg = ""
        if payload.summary.governance_blocked:
            blocked_msg = (
                f"\nGovernance blocked: {payload.summary.governance_blocked} "
                f"(upload disabled until all ready candidates are VERIFIED)"
            )

        gov = compute_governance_stats(payload.rows)
        QMessageBox.information(
            self,
            "Validation Complete",
            f"Scanned: {payload.summary.files_scanned}\n"
            f"Governance verified: {gov.verified}\n"
            f"Governance not found: {gov.not_found}\n"
            f"Governance duplicate: {gov.duplicate}\n"
            f"Governance errors: {gov.errors}\n"
            f"S3 missing: {gov.s3_missing}\n"
            f"Ready to replace: {gov.ready_to_replace}\n"
            f"Preflight errors: {payload.summary.validation_errors}"
            f"{blocked_msg}",
        )

    def _apply_validation_result(self, payload: ValidationResult) -> None:
        """Single update path: validation table, validated_files, preview, upload queue."""
        self._preflight_rows = payload.rows
        self._summary = payload.summary
        self._validated_files = payload.validated_files
        self._upload_jobs = payload.upload_jobs
        self._resolution_results = payload.resolution_results
        self._governance_complete = payload.governance_complete
        self._populate_preflight_table(payload.rows)
        self._update_preview(payload.summary)

    def _populate_preflight_table(self, rows: list[PreflightRow]) -> None:
        self._preflight_table.clear()
        for row in rows:
            d = row.discovered
            if not d.clean_filename and not d.excluded:
                continue
            icon = _status_icon_for_preflight(row)
            cat_s3 = "YES" if row.catalogue_s3_exists else "NO"
            resolved_s3 = "YES" if row.s3_exists else "NO"
            self._preflight_table.append_row(
                [
                    "",
                    d.original_filename,
                    d.clean_filename or "—",
                    cat_s3,
                    row.resolved_iconik_s3_key or "—",
                    resolved_s3,
                    _format_bytes(d.size_bytes),
                    _format_bytes(row.s3_size) if row.s3_size is not None else "—",
                    row.action,
                    row.governance_status or "—",
                    row.resolved_asset_id or "—",
                    row.resolved_file_set_id or "—",
                    row.resolution_method or "—",
                    row.metadata_status or "—",
                    row.governance_warnings or "—",
                    row.governance_message or row.status_message,
                ],
                status_icon=icon,
            )

    def _update_preview(self, summary: UploadSummary) -> None:
        gov = compute_governance_stats(self._preflight_rows)
        self._stat_gov_verified.set_value(str(gov.verified))
        self._stat_gov_not_found.set_value(str(gov.not_found))
        self._stat_gov_duplicate.set_value(str(gov.duplicate))
        self._stat_gov_errors.set_value(str(gov.errors))
        self._stat_s3_missing.set_value(str(gov.s3_missing))
        self._stat_ready.set_value(str(gov.ready_to_replace))

        if gov.ready_to_replace:
            self._preview_detail.setText(
                f"You are about to replace {gov.ready_to_replace} governed file(s) in "
                f"{self._catalogue_combo.currentText()}. "
                f"Governance verified: {gov.verified}; S3 missing (resolved key): {gov.s3_missing}. "
                "Review the validation table before uploading."
            )
        elif gov.errors or gov.not_found or gov.duplicate:
            self._preview_detail.setText(
                f"Governance — verified: {gov.verified}, not found: {gov.not_found}, "
                f"duplicate: {gov.duplicate}, errors: {gov.errors}. "
                f"S3 missing (resolved key): {gov.s3_missing}. "
                "Upload is blocked until ready candidates are VERIFIED."
            )
        else:
            self._preview_detail.setText(
                "No files are ready to replace. Run scan and validation to see governance results."
            )

    def _start_dual_replacement(self) -> None:
        engp = self._engp_file_path.path().strip()
        cfx = self._cfx_file_path.path().strip()
        if not engp and not cfx:
            QMessageBox.warning(self, "Replacement", "Select at least one file.")
            return
        try:
            catalogue = self._resolve_catalogue()
        except ValueError as exc:
            QMessageBox.warning(self, "Catalogue", str(exc))
            return

        iconik = self._build_iconik_service()
        if not iconik.configured():
            QMessageBox.warning(
                self,
                "Iconik",
                "Configure Iconik App ID, Auth Token, and Storage ID in Preferences.",
            )
            return

        service = DualReplacementService(self._s3, iconik)
        try:
            targets = service.build_targets(
                engp_path=engp,
                cfx_path=cfx,
                catalogue=catalogue,
            )
            resolutions = service.resolve_targets(targets, catalogue)
        except Exception as exc:
            QMessageBox.critical(self, "Asset Resolution", str(exc))
            return

        self._update_resolution_governance_display(resolutions)

        duplicates = [r for r in resolutions if r.status == GovernanceStatus.DUPLICATE]
        if duplicates:
            DuplicateResolutionDialog(duplicates, self).exec()
            return

        non_verified = [r for r in resolutions if r.status != GovernanceStatus.VERIFIED]
        if non_verified:
            lines = "\n".join(
                f"{r.local_filename}: {r.status.value} — {r.message}" for r in non_verified
            )
            QMessageBox.critical(
                self,
                "Asset Resolution Failed",
                "Replacement cannot proceed until all targets are VERIFIED.\n\n" + lines,
            )
            return

        preview = ResolutionPreviewDialog(resolutions, parent=self)
        if preview.exec() != QDialog.DialogCode.Accepted or not preview.confirmed:
            return

        self._dual_replace_btn.setEnabled(False)
        self._ready_state = "UPLOADING"
        self._refresh_header()
        worker = DualReplacementWorker(
            service,
            engp_path=engp,
            cfx_path=cfx,
            catalogue=catalogue,
            resolutions=resolutions,
            preserve_asset_ids=self._preserve_iconik_ids.isChecked(),
        )
        thread = run_in_thread(worker, self)
        worker.log_line.connect(
            lambda msg: logger.info(msg),
            Qt.ConnectionType.QueuedConnection,
        )
        worker.finished.connect(
            self._on_dual_replacement_finished,
            Qt.ConnectionType.QueuedConnection,
        )
        worker.finished.connect(thread.quit)
        worker.failed.connect(
            lambda e: self._on_worker_failed(e, "Replacement"),
            Qt.ConnectionType.QueuedConnection,
        )
        worker.failed.connect(thread.quit)
        thread.finished.connect(self._clear_active_worker)
        thread.finished.connect(thread.deleteLater)
        self._active_worker = worker
        self._active_thread = thread
        thread.start()

    def _update_resolution_governance_display(self, resolutions: list[AssetResolutionResult]) -> None:
        lines: list[str] = []
        for result in resolutions:
            if result.status == GovernanceStatus.VERIFIED and result.target:
                target = result.target
                warning_text = ""
                if result.governance_warnings:
                    warning_text = f" | warnings: {', '.join(result.governance_warnings)}"
                metadata_text = ""
                if target.metadata_status not in ("", "AVAILABLE"):
                    metadata_text = f" | metadata: {target.metadata_status}"
                lines.append(
                    f"{result.asset_type.value} {result.local_filename}: "
                    f"{result.status.value} | asset {target.asset_id} | "
                    f"file set {target.file_set_id} | {target.iconik_s3_key} | "
                    f"{result.resolution_method}{warning_text}{metadata_text}"
                )
            else:
                lines.append(
                    f"{result.asset_type.value} {result.local_filename}: "
                    f"{result.status.value} — {result.message}"
                )
        self._resolution_governance_label.setText(
            "Asset resolution:\n" + "\n".join(lines) if lines else "Asset resolution: no targets."
        )

    @Slot(object)
    def _on_dual_replacement_finished(self, outcome: DualReplacementOutcome | list) -> None:
        if isinstance(outcome, DualReplacementOutcome):
            records = outcome.records
            batch_failed = outcome.batch_failed
            failure_records = outcome.failure_records
        else:
            records = outcome
            batch_failed = False
            failure_records = []

        csv_path = xlsx_path = None
        if records:
            csv_path, xlsx_path = self._reports.write_verification_reports(records)
            self._last_report_label.setText(
                f"Last verification audit:\n{csv_path}\n{xlsx_path}"
            )
        if failure_records:
            fail_csv, fail_xlsx = self._reports.write_failure_reports(failure_records)
            self._last_report_label.setText(
                f"BATCH FAILED — see failure report:\n{fail_csv}\n{fail_xlsx}"
            )

        self._ready_state = "ERROR" if batch_failed else "READY"
        self._update_action_states()
        self._refresh_header()
        self._sidebar.go_to("reports")

        if batch_failed:
            QMessageBox.critical(
                self,
                "BATCH FAILED",
                "Asset ID preservation failed.\nReview replacement_failure.xlsx",
            )
            return

        fails = sum(1 for r in records if getattr(r, "status", "") == "FAIL")
        warns = sum(1 for r in records if getattr(r, "status", "") == "WARNING")
        if fails:
            QMessageBox.warning(
                self,
                "Replacement Complete",
                f"{fails} verification FAIL(s). See replacement_audit.xlsx",
            )
        elif warns:
            QMessageBox.information(
                self,
                "Replacement Complete",
                f"Upload complete with {warns} WARNING(s). See replacement_audit.xlsx",
            )
        elif records:
            QMessageBox.information(
                self,
                "Replacement Complete",
                "ENGP/CFX replacement verified. Audit report saved.",
            )
        else:
            QMessageBox.information(
                self,
                "Replacement Complete",
                "S3 replacement complete. No Iconik assets matched for verification.",
            )

    def _start_upload(self) -> None:
        if not self._upload_jobs:
            return
        if not self._governance_complete:
            QMessageBox.warning(
                self,
                "Governance Required",
                "Iconik governance has not completed. Run validation before uploading.",
            )
            return
        if not all_replace_candidates_verified(self._preflight_rows):
            QMessageBox.critical(
                self,
                "Upload Blocked",
                "Upload is blocked: not all governance-ready candidates are "
                "GovernanceStatus.VERIFIED.\n\n"
                "Resolve NOT_FOUND, DUPLICATE, or other governance failures first.",
            )
            return
        try:
            catalogue = self._resolve_catalogue()
        except ValueError as exc:
            QMessageBox.warning(self, "Catalogue", str(exc))
            return

        verified_resolutions = [
            r
            for r in self._resolution_results
            if r.status == GovernanceStatus.VERIFIED and r.target
        ]
        if not verified_resolutions:
            QMessageBox.warning(self, "Upload", "No governed assets are ready to upload.")
            return

        preview = ResolutionPreviewDialog(
            verified_resolutions,
            parent=self,
            window_title="Confirm Bulk Upload Governance",
            proceed_label="Proceed with Upload",
            intro_text=(
                "Review governed Iconik asset bindings before S3 upload. "
                "Only VERIFIED assets will be uploaded."
            ),
        )
        if preview.exec() != QDialog.DialogCode.Accepted or not preview.confirmed:
            return

        replace_count = sum(1 for j in self._upload_jobs if j.action == UploadAction.REPLACE)
        reply = QMessageBox.question(
            self,
            "Confirm Upload",
            f"Replace {replace_count} existing object(s) in S3?\n\n"
            "Iconik assets and metadata are not modified — only S3 object bytes are overwritten.",
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self._upload_btn.setEnabled(False)
        self._cancel_upload_btn.setEnabled(True)
        self._ready_state = "UPLOADING"
        self._refresh_header()
        self._upload_panel.reset(replace_count)

        worker = UploadWorker(self._upload_engine, self._upload_jobs, catalogue)
        thread = run_in_thread(worker, self)
        worker.progress.connect(
            self._on_upload_progress,
            Qt.ConnectionType.QueuedConnection,
        )
        worker.finished.connect(
            self._on_upload_finished,
            Qt.ConnectionType.QueuedConnection,
        )
        worker.finished.connect(thread.quit)
        worker.failed.connect(
            lambda e: self._on_worker_failed(e, "Upload"),
            Qt.ConnectionType.QueuedConnection,
        )
        worker.failed.connect(thread.quit)
        thread.finished.connect(self._clear_active_worker)
        thread.finished.connect(thread.deleteLater)
        self._active_worker = worker
        self._active_thread = thread
        thread.start()

    @Slot(object)
    def _on_upload_finished(self, records: list[AuditRecord]) -> None:
        self._on_upload_done(records)

    def _on_upload_progress(self, progress) -> None:
        self._upload_panel.update_progress(progress)

    def _on_upload_done(self, records: list[AuditRecord]) -> None:
        self._audit_records = records
        csv_path, xlsx_path = self._reports.write_reports(records)
        self._last_report_label.setText(f"Last report:\n{csv_path}\n{xlsx_path}")
        self._cancel_upload_btn.setEnabled(False)
        self._upload_btn.setEnabled(True)
        self._ready_state = "READY"
        self._upload_panel.set_complete_message("Upload complete — audit reports generated.")
        self._update_action_states()
        self._refresh_header()
        self._sidebar.go_to("reports")
        QMessageBox.information(self, "Upload Complete", "Audit reports saved to reports/")

    def _cancel_upload(self) -> None:
        self._upload_engine.cancel()
        self._cancel_upload_btn.setEnabled(False)
        self._ready_state = "READY"
        self._refresh_header()

    def _on_worker_failed(self, error: str, label: str) -> None:
        self._active_thread = None
        self._active_worker = None
        if label == "Pre-flight":
            self._validation_complete = False
            self._governance_complete = False
        if label == "Housekeeping":
            self._housekeeping_page.set_busy(False)
        self._ready_state = "ERROR"
        self._update_action_states()
        self._refresh_header()
        logger.error("%s failed: %s", label, error)
        QMessageBox.critical(self, label, error)

    def _test_s3(self) -> None:
        try:
            cat = self._resolve_catalogue()
        except ValueError as exc:
            QMessageBox.warning(self, "S3 Test", str(exc))
            return
        ok, msg = self._s3.test_connection(cat.location)
        if ok:
            QMessageBox.information(self, "S3 Test", msg)
        else:
            QMessageBox.warning(self, "S3 Test", msg)

    def _open_reports_folder(self) -> None:
        path = str(REPORTS_DIR.resolve())
        if sys.platform == "darwin":
            subprocess.run(["open", path], check=False)
        elif sys.platform == "win32":
            subprocess.run(["explorer", path], check=False)
        else:
            subprocess.run(["xdg-open", path], check=False)


class AppShell(QMainWindow):
    def __init__(self) -> None:
        from app import APP_NAME

        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1440, 900)
        self.setMinimumSize(1100, 700)
        self._content = MainWindow()
        self.setCentralWidget(self._content)


def run_app() -> int:
    app = QApplication(sys.argv)
    from app import APP_NAME

    app.setApplicationName(APP_NAME)
    apply_theme(app)
    shell = AppShell()
    shell.show()
    return app.exec()
