"""Catalogue definitions and S3 URI parsing."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from models.catalogue import CatalogueDefinition, S3Location
from services.paths import CATALOGUES_PATH

logger = logging.getLogger(__name__)

S3_URI_RE = re.compile(r"^s3://([^/]+)/?(.*)$", re.IGNORECASE)


def parse_s3_uri(uri: str) -> S3Location:
    match = S3_URI_RE.match(uri.strip())
    if not match:
        raise ValueError(f"Invalid S3 URI: {uri}")
    bucket = match.group(1)
    prefix = (match.group(2) or "").strip("/")
    return S3Location(bucket=bucket, prefix=prefix)


class CatalogueService:
    def __init__(self, catalogues_path: Path | None = None) -> None:
        self._path = catalogues_path or CATALOGUES_PATH
        self._catalogues: dict[str, CatalogueDefinition] = {}
        self.reload()

    def reload(self) -> None:
        self._catalogues.clear()
        if not self._path.exists():
            logger.warning("Catalogues file missing: %s", self._path)
            return
        with self._path.open(encoding="utf-8") as fh:
            raw = json.load(fh)
        if not isinstance(raw, dict):
            return
        for name, entry in raw.items():
            if not isinstance(entry, dict):
                continue
            s3_path = str(entry.get("s3_path", "")).strip()
            if not s3_path:
                continue
            try:
                location = parse_s3_uri(s3_path)
                self._catalogues[name] = CatalogueDefinition(
                    name=name,
                    s3_path=s3_path,
                    location=location,
                )
            except ValueError as exc:
                logger.warning("Skipping catalogue %s: %s", name, exc)

    def names(self) -> list[str]:
        return sorted(self._catalogues.keys())

    def get(self, name: str) -> CatalogueDefinition | None:
        return self._catalogues.get(name)

    def resolve(
        self,
        catalogue_name: str,
        *,
        custom_s3_path: str = "",
    ) -> CatalogueDefinition:
        if catalogue_name == "CUSTOM":
            path = custom_s3_path.strip()
            if not path:
                raise ValueError("Custom catalogue requires an S3 path in settings.")
            location = parse_s3_uri(path)
            return CatalogueDefinition(name="CUSTOM", s3_path=path, location=location)
        cat = self.get(catalogue_name)
        if cat is None:
            raise ValueError(f"Unknown catalogue: {catalogue_name}")
        return cat
