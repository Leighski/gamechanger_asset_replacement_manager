"""Undo and redo support for Design Specification changes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class DesignSpecChange:
    property_name: str
    old_value: Any
    new_value: Any


class DesignSpecUndoStack:
    """Reversible command stack for design specification edits."""

    def __init__(self, *, max_depth: int = 100) -> None:
        self._max_depth = max_depth
        self._undo: list[DesignSpecChange] = []
        self._redo: list[DesignSpecChange] = []

    def clear(self) -> None:
        self._undo.clear()
        self._redo.clear()

    def push(self, change: DesignSpecChange) -> None:
        if (
            self._undo
            and self._undo[-1].property_name == change.property_name
            and self._undo[-1].new_value == change.new_value
            and self._undo[-1].old_value == change.old_value
        ):
            return
        self._undo.append(change)
        if len(self._undo) > self._max_depth:
            self._undo.pop(0)
        self._redo.clear()

    def can_undo(self) -> bool:
        return bool(self._undo)

    def can_redo(self) -> bool:
        return bool(self._redo)

    def undo(self) -> DesignSpecChange | None:
        if not self._undo:
            return None
        change = self._undo.pop()
        self._redo.append(change)
        return change

    def redo(self) -> DesignSpecChange | None:
        if not self._redo:
            return None
        change = self._redo.pop()
        self._undo.append(change)
        return change
