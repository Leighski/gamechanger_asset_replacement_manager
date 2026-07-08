"""Application status bar with icons."""

from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QHBoxLayout, QLabel, QStatusBar, QWidget

from core.memory import memory_usage_mb
from core.version import get_python_version
from services.version_manager import VersionManager
from ui.icons import icon
from ui.typography import Typography


class _StatusItem(QWidget):
    def __init__(self, icon_name: str, text: str = "", parent=None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._icon = QLabel()
        self._icon.setFixedSize(14, 14)
        self._text = QLabel(text)
        self._text.setFont(Typography.status())

        layout.addWidget(self._icon)
        layout.addWidget(self._text)

        self.set_icon(icon_name)
        self.set_text(text)

    def set_icon(self, icon_name: str) -> None:
        self._icon.setPixmap(icon(icon_name, size=14).pixmap(14, 14))

    def set_text(self, text: str) -> None:
        self._text.setText(text)


class ApplicationStatusBar(QStatusBar):
    def __init__(self, version_manager: VersionManager, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._version_manager = version_manager

        self._ready = QLabel("Ready")
        self._ready.setFont(Typography.status())
        self._project = _StatusItem("folder", "No project")
        self._autosave = _StatusItem("status_idle", "Autosave idle")
        self._python = _StatusItem("python", f"Python {get_python_version()}")
        self._app_version = _StatusItem("doc", "")
        self._memory = _StatusItem("memory", "Memory —")

        self.addWidget(self._ready)
        self.addWidget(self._project)
        self.addPermanentWidget(self._autosave)
        self.addPermanentWidget(self._python)
        self.addPermanentWidget(self._app_version)
        self.addPermanentWidget(self._memory)

        self._refresh_static()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh_memory)
        self._timer.start(2000)
        self._refresh_memory()

    def set_ready(self, message: str = "Ready") -> None:
        self._ready.setText(message)

    def set_project(self, name: str, status: str = "Active") -> None:
        if name:
            self._project.set_text(f"{name} ({status})")
        else:
            self._project.set_text("No project")

    def set_autosave(self, message: str) -> None:
        lowered = message.lower()
        icon_name = (
            "status_ok"
            if "saved" in lowered or "enabled" in lowered
            else "status_idle"
        )
        self._autosave.set_icon(icon_name)
        display = message.replace("Autosave: ", "Autosave ")
        self._autosave.set_text(display)

    def _refresh_static(self) -> None:
        info = self._version_manager.info
        self._app_version.set_text(info.branding_line)

    def _refresh_memory(self) -> None:
        mb = memory_usage_mb()
        self._memory.set_text(f"Memory {mb:.1f} MB")
