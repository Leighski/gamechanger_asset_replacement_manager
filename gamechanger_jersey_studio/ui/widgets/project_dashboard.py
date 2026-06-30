"""Project dashboard centre panel."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QVBoxLayout

from models.project import ProjectDocument
from models.reference_image import REQUIRED_CATEGORIES
from services.design_spec_completion import CompletionReport
from services.design_specification_service import DesignSpecificationService
from services.reference_image_service import ReferenceImageService
from ui.icons import icon
from ui.theme import Theme
from ui.typography import Typography


class DashboardCard(QFrame):
    def __init__(self, title: str, icon_name: str, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(Theme.SPACING_LG, Theme.SPACING_MD, Theme.SPACING_LG, Theme.SPACING_MD)
        layout.setSpacing(Theme.SPACING_SM)

        header = QHBoxLayout()
        header.setSpacing(Theme.SPACING_SM)
        glyph = QLabel()
        glyph.setPixmap(icon(icon_name, color=Theme.ACCENT, size=16).pixmap(16, 16))
        self._title = QLabel(title)
        self._title.setFont(Typography.caption())
        self._title.setStyleSheet(f"color: {Theme.TEXT_MUTED}; font-weight: 600;")
        header.addWidget(glyph)
        header.addWidget(self._title)
        header.addStretch(1)

        self._value = QLabel("—")
        self._value.setWordWrap(True)
        self._value.setFont(Typography.subheading())

        layout.addLayout(header)
        layout.addWidget(self._value)

    def set_value(self, text: str) -> None:
        self._value.setText(text)


class CompletionRow(QFrame):
    def __init__(self, label: str, parent=None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._label = QLabel(label)
        self._label.setFont(Typography.body())
        self._percent = QLabel("—")
        self._percent.setFont(Typography.subheading())
        self._percent.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self._label, stretch=1)
        layout.addWidget(self._percent)

    def set_percent(self, percent: int) -> None:
        self._percent.setText(f"{percent}%")
        colour = Theme.SUCCESS if percent >= 80 else Theme.WARNING if percent >= 40 else Theme.TEXT_MUTED
        self._percent.setStyleSheet(f"color: {colour};")


class ProjectDashboard(QFrame):
    references_clicked = Signal()

    _CARD_DEFS = (
        ("project_name", "Project Name", "folder"),
        ("club", "Club", "design"),
        ("competition", "Competition", "reports"),
        ("season", "Season", "activity"),
        ("build_profile", "Build Profile", "settings"),
        ("status", "Project Status", "validation"),
        ("references", "Reference Images", "image"),
        ("outputs", "Generated Outputs", "preview"),
        ("validation", "Validation Status", "validation"),
    )

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._design_service: DesignSpecificationService | None = None
        self._reference_service: ReferenceImageService | None = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(Theme.SPACING_XL, Theme.SPACING_XL, Theme.SPACING_XL, Theme.SPACING_XL)
        layout.setSpacing(Theme.SPACING_LG)

        self._heading = QLabel("Project Dashboard")
        self._heading.setProperty("title", True)
        self._heading.setFont(Typography.heading())
        self._subtitle = QLabel("No project loaded")
        self._subtitle.setProperty("muted", True)
        self._subtitle.setFont(Typography.body())

        grid_host = QFrame()
        grid = QGridLayout(grid_host)
        grid.setSpacing(Theme.SPACING_MD)

        self._cards: dict[str, DashboardCard] = {}
        for index, (key, title, icon_name) in enumerate(self._CARD_DEFS):
            card = DashboardCard(title, icon_name)
            self._cards[key] = card
            grid.addWidget(card, index // 3, index % 3)

        completion_frame = QFrame()
        completion_frame.setObjectName("panel")
        completion_layout = QVBoxLayout(completion_frame)
        completion_layout.setContentsMargins(Theme.SPACING_LG, Theme.SPACING_MD, Theme.SPACING_LG, Theme.SPACING_MD)

        completion_header = QHBoxLayout()
        completion_glyph = QLabel()
        completion_glyph.setPixmap(icon("design", color=Theme.ACCENT, size=16).pixmap(16, 16))
        completion_title = QLabel("Design Specification Completeness")
        completion_title.setFont(Typography.subheading())
        completion_header.addWidget(completion_glyph)
        completion_header.addWidget(completion_title)
        completion_header.addStretch(1)

        self._completion_rows: dict[str, CompletionRow] = {}
        rows_host = QVBoxLayout()
        rows_host.setSpacing(Theme.SPACING_SM)
        for key, label in (
            ("project_information", "Project Information"),
            ("colours", "Colours"),
            ("construction", "Construction"),
            ("pattern", "Pattern"),
            ("effects", "Effects"),
            ("output", "Output"),
        ):
            row = CompletionRow(label)
            self._completion_rows[key] = row
            rows_host.addWidget(row)

        self._overall_row = CompletionRow("Overall Completion")
        self._overall_row._percent.setFont(Typography.heading())

        completion_layout.addLayout(completion_header)
        completion_layout.addLayout(rows_host)
        completion_layout.addWidget(self._overall_row)

        reference_frame = QFrame()
        reference_frame.setObjectName("panel")
        reference_layout = QVBoxLayout(reference_frame)
        reference_layout.setContentsMargins(Theme.SPACING_LG, Theme.SPACING_MD, Theme.SPACING_LG, Theme.SPACING_MD)
        ref_header = QHBoxLayout()
        ref_glyph = QLabel()
        ref_glyph.setPixmap(icon("image", color=Theme.ACCENT, size=16).pixmap(16, 16))
        ref_title = QLabel("Reference Images")
        ref_title.setFont(Typography.subheading())
        ref_header.addWidget(ref_glyph)
        ref_header.addWidget(ref_title)
        ref_header.addStretch(1)
        self._ref_imported = QLabel("Imported: —")
        self._ref_required = QLabel("Required categories: —")
        self._ref_missing = QLabel("Missing categories: —")
        self._ref_resolution = QLabel("Resolution: —")
        for label in (self._ref_imported, self._ref_required, self._ref_missing, self._ref_resolution):
            label.setFont(Typography.body())
        self._ref_preview = QLabel()
        self._ref_preview.setFixedSize(120, 80)
        self._ref_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._ref_preview.setStyleSheet(f"background: {Theme.PANEL_ELEVATED}; border-radius: {Theme.RADIUS_SM}px;")
        preview_row = QHBoxLayout()
        preview_row.addWidget(self._ref_preview)
        preview_row.addStretch(1)
        reference_layout.addLayout(ref_header)
        reference_layout.addWidget(self._ref_imported)
        reference_layout.addWidget(self._ref_required)
        reference_layout.addWidget(self._ref_missing)
        reference_layout.addWidget(self._ref_resolution)
        reference_layout.addLayout(preview_row)

        activity_frame = QFrame()
        activity_frame.setObjectName("panel")
        activity_layout = QVBoxLayout(activity_frame)
        activity_layout.setContentsMargins(Theme.SPACING_LG, Theme.SPACING_MD, Theme.SPACING_LG, Theme.SPACING_MD)

        activity_header = QHBoxLayout()
        activity_glyph = QLabel()
        activity_glyph.setPixmap(icon("activity", color=Theme.ACCENT, size=16).pixmap(16, 16))
        self._activity = QLabel("Recent Activity")
        self._activity.setFont(Typography.subheading())
        activity_header.addWidget(activity_glyph)
        activity_header.addWidget(self._activity)
        activity_header.addStretch(1)

        self._activity_list = QLabel("No activity recorded.")
        self._activity_list.setProperty("muted", True)
        self._activity_list.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._activity_list.setWordWrap(True)

        activity_layout.addLayout(activity_header)
        activity_layout.addWidget(self._activity_list)

        layout.addWidget(self._heading)
        layout.addWidget(self._subtitle)
        layout.addWidget(grid_host)
        layout.addWidget(completion_frame)
        layout.addWidget(reference_frame)
        layout.addWidget(activity_frame, stretch=1)

        self.clear()

    def set_design_service(self, service: DesignSpecificationService) -> None:
        self._design_service = service

    def set_reference_service(self, service: ReferenceImageService) -> None:
        self._reference_service = service
        self._cards["references"].mousePressEvent = lambda _event: self.references_clicked.emit()  # type: ignore[method-assign]

    def set_project(self, document: ProjectDocument | None) -> None:
        if document is None:
            self.clear()
            return
        m = document.manifest
        self._subtitle.setText(f"{m.club_name} · {m.season}")
        self._cards["project_name"].set_value(m.project_name)
        self._cards["club"].set_value(m.club_name)
        self._cards["competition"].set_value(m.competition)
        self._cards["season"].set_value(m.season)
        self._cards["build_profile"].set_value(m.build_profile)
        self._cards["status"].set_value(m.status.value)
        self._cards["references"].set_value(str(m.reference_image_count))
        self._cards["outputs"].set_value(str(m.generated_output_count))
        self._cards["validation"].set_value(m.validation_status.value)
        self._set_reference_summary(document)

        if self._design_service is not None:
            spec = self._design_service.ensure_spec(document)
            report = self._design_service.completion(spec)
            self._set_completion(report)

        recent = document.history.recent(5)
        if recent:
            lines = [
                f"{entry.timestamp} — {entry.event.value} ({entry.user})"
                for entry in recent
            ]
            self._activity_list.setText("\n".join(lines))
        else:
            self._activity_list.setText("No activity recorded yet.")

    def _set_completion(self, report: CompletionReport) -> None:
        for section in report.sections:
            row = self._completion_rows.get(section.section)
            if row is not None:
                row.set_percent(section.percent)
        self._overall_row.set_percent(report.overall_percent)

    def _set_reference_summary(self, document: ProjectDocument) -> None:
        if self._reference_service is None:
            self._ref_imported.setText("Imported: —")
            self._ref_required.setText(f"Required categories: {', '.join(REQUIRED_CATEGORIES)}")
            self._ref_missing.setText("Missing categories: —")
            self._ref_resolution.setText("Resolution: —")
            self._ref_preview.clear()
            return
        manifest = self._reference_service.ensure_manifest(document)
        missing = self._reference_service.missing_categories()
        self._ref_imported.setText(f"Imported: {len(manifest.images)}")
        self._ref_required.setText(f"Required categories: {', '.join(REQUIRED_CATEGORIES)}")
        self._ref_missing.setText(
            f"Missing categories: {', '.join(missing) if missing else 'None'}"
        )
        self._ref_resolution.setText(f"Resolution: {self._reference_service.resolution_summary()}")
        if manifest.images:
            first = manifest.sorted_images()[0]
            thumb = self._reference_service.thumbnail_path(document.manifest.project_id, first.image_id)
            if thumb.is_file():
                self._ref_preview.setPixmap(
                    QPixmap(str(thumb)).scaled(
                        120,
                        80,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
            else:
                self._ref_preview.setText("—")
        else:
            self._ref_preview.setText("No preview")

    def clear(self) -> None:
        self._subtitle.setText("No project loaded")
        for card in self._cards.values():
            card.set_value("—")
        for row in self._completion_rows.values():
            row.set_percent(0)
        self._overall_row.set_percent(0)
        self._ref_imported.setText("Imported: —")
        self._ref_required.setText("Required categories: —")
        self._ref_missing.setText("Missing categories: —")
        self._ref_resolution.setText("Resolution: —")
        self._ref_preview.clear()
        self._activity_list.setText("Create or open a project to view activity.")
