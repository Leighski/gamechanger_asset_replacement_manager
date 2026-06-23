"""Pre-replacement governance preview for verified Iconik asset bindings."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from services.asset_resolution_service import AssetResolutionResult, GovernanceStatus


class ResolutionPreviewDialog(QDialog):
    def __init__(
        self,
        results: list[AssetResolutionResult],
        *,
        parent=None,
        window_title: str = "Confirm Iconik Asset Resolution",
        proceed_label: str = "Proceed with Replacement",
        intro_text: str | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(window_title)
        self.setMinimumSize(960, 320)
        self._confirmed = False

        verified = [r for r in results if r.status == GovernanceStatus.VERIFIED and r.target]

        layout = QVBoxLayout(self)
        intro = QLabel(
            intro_text
            or (
                "Review the resolved Iconik assets before replacement. "
                "Only verified bindings will be modified."
            )
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        table = QTableWidget(len(verified), 9)
        table.setHorizontalHeaderLabels(
            [
                "Type",
                "Filename",
                "Governance",
                "Warnings",
                "Metadata",
                "Asset ID",
                "File Set ID",
                "Iconik S3 Key",
                "Resolution",
            ]
        )
        table.horizontalHeader().setStretchLastSection(True)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        for row, result in enumerate(verified):
            target = result.target
            assert target is not None
            warnings = ", ".join(result.governance_warnings) if result.governance_warnings else ""
            table.setItem(row, 0, QTableWidgetItem(result.asset_type.value))
            table.setItem(row, 1, QTableWidgetItem(result.local_filename))
            table.setItem(row, 2, QTableWidgetItem(result.status.value))
            table.setItem(row, 3, QTableWidgetItem(warnings))
            table.setItem(row, 4, QTableWidgetItem(target.metadata_status))
            table.setItem(row, 5, QTableWidgetItem(target.asset_id))
            table.setItem(row, 6, QTableWidgetItem(target.file_set_id))
            table.setItem(row, 7, QTableWidgetItem(target.iconik_s3_key))
            table.setItem(row, 8, QTableWidgetItem(result.resolution_method))
        table.resizeColumnsToContents()
        layout.addWidget(table)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(proceed_label)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _accept(self) -> None:
        self._confirmed = True
        self.accept()

    @property
    def confirmed(self) -> bool:
        return self._confirmed
