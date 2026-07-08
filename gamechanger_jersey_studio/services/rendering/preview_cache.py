"""Preview Cache — cache rendered layers and invalidate selectively."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from PIL import Image


@dataclass
class CacheStats:
    hits: int = 0
    misses: int = 0


@dataclass
class PreviewCache:
    """In-memory layer cache with per-layer invalidation."""

    _layers: dict[str, Image.Image] = field(default_factory=dict)
    _keys: dict[str, str] = field(default_factory=dict)
    stats: CacheStats = field(default_factory=CacheStats)

    def get(self, layer_id: str, cache_key: str) -> Image.Image | None:
        stored_key = self._keys.get(layer_id)
        if stored_key == cache_key and layer_id in self._layers:
            self.stats.hits += 1
            return self._layers[layer_id].copy()
        self.stats.misses += 1
        return None

    def put(self, layer_id: str, cache_key: str, image: Image.Image) -> None:
        self._keys[layer_id] = cache_key
        self._layers[layer_id] = image.copy()

    def invalidate(self, layer_id: str | None = None) -> None:
        if layer_id is None:
            self._layers.clear()
            self._keys.clear()
            return
        self._layers.pop(layer_id, None)
        self._keys.pop(layer_id, None)

    @staticmethod
    def make_key(*parts: str) -> str:
        payload = "|".join(parts)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
