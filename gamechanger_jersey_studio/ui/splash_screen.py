"""Application splash screen."""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from core.version import APP_NAME, BUILD_LABEL, VERSION_LABEL
from ui.animations import fade_in
from ui.icons import icon
from ui.theme import Theme
from ui.typography import Typography


class SplashScreen(QWidget):
    """Professional startup splash shown for approximately two seconds."""

    finished = Signal()

    _STAGES = (
        "Initialising…",
        "Loading settings…",
        "Preparing workspace…",
        "Ready.",
    )

    def __init__(self) -> None:
        super().__init__(None, Qt.WindowType.SplashScreen | Qt.WindowType.FramelessWindowHint)
        self.setFixedSize(540, 340)
        self.setObjectName("splash")
        self.setStyleSheet(
            f"""
            QWidget#splash {{
                background-color: {Theme.PANEL};
                border: 1px solid {Theme.BORDER};
                border-radius: {Theme.RADIUS_LG}px;
            }}
            """
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(48, 48, 48, 48)
        layout.setSpacing(10)

        brand_icon = QLabel()
        brand_icon.setPixmap(icon("design", color=Theme.ACCENT, size=44).pixmap(44, 44))
        brand_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel(APP_NAME)
        title.setProperty("hero", True)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(Typography.display())

        version = QLabel(VERSION_LABEL)
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version.setProperty("muted", True)
        version.setFont(Typography.subheading())

        build = QLabel(BUILD_LABEL)
        build.setAlignment(Qt.AlignmentFlag.AlignCenter)
        build.setProperty("muted", True)
        build.setFont(Typography.caption())

        self._status = QLabel(self._STAGES[0])
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status.setFont(Typography.caption())
        self._status.setStyleSheet(f"color: {Theme.ACCENT}; padding-top: 28px;")

        layout.addStretch(1)
        layout.addWidget(brand_icon)
        layout.addWidget(title)
        layout.addWidget(version)
        layout.addWidget(build)
        layout.addWidget(self._status)
        layout.addStretch(2)

        self._stage_index = 0
        self._stage_timer = QTimer(self)
        self._stage_timer.timeout.connect(self._advance_stage)
        self._finish_timer = QTimer(self)
        self._finish_timer.setSingleShot(True)
        self._finish_timer.timeout.connect(self._complete)

    def start(self, duration_ms: int = 2000) -> None:
        self.show()
        fade_in(self, duration_ms=180)
        interval = max(300, duration_ms // len(self._STAGES))
        self._stage_timer.start(interval)
        self._finish_timer.start(duration_ms)

    def _advance_stage(self) -> None:
        self._stage_index = min(self._stage_index + 1, len(self._STAGES) - 1)
        self._status.setText(self._STAGES[self._stage_index])
        if self._stage_index >= len(self._STAGES) - 1:
            self._stage_timer.stop()

    def _complete(self) -> None:
        self._stage_timer.stop()
        self._status.setText(self._STAGES[-1])
        self.hide()
        self.finished.emit()
