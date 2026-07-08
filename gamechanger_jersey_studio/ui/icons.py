"""SVG icon loading — consistent stroke icons at 1x and 2x."""

from __future__ import annotations

from PySide6.QtCore import QByteArray, QSize, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

_ICON_TEMPLATE = """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">{paths}</svg>"""

_SVGS: dict[str, str] = {
    "projects": '<path d="M3 7V5a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Z"/>',
    "design": '<path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z"/>',
    "libraries": '<path d="m8 3 4 4-4 4"/><path d="M4 7h8"/><path d="m14 13 4 4-4 4"/><path d="M10 17h8"/>',
    "preview": '<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/>',
    "validation": '<path d="M9 11 11 13 15 9"/><path d="M12 22a10 10 0 1 0-10-10"/>',
    "reports": '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z"/><path d="M14 2v6h6"/><path d="M8 13h8"/><path d="M8 17h5"/>',
    "settings": '<circle cx="12" cy="12" r="3"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/>',
    "new": '<path d="M12 5v14"/><path d="M5 12h14"/>',
    "open": '<path d="M3 7V5a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Z"/>',
    "save": '<path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2Z"/><path d="M17 21v-8H7v8"/><path d="M7 3v5h8"/>',
    "help": '<circle cx="12" cy="12" r="10"/><path d="M9.5 9.5a2.5 2.5 0 1 1 4.2 1.8c-.8.7-1.7 1.5-1.7 2.7"/><circle cx="12" cy="17" r=".5"/>',
    "folder": '<path d="M3 7V5a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Z"/>',
    "image": '<rect x="3" y="5" width="18" height="14" rx="2"/><circle cx="8.5" cy="10.5" r="1.5"/><path d="m21 17-5-5L5 19"/>',
    "activity": '<path d="M3 12h4l2-7 4 14 2-7h6"/>',
    "status_ok": '<path d="M20 6 9 17l-5-5"/>',
    "status_idle": '<circle cx="12" cy="12" r="9"/>',
    "memory": '<rect x="4" y="4" width="16" height="16" rx="2"/><path d="M9 9h6v6H9Z"/>',
    "python": '<path d="M9 4h6v4H9z"/><path d="M8 20h8a2 2 0 0 0 2-2v-5H6v5a2 2 0 0 0 2 2Z"/>',
    "doc": '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z"/><path d="M14 2v6h6"/>',
}


def icon(name: str, *, color: str = "#C8C8C8", size: int = 18) -> QIcon:
    paths = _SVGS.get(name, _SVGS["status_idle"])
    svg = _ICON_TEMPLATE.format(color=color, paths=paths)
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    pixmap = QPixmap(size * 2, size * 2)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    result = QIcon(pixmap)
    result.addPixmap(pixmap, QIcon.Mode.Normal, QIcon.State.Off)
    return result


def icon_size(size: int = 18) -> QSize:
    return QSize(size, size)
