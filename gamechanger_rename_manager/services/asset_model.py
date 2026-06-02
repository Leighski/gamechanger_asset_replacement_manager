"""Domain models for assets, file sets, and rename planning."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class VariantType(str, Enum):
    MAIN = "MAIN"
    CFX = "CFX"
    MT = "MT"
    UNKNOWN = "UNKNOWN"


class IntegrityLevel(str, Enum):
    OK = "ok"
    WARN = "warn"
    ERROR = "error"


@dataclass
class IntegrityIssue:
    level: IntegrityLevel
    code: str
    message: str


@dataclass
class FileSetRecord:
    fileset_id: str
    name: str
    base_dir: str = ""
    storage_path: str = ""
    bucket: str = ""
    s3_key: str = ""
    format_id: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class AssetRecord:
    asset_id: str
    title: str
    file_set_name: str = ""
    fileset_id: str = ""
    duration_sec: float | None = None
    variant: VariantType = VariantType.UNKNOWN
    storage_path: str = ""
    s3_key: str = ""
    thumbnail_url: str = ""
    integrity_status: IntegrityLevel = IntegrityLevel.OK
    integrity_issues: list[IntegrityIssue] = field(default_factory=list)
    search_hit: dict[str, Any] = field(default_factory=dict)
    file_sets: list[FileSetRecord] = field(default_factory=list)
    linked_variants: dict[VariantType, str] = field(default_factory=dict)
    collection_ids: list[str] = field(default_factory=list)
    collection_breadcrumb: str = ""
    collection_paths: list[str] = field(default_factory=list)
    has_duplicate_filename: bool = False
    is_deleted: bool = False

    @property
    def is_operational(self) -> bool:
        return not self.is_deleted

    @property
    def display_filename(self) -> str:
        return self.file_set_name or self.title


@dataclass
class PlannedOperation:
    phase: str
    description: str
    detail: str = ""


@dataclass
class RenamePlan:
    asset: AssetRecord
    old_filename: str
    new_filename: str
    variant: VariantType
    operations: list[PlannedOperation] = field(default_factory=list)
    warnings: list[IntegrityIssue] = field(default_factory=list)
