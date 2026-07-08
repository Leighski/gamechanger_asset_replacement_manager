"""Recovery restore dialog."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
)

from services.autosave_service import RecoveryCandidate


class RecoveryDialog(QDialog):
    def __init__(self, candidates: list[RecoveryCandidate], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Recover Unsaved Work")
        self.resize(520, 320)
        self._candidates = candidates
        self._selected: RecoveryCandidate | None = candidates[0] if candidates else None

        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(
                "Jersey Studio did not shut down cleanly. "
                "The following recovery copies are available:"
            )
        )
        self._list = QListWidget()
        for candidate in candidates:
            item = QListWidgetItem(
                f"{candidate.project_name} — saved {candidate.saved_at}\n{candidate.recovery_path}"
            )
            item.setData(256, candidate)
            self._list.addItem(item)
        if self._list.count():
            self._list.setCurrentRow(0)
        self._list.currentItemChanged.connect(self._on_select)

        buttons = QDialogButtonBox()
        restore_btn = buttons.addButton("Restore", QDialogButtonBox.ButtonRole.AcceptRole)
        discard_btn = buttons.addButton("Discard", QDialogButtonBox.ButtonRole.RejectRole)
        restore_btn.clicked.connect(self.accept)
        discard_btn.clicked.connect(self.reject)

        layout.addWidget(self._list, stretch=1)
        layout.addWidget(buttons)

    def selected(self) -> RecoveryCandidate | None:
        return self._selected

    def _on_select(self, current: QListWidgetItem | None, _previous) -> None:
        if current is not None:
            self._selected = current.data(256)
