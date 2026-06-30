"""In-memory byte store for reference images during an open project session."""

from __future__ import annotations

from pathlib import Path


class ReferenceImageByteStore:
    """Maps storage_path → immutable image bytes."""

    def __init__(self) -> None:
        self._bytes: dict[str, bytes] = {}

    def clear(self) -> None:
        self._bytes.clear()

    def put(self, storage_path: str, data: bytes) -> None:
        self._bytes[storage_path] = data

    def get(self, storage_path: str) -> bytes | None:
        return self._bytes.get(storage_path)

    def remove(self, storage_path: str) -> None:
        self._bytes.pop(storage_path, None)

    def items(self) -> list[tuple[str, bytes]]:
        return list(self._bytes.items())

    def __len__(self) -> int:
        return len(self._bytes)


def storage_path_for(image_id: str, ext: str) -> str:
    normalised = ext if ext.startswith(".") else f".{ext}"
    return f"references/images/{image_id}{normalised}"
