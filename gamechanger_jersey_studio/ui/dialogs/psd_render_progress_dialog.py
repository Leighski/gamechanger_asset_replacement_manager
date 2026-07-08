"""PSD Render Progress dialog."""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QDialog, QLabel, QListWidget, QProgressBar, QVBoxLayout

from models.psd_render import PSDRenderProgress, PSDRenderStage
from ui.theme import Theme
from ui.typography import Typography


class PSDRenderProgressDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Production PSD Render")
        self.setModal(True)
        self.resize(520, 420)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(Theme.SPACING_XL, Theme.SPACING_XL, Theme.SPACING_XL, Theme.SPACING_XL)
        layout.setSpacing(Theme.SPACING_MD)

        self._stage = QLabel("Preparing…")
        self._stage.setFont(Typography.subheading())
        self._elapsed = QLabel("Elapsed: 0 ms")
        self._elapsed.setProperty("muted", True)
        self._layer = QLabel("")
        self._layer.setProperty("muted", True)
        self._bar = QProgressBar()
        self._bar.setRange(0, len(PSDRenderStage))
        self._remaining = QListWidget()
        self._warnings = QListWidget()
        self._errors = QListWidget()

        layout.addWidget(self._stage)
        layout.addWidget(self._elapsed)
        layout.addWidget(self._layer)
        layout.addWidget(self._bar)
        layout.addWidget(QLabel("Remaining stages"))
        layout.addWidget(self._remaining)
        layout.addWidget(QLabel("Warnings"))
        layout.addWidget(self._warnings)
        layout.addWidget(QLabel("Errors"))
        layout.addWidget(self._errors)

    def update_progress(self, progress: PSDRenderProgress) -> None:
        if progress.current_stage is not None:
            self._stage.setText(f"Current stage: {progress.current_stage.value}")
        self._elapsed.setText(f"Elapsed: {progress.elapsed_ms:.0f} ms")
        self._layer.setText(f"Current layer: {progress.current_layer or '—'}")
        self._bar.setValue(len(progress.completed_stages))
        self._remaining.clear()
        for stage in progress.remaining_stages:
            self._remaining.addItem(stage.value)
        self._warnings.clear()
        for warning in progress.warnings:
            self._warnings.addItem(warning)
        self._errors.clear()
        for error in progress.errors:
            self._errors.addItem(error)
