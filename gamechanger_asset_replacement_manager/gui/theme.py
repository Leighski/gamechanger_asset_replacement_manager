"""Visual theme — dark mode, Gamechanger blue accent."""

from __future__ import annotations

from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QApplication


class Theme:
    BG = "#1E1E1E"
    PANEL = "#252526"
    PANEL_ELEVATED = "#2D2D30"
    BORDER = "#3C3C3C"
    BORDER_SUBTLE = "#333333"
    TEXT = "#E8E8E8"
    TEXT_SECONDARY = "#9DA5B4"
    TEXT_MUTED = "#6C757D"
    ACCENT = "#007ACC"
    ACCENT_HOVER = "#1A8CD8"
    ACCENT_PRESSED = "#005A9E"
    SUCCESS = "#28A745"
    WARNING = "#FFC107"
    ERROR = "#DC3545"
    ROW_ALT = "#2A2D2E"
    ROW_HOVER = "#323638"
    INPUT_BG = "#1B1B1C"
    SIDEBAR = "#181818"
    SIDEBAR_ACTIVE = "#094771"

    FONT_UI = "Segoe UI"
    FONT_MONO = "SF Mono"
    FONT_SIZE = 13
    FONT_SIZE_SM = 11
    FONT_SIZE_LG = 15
    FONT_SIZE_TITLE = 22
    FONT_SIZE_HERO = 36

    MARGIN = 20
    CARD_RADIUS = 8
    SPACING = 14


def _color(hex_str: str) -> QColor:
    return QColor(hex_str)


def apply_theme(app: QApplication) -> None:
    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, _color(Theme.BG))
    palette.setColor(QPalette.ColorRole.WindowText, _color(Theme.TEXT))
    palette.setColor(QPalette.ColorRole.Base, _color(Theme.INPUT_BG))
    palette.setColor(QPalette.ColorRole.AlternateBase, _color(Theme.ROW_ALT))
    palette.setColor(QPalette.ColorRole.Text, _color(Theme.TEXT))
    palette.setColor(QPalette.ColorRole.Button, _color(Theme.PANEL_ELEVATED))
    palette.setColor(QPalette.ColorRole.ButtonText, _color(Theme.TEXT))
    palette.setColor(QPalette.ColorRole.Highlight, _color(Theme.ACCENT))
    palette.setColor(QPalette.ColorRole.HighlightedText, _color("#FFFFFF"))
    palette.setColor(QPalette.ColorRole.ToolTipBase, _color(Theme.PANEL_ELEVATED))
    palette.setColor(QPalette.ColorRole.ToolTipText, _color(Theme.TEXT))
    app.setPalette(palette)
    app.setFont(QFont(Theme.FONT_UI, Theme.FONT_SIZE))
    app.setStyleSheet(build_stylesheet())


