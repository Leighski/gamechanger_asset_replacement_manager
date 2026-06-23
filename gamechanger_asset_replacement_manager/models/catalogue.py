"""Catalogue and S3 location models."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class S3Location:
    """Parsed S3 URI."""

    bucket: str
    prefix: str  # no leading slash, trailing slash optional

    @property
    def uri(self) -> str:
        p = self.prefix.strip("/")
        if p:
            return f"s3://{self.bucket}/{p}/"
        return f"s3://{self.bucket}/"

    def key_for_filename(self, filename: str) -> str:
        name = filename.lstrip("/")
        prefix = self.prefix.strip("/")
        if prefix:
            return f"{prefix}/{name}"
        return name


@dataclass(frozen=True)
class CatalogueDefinition:
    """Named catalogue mapping to an S3 prefix."""

    name: str
    s3_path: str
    location: S3Location
