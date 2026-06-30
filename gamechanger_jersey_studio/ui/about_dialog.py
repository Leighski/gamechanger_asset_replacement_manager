"""About dialog."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QVBoxLayout

from services.version_manager import VersionManager
from ui.icons import icon
from ui.theme import Theme
from ui.typography import Typography


class AboutDialog(QDialog):
    def __init__(self, version_manager: VersionManager, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("About Gamechanger Jersey Studio")
        self.setModal(True)
        self.resize(480, 520)

        info = version_manager.info
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 24)
        layout.setSpacing(6)

        brand_icon = QLabel()
        brand_icon.setPixmap(icon("design", color=Theme.ACCENT, size=40).pixmap(40, 40))
        brand_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel(info.application_name)
        title.setProperty("hero", True)
        title.setFont(Typography.display())
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        version = QLabel(info.version_label)
        version.setFont(Typography.subheading())
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)

        build = QLabel(f"{info.build_label}  ·  {info.work_package}")
        build.setAlignment(Qt.AlignmentFlag.AlignCenter)
        build.setProperty("muted", True)

        release = QLabel(f"Release date: {info.release_date}")
        release.setAlignment(Qt.AlignmentFlag.AlignCenter)
        release.setProperty("muted", True)

        details = QLabel(
            f"Python {info.python_version}\n"
            f"Qt {info.qt_version}\n\n"
            f"Application\n{info.application_path}\n\n"
            f"Configuration\n{info.configuration_path}\n\n"
            f"Logs\n{info.log_path}"
        )
        details.setFont(Typography.mono_caption())
        details.setProperty("muted", True)
        details.setWordWrap(True)
        details.setAlignment(Qt.AlignmentFlag.AlignLeft)
        details.setStyleSheet(f"padding: 16px 0; line-height: 1.5;")

        copyright_label = QLabel(info.copyright)
        copyright_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        copyright_label.setProperty("muted", True)
        copyright_label.setStyleSheet("padding-top: 8px;")

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self.accept)

        layout.addWidget(brand_icon)
        layout.addWidget(title)
        layout.addWidget(version)
        layout.addWidget(build)
        layout.addWidget(release)
        layout.addWidget(details)
        layout.addStretch(1)
        layout.addWidget(copyright_label)
        layout.addWidget(buttons)
