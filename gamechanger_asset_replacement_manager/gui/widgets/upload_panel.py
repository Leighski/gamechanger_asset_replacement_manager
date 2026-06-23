"""Professional upload progress panel."""

from __future__ import annotations

from PySide6.QtWidgets import QGridLayout, QLabel, QProgressBar, QVBoxLayout, QWidget

from gui.theme import Theme
from models.upload import UploadProgress


class UploadProgressPanel(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        self._overall_label = QLabel("Overall progress")
        self._overall_label.setProperty("class", "muted")
        self._progress = QProgressBar()
        self._progress.setFormat("%p% — %v / %m files")
        layout.addWidget(self._overall_label)
        layout.addWidget(self._progress)

        self._current_file = QLabel("Waiting to start…")
        self._current_file.setWordWrap(True)
        self._current_file.setStyleSheet(f"font-size: {Theme.FONT_SIZE_LG}px; color: {Theme.TEXT};")
        layout.addWidget(self._current_file)

        grid = QGridLayout()
        grid.setSpacing(12)
        self._speed = self._stat_cell("Transfer speed", "—")
        self._eta = self._stat_cell("Est. time remaining", "—")
        self._completed = self._stat_cell("Completed", "0")
        self._failures = self._stat_cell("Failures", "0")
        self._successes = self._stat_cell("Successes", "0")
        self._skipped = self._stat_cell("Skipped", "0")

        cells = [
            self._speed,
            self._eta,
            self._completed,
            self._successes,
            self._failures,
            self._skipped,
        ]
        for i, cell in enumerate(cells):
            grid.addWidget(cell, i // 3, i % 3)
        layout.addLayout(grid)

        self._elapsed = QLabel("Elapsed: 0s")
        self._elapsed.setProperty("class", "muted")
        layout.addWidget(self._elapsed)

    def _stat_cell(self, title: str, value: str) -> QWidget:
        wrap = QVBoxLayout()
        t = QLabel(title)
        t.setProperty("class", "muted")
        v = QLabel(value)
        v.setStyleSheet(f"font-size: 18px; font-weight: 600; color: {Theme.TEXT};")
        wrap.addWidget(t)
        wrap.addWidget(v)
        box = QWidget()
        box.setLayout(wrap)
        box._value = v  # type: ignore[attr-defined]
        return box

    @staticmethod
    def _set_cell(box: QWidget, text: str, color: str | None = None) -> None:
        v: QLabel = box._value  # type: ignore[attr-defined]
        v.setText(text)
        if color:
            v.setStyleSheet(f"font-size: 18px; font-weight: 600; color: {color};")

    def reset(self, total: int) -> None:
        self._progress.setMaximum(max(total, 1))
        self._progress.setValue(0)
        self._current_file.setText("Preparing upload…")
        self._set_cell(self._speed, "—")
        self._set_cell(self._eta, "—")
        self._set_cell(self._completed, f"0 / {total}")
        self._set_cell(self._successes, "0", Theme.SUCCESS)
        self._set_cell(self._failures, "0", Theme.ERROR)
        self._set_cell(self._skipped, "0")
        self._elapsed.setText("Elapsed: 0s")

    def update_progress(self, p: UploadProgress) -> None:
        total = max(p.total, 1)
        self._progress.setMaximum(total)
        self._progress.setValue(p.completed)
        self._current_file.setText(p.current_file or "—")

        speed = f"{p.speed_mbps:.2f} Mbps" if p.speed_mbps > 0 else "—"
        self._set_cell(self._speed, speed)

        eta_sec = 0.0
        if p.completed > 0 and p.remaining > 0:
            rate = p.elapsed_seconds / p.completed
            eta_sec = rate * p.remaining
        eta_text = self._format_duration(eta_sec) if eta_sec > 0 else "—"
        self._set_cell(self._eta, eta_text)

        self._set_cell(self._completed, f"{p.completed} / {total}")
        self._set_cell(self._successes, str(p.success_count), Theme.SUCCESS)
        self._set_cell(self._failures, str(p.failure_count), Theme.ERROR)
        self._set_cell(self._skipped, str(p.skipped_count))
        self._elapsed.setText(f"Elapsed: {self._format_duration(p.elapsed_seconds)}")

    @staticmethod
    def _format_duration(seconds: float) -> str:
        s = int(seconds)
        if s < 60:
            return f"{s}s"
        m, s = divmod(s, 60)
        if m < 60:
            return f"{m}m {s}s"
        h, m = divmod(m, 60)
        return f"{h}h {m}m"

    def set_complete_message(self, message: str) -> None:
        self._current_file.setText(message)
        self._progress.setValue(self._progress.maximum())
