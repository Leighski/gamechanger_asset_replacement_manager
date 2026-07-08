"""Local and remote content fingerprinting for replacement verification."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ContentFingerprint:
    size: int
    md5: str
    sha1: str

    def matches(self, other: ContentFingerprint) -> bool:
        return self.size == other.size and self.md5 == other.md5 and self.sha1 == other.sha1


def fingerprint_file(path: Path) -> ContentFingerprint:
    md5 = hashlib.md5()
    sha1 = hashlib.sha1()
    size = 0
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            md5.update(chunk)
            sha1.update(chunk)
    return ContentFingerprint(size=size, md5=md5.hexdigest(), sha1=sha1.hexdigest())


def fingerprint_bytes(data: bytes) -> ContentFingerprint:
    return ContentFingerprint(
        size=len(data),
        md5=hashlib.md5(data).hexdigest(),
        sha1=hashlib.sha1(data).hexdigest(),
    )


def etag_to_md5(etag: str | None) -> str | None:
    if not etag:
        return None
    value = etag.strip().strip('"')
    if not value or "-" in value:
        return None
    return value.lower()
