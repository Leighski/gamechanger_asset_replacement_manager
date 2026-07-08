"""Dialog for reviewing ambiguous Iconik asset resolution candidates."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from services.asset_resolution_service import AssetResolutionResult, GovernanceStatus


class DuplicateResolutionDialog(QDialog):
    def __init__(
        self,
        results: list[AssetResolutionResult],
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Duplicate Iconik Assets Detected")
        self.setMinimumSize(900, 420)
        self._results = [r for r in results if r.status == GovernanceStatus.DUPLICATE]

        layout = QVBoxLayout(self)
        intro = QLabel(
            "Multiple Iconik assets match the same filename. "
            "Replacement cannot proceed until duplicates are resolved in Iconik.\n"
            "Findings have been appended to reports/duplicate_assets.csv."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        for result in self._results:
            header = QLabel(
                f"{result.asset_type.value}: {result.local_filename} "
                f"({result.duplicate_count} candidates)"
            )
            header.setStyleSheet("font-weight: 600; margin-top: 8px;")
            layout.addWidget(header)

            table = QTableWidget(len(result.candidates), 6)
            table.setHorizontalHeaderLabels(
                [
                    "Asset ID",
                    "Title",
                    "File Set Name",
                    "File Set ID",
                    "S3 Key",
                    "Storage Path",
                ]
            )
            table.horizontalHeader().setStretchLastSection(True)
            table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
            for row, candidate in enumerate(result.candidates):
                table.setItem(row, 0, QTableWidgetItem(candidate.asset_id))
                table.setItem(row, 1, QTableWidgetItem(candidate.title))
                table.setItem(row, 2, QTableWidgetItem(candidate.file_set_name))
                table.setItem(row, 3, QTableWidgetItem(candidate.file_set_id))
                table.setItem(row, 4, QTableWidgetItem(candidate.s3_key))
                table.setItem(row, 5, QTableWidgetItem(candidate.storage_path))
            table.resizeColumnsToContents()
            layout.addWidget(table)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)
