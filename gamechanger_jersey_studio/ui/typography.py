"""Typography system for consistent text hierarchy."""

from __future__ import annotations

import sys

from PySide6.QtGui import QFont


def _body_family() -> str:
    if sys.platform == "darwin":
        return ".AppleSystemUIFont"
    if sys.platform.startswith("win"):
        return "Segoe UI"
    return "Inter"


def _mono_family() -> str:
    if sys.platform == "darwin":
        return "Menlo"
    if sys.platform.startswith("win"):
        return "Cascadia Mono"
    return "JetBrains Mono"


class Typography:
    FAMILY_BODY = _body_family()
    FAMILY_MONO = _mono_family()

    SIZE_CAPTION = 11
    SIZE_BODY = 13
    SIZE_SUBHEADING = 15
    SIZE_HEADING = 20
    SIZE_DISPLAY = 26

    WEIGHT_REGULAR = QFont.Weight.Normal
    WEIGHT_MEDIUM = QFont.Weight.Medium
    WEIGHT_SEMIBOLD = QFont.Weight.DemiBold
    WEIGHT_BOLD = QFont.Weight.Bold

    @classmethod
    def font(
        cls,
        *,
        size: int = SIZE_BODY,
        weight: QFont.Weight = WEIGHT_REGULAR,
        family: str | None = None,
    ) -> QFont:
        font = QFont(family or cls.FAMILY_BODY, size)
        font.setWeight(weight)
        return font

    @classmethod
    def display(cls) -> QFont:
        return cls.font(size=cls.SIZE_DISPLAY, weight=cls.WEIGHT_BOLD)

    @classmethod
    def heading(cls) -> QFont:
        return cls.font(size=cls.SIZE_HEADING, weight=cls.WEIGHT_SEMIBOLD)

    @classmethod
    def subheading(cls) -> QFont:
        return cls.font(size=cls.SIZE_SUBHEADING, weight=cls.WEIGHT_MEDIUM)

    @classmethod
    def body(cls) -> QFont:
        return cls.font(size=cls.SIZE_BODY)

    @classmethod
    def caption(cls) -> QFont:
        return cls.font(size=cls.SIZE_CAPTION)

    @classmethod
    def status(cls) -> QFont:
        return cls.font(size=cls.SIZE_CAPTION, weight=cls.WEIGHT_MEDIUM)

    @classmethod
    def mono_caption(cls) -> QFont:
        return cls.font(size=cls.SIZE_CAPTION, family=cls.FAMILY_MONO)
