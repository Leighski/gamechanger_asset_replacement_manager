"""Render Queue — coalesce rapid render requests."""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock


@dataclass
class RenderQueue:
    """Track pending render generation tokens."""

    _pending_token: int = 0
    _lock: Lock = field(default_factory=Lock)

    def enqueue(self) -> int:
        with self._lock:
            self._pending_token += 1
            return self._pending_token

    def is_current(self, token: int) -> bool:
        with self._lock:
            return token == self._pending_token
