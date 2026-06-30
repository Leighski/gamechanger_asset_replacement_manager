"""Professional dark theme — premium desktop polish."""

from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from ui.typography import Typography


class Theme:
    """Lightroom / DaVinci inspired dark palette."""

    BACKGROUND = "#141414"
    PANEL = "#1C1C1C"
    PANEL_ELEVATED = "#242424"
    PANEL_HOVER = "#2A2A2A"
    SIDEBAR = "#181818"
    TOOLBAR = "#1A1A1A"
    BORDER = "#323232"
    BORDER_SUBTLE = "#2A2A2A"
    BORDER_FOCUS = "#4A8BE5"

    TEXT = "#EDEDED"
    TEXT_MUTED = "#9A9A9A"
    TEXT_DISABLED = "#5C5C5C"

    ACCENT = "#3A7BD5"
    ACCENT_HOVER = "#4A8BE5"
    ACCENT_PRESSED = "#2F6BC4"
    ACCENT_SUBTLE = "rgba(58, 123, 213, 0.15)"

    SUCCESS = "#4CAF7A"
    WARNING = "#D9A441"
    ERROR = "#D95C5C"

    RADIUS_SM = 4
    RADIUS_MD = 8
    RADIUS_LG = 12

    SPACING_XS = 4
    SPACING_SM = 8
    SPACING_MD = 12
    SPACING_LG = 16
    SPACING_XL = 24

    FONT_FAMILY = Typography.FAMILY_BODY
    FONT_SIZE = Typography.SIZE_BODY
    FONT_SIZE_SMALL = Typography.SIZE_CAPTION
    FONT_SIZE_TITLE = Typography.SIZE_HEADING

    @classmethod
    def apply(cls, app: QApplication) -> None:
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor(cls.BACKGROUND))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(cls.TEXT))
        palette.setColor(QPalette.ColorRole.Base, QColor(cls.PANEL))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(cls.PANEL_ELEVATED))
        palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(cls.PANEL_ELEVATED))
        palette.setColor(QPalette.ColorRole.ToolTipText, QColor(cls.TEXT))
        palette.setColor(QPalette.ColorRole.Text, QColor(cls.TEXT))
        palette.setColor(QPalette.ColorRole.Button, QColor(cls.PANEL_ELEVATED))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor(cls.TEXT))
        palette.setColor(QPalette.ColorRole.BrightText, QColor(cls.ACCENT))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(cls.ACCENT))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#FFFFFF"))
        palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(cls.TEXT_MUTED))
        palette.setColor(QPalette.ColorRole.Link, QColor(cls.ACCENT))
        app.setPalette(palette)
        app.setFont(Typography.body())

        app.setStyleSheet(
            f"""
            QMainWindow, QWidget {{
                background-color: {cls.BACKGROUND};
                color: {cls.TEXT};
                selection-background-color: {cls.ACCENT};
                selection-color: #FFFFFF;
            }}
            QToolBar {{
                background: {cls.TOOLBAR};
                border-bottom: 1px solid {cls.BORDER};
                spacing: 6px;
                padding: 6px 10px;
            }}
            QToolBar QToolButton {{
                background: transparent;
                border: 1px solid transparent;
                border-radius: {cls.RADIUS_SM}px;
                padding: 6px 10px;
                color: {cls.TEXT};
            }}
            QToolBar QToolButton:hover {{
                background: {cls.PANEL_HOVER};
                border-color: {cls.BORDER};
            }}
            QToolBar QToolButton:pressed {{
                background: {cls.ACCENT_SUBTLE};
                border-color: {cls.ACCENT};
            }}
            QToolBar QToolButton:disabled {{
                color: {cls.TEXT_DISABLED};
            }}
            QMenuBar {{
                background: {cls.TOOLBAR};
                border-bottom: 1px solid {cls.BORDER};
                padding: 2px 0;
            }}
            QMenuBar::item {{
                padding: 6px 12px;
                background: transparent;
            }}
            QMenuBar::item:selected {{
                background: {cls.PANEL_HOVER};
                border-radius: {cls.RADIUS_SM}px;
            }}
            QMenu {{
                background: {cls.PANEL_ELEVATED};
                border: 1px solid {cls.BORDER};
                padding: 6px;
            }}
            QMenu::item {{
                padding: 8px 28px 8px 16px;
                border-radius: {cls.RADIUS_SM}px;
            }}
            QMenu::item:selected {{
                background: {cls.ACCENT_SUBTLE};
                color: {cls.TEXT};
            }}
            QMenu::item:disabled {{
                color: {cls.TEXT_DISABLED};
            }}
            QFrame#sidebar {{
                background-color: {cls.SIDEBAR};
                border-right: 1px solid {cls.BORDER};
            }}
            QFrame#panel, QFrame#card {{
                background-color: {cls.PANEL};
                border: 1px solid {cls.BORDER_SUBTLE};
                border-radius: {cls.RADIUS_MD}px;
            }}
            QPushButton {{
                background-color: {cls.PANEL_ELEVATED};
                color: {cls.TEXT};
                border: 1px solid {cls.BORDER};
                border-radius: {cls.RADIUS_SM}px;
                padding: 9px 16px;
                min-height: 22px;
            }}
            QPushButton:hover {{
                background-color: {cls.PANEL_HOVER};
                border-color: {cls.ACCENT_HOVER};
            }}
            QPushButton:pressed {{
                background-color: {cls.ACCENT_PRESSED};
                border-color: {cls.ACCENT_PRESSED};
            }}
            QPushButton:disabled {{
                color: {cls.TEXT_DISABLED};
                border-color: {cls.BORDER_SUBTLE};
                background-color: {cls.PANEL};
            }}
            QPushButton:focus {{
                border-color: {cls.BORDER_FOCUS};
                outline: none;
            }}
            QPushButton[primary="true"] {{
                background-color: {cls.ACCENT};
                border-color: {cls.ACCENT};
                color: #FFFFFF;
                font-weight: 600;
            }}
            QPushButton[primary="true"]:hover {{
                background-color: {cls.ACCENT_HOVER};
                border-color: {cls.ACCENT_HOVER};
            }}
            QPushButton[nav="true"] {{
                text-align: left;
                padding: 10px 12px;
                border: 1px solid transparent;
                border-radius: {cls.RADIUS_SM}px;
                background-color: transparent;
            }}
            QPushButton[nav="true"]:hover {{
                background-color: {cls.PANEL_HOVER};
            }}
            QPushButton[nav="true"]:checked {{
                background-color: {cls.ACCENT_SUBTLE};
                border-color: {cls.ACCENT};
                color: {cls.TEXT};
            }}
            QPushButton[nav="true"]:focus {{
                border-color: {cls.BORDER_FOCUS};
            }}
            QLineEdit, QPlainTextEdit, QComboBox {{
                background: {cls.PANEL_ELEVATED};
                border: 1px solid {cls.BORDER};
                border-radius: {cls.RADIUS_SM}px;
                padding: 8px 10px;
                color: {cls.TEXT};
            }}
            QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus {{
                border-color: {cls.BORDER_FOCUS};
            }}
            QStatusBar {{
                background-color: {cls.SIDEBAR};
                color: {cls.TEXT_MUTED};
                border-top: 1px solid {cls.BORDER};
                padding: 2px 8px;
            }}
            QStatusBar QLabel {{
                padding: 0 10px;
            }}
            QTreeWidget {{
                background: transparent;
                border: none;
                outline: none;
            }}
            QTreeWidget::item {{
                padding: 6px 4px;
                border-radius: {cls.RADIUS_SM}px;
            }}
            QTreeWidget::item:selected {{
                background: {cls.ACCENT_SUBTLE};
                color: {cls.ACCENT_HOVER};
            }}
            QTableWidget {{
                background: {cls.PANEL};
                border: 1px solid {cls.BORDER_SUBTLE};
                border-radius: {cls.RADIUS_MD}px;
                gridline-color: {cls.BORDER_SUBTLE};
            }}
            QHeaderView::section {{
                background: {cls.PANEL_ELEVATED};
                color: {cls.TEXT_MUTED};
                border: none;
                padding: 10px;
                font-weight: 600;
            }}
            QSplitter::handle {{
                background: {cls.BORDER};
            }}
            QLabel[muted="true"] {{
                color: {cls.TEXT_MUTED};
            }}
            QLabel[title="true"] {{
                font-size: {cls.FONT_SIZE_TITLE}px;
                font-weight: 600;
            }}
            QLabel[hero="true"] {{
                font-size: {Typography.SIZE_DISPLAY}px;
                font-weight: 700;
            }}
            """
        )