def build_stylesheet() -> str:
    t = Theme
    return f"""
    QMainWindow, QWidget {{
        background-color: {t.BG};
        color: {t.TEXT};
    }}
    QScrollArea {{
        border: none;
        background-color: transparent;
    }}
    QScrollBar:vertical {{
        background: {t.BG};
        width: 10px;
        margin: 0;
    }}
    QScrollBar::handle:vertical {{
        background: {t.BORDER};
        border-radius: 5px;
        min-height: 24px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {t.ACCENT};
    }}
    QLabel[class="muted"] {{
        color: {t.TEXT_SECONDARY};
    }}
    QLabel[class="hero"] {{
        font-size: {t.FONT_SIZE_HERO}px;
        font-weight: 700;
        color: {t.TEXT};
    }}
    QLabel[class="card-title"] {{
        font-size: {t.FONT_SIZE_LG}px;
        font-weight: 600;
        color: {t.TEXT};
    }}
    QFrame[class="card"] {{
        background-color: {t.PANEL};
        border: 1px solid {t.BORDER_SUBTLE};
        border-radius: {t.CARD_RADIUS}px;
    }}
    QFrame[class="stat-card"] {{
        background-color: {t.PANEL_ELEVATED};
        border: 1px solid {t.BORDER_SUBTLE};
        border-radius: {t.CARD_RADIUS}px;
    }}
    QPushButton {{
        background-color: {t.PANEL_ELEVATED};
        color: {t.TEXT};
        border: 1px solid {t.BORDER};
        border-radius: 6px;
        padding: 10px 18px;
        font-size: {t.FONT_SIZE}px;
        font-weight: 500;
        min-height: 20px;
    }}
    QPushButton:hover {{
        background-color: {t.ROW_HOVER};
        border-color: {t.ACCENT};
    }}
    QPushButton:pressed {{
        background-color: {t.ACCENT_PRESSED};
    }}
    QPushButton:disabled {{
        color: {t.TEXT_MUTED};
        background-color: {t.PANEL};
        border-color: {t.BORDER_SUBTLE};
    }}
    QPushButton[class="primary"] {{
        background-color: {t.ACCENT};
        border-color: {t.ACCENT};
        color: #FFFFFF;
        font-weight: 600;
    }}
    QPushButton[class="primary"]:hover {{
        background-color: {t.ACCENT_HOVER};
        border-color: {t.ACCENT_HOVER};
    }}
    QPushButton[class="danger"] {{
        background-color: transparent;
        border-color: {t.ERROR};
        color: {t.ERROR};
    }}
    QPushButton[class="ghost"] {{
        background-color: transparent;
        border-color: transparent;
        color: {t.TEXT_SECONDARY};
    }}
    QPushButton[class="ghost"]:hover {{
        color: {t.ACCENT};
        background-color: {t.PANEL_ELEVATED};
    }}
    QLineEdit, QSpinBox, QComboBox {{
        background-color: {t.INPUT_BG};
        color: {t.TEXT};
        border: 1px solid {t.BORDER};
        border-radius: 6px;
        padding: 10px 12px;
        font-size: {t.FONT_SIZE}px;
        min-height: 18px;
    }}
    QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{
        border-color: {t.ACCENT};
    }}
    QComboBox::drop-down {{
        border: none;
        width: 28px;
    }}
    QComboBox QAbstractItemView {{
        background-color: {t.PANEL_ELEVATED};
        color: {t.TEXT};
        selection-background-color: {t.ACCENT};
        border: 1px solid {t.BORDER};
    }}
    QCheckBox {{
        spacing: 10px;
        color: {t.TEXT};
        font-size: {t.FONT_SIZE}px;
    }}
    QCheckBox::indicator {{
        width: 18px;
        height: 18px;
        border-radius: 4px;
        border: 1px solid {t.BORDER};
        background: {t.INPUT_BG};
    }}
    QCheckBox::indicator:checked {{
        background: {t.ACCENT};
        border-color: {t.ACCENT};
    }}
    QProgressBar {{
        border: none;
        border-radius: 6px;
        background-color: {t.INPUT_BG};
        text-align: center;
        color: {t.TEXT};
        font-weight: 600;
        min-height: 22px;
    }}
    QProgressBar::chunk {{
        background-color: {t.ACCENT};
        border-radius: 6px;
    }}
    QTableView {{
        background-color: {t.PANEL};
        alternate-background-color: {t.ROW_ALT};
        color: {t.TEXT};
        gridline-color: {t.BORDER_SUBTLE};
        border: 1px solid {t.BORDER_SUBTLE};
        border-radius: 6px;
        selection-background-color: {t.SIDEBAR_ACTIVE};
        selection-color: #FFFFFF;
        font-size: {t.FONT_SIZE_SM}px;
    }}
    QTableView::item {{
        padding: 6px 8px;
    }}
    QHeaderView::section {{
        background-color: {t.PANEL_ELEVATED};
        color: {t.TEXT_SECONDARY};
        padding: 10px 8px;
        border: none;
        border-bottom: 1px solid {t.BORDER};
        font-weight: 600;
        font-size: {t.FONT_SIZE_SM}px;
    }}
    QListWidget {{
        background-color: {t.INPUT_BG};
        border: 1px solid {t.BORDER};
        border-radius: 6px;
    }}
    QTabWidget::pane {{
        border: 1px solid {t.BORDER};
        border-radius: 6px;
        background: {t.PANEL};
    }}
    QTabBar::tab {{
        background: {t.PANEL};
        color: {t.TEXT_SECONDARY};
        padding: 12px 20px;
        margin-right: 2px;
        border-top-left-radius: 6px;
        border-top-right-radius: 6px;
    }}
    QTabBar::tab:selected {{
        background: {t.PANEL_ELEVATED};
        color: {t.ACCENT};
        font-weight: 600;
    }}
    QDialog {{
        background-color: {t.BG};
    }}
    QMessageBox {{
        background-color: {t.PANEL};
    }}
    """
