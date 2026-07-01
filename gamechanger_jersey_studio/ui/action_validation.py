"""Startup validation for QAction callbacks — prevents menu-triggered crashes."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtGui import QAction

from services.logging_manager import get_logger

logger = get_logger()


def validate_action_callbacks(
    owner: object,
    bindings: list[tuple[QAction, str]],
) -> list[str]:
    """Verify named callbacks exist on owner. Disable broken actions. Return errors."""
    errors: list[str] = []
    for action, method_name in bindings:
        callback: Callable[..., object] | None = getattr(owner, method_name, None)
        if callback is None or not callable(callback):
            label = action.text().replace("&", "")
            message = f"Menu action '{label}' references missing callback '{method_name}'"
            logger.error(message)
            action.setEnabled(False)
            errors.append(message)
    return errors
