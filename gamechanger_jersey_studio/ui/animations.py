"""Subtle UI animations."""

from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QTimer
from PySide6.QtWidgets import QGraphicsOpacityEffect, QWidget


def fade_in(widget: QWidget, *, duration_ms: int = 220, start: float = 0.0) -> QPropertyAnimation:
    effect = QGraphicsOpacityEffect(widget)
    widget.setGraphicsEffect(effect)
    animation = QPropertyAnimation(effect, b"opacity", widget)
    animation.setDuration(duration_ms)
    animation.setStartValue(start)
    animation.setEndValue(1.0)
    animation.setEasingCurve(QEasingCurve.Type.OutCubic)
    animation.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
    return animation


def crossfade_stack(stack, index: int, *, duration_ms: int = 160) -> None:
    """Switch stacked widget index with a brief fade."""
    widget = stack.widget(index)
    if widget is None:
        stack.setCurrentIndex(index)
        return
    stack.setCurrentIndex(index)
    fade_in(widget, duration_ms=duration_ms)
