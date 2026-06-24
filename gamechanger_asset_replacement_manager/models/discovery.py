"""File discovery and preflight models."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class FileIssue(str, Enum):
    APPLE_DOUBLE = "apple_double"
    HIDDEN = "hidden"
    INVALID_EXTENSION = "invalid_extension"
    DUPLICATE_NAME = "duplicate_name"
    TRAILING_SPACE = "trailing_space"
    DOUBLE_SPACE = "double_space"
    LEADING_SPACE = "leading_space"
    INVISIBLE_CHAR = "invisible_char"
    EXTENSION_CASE = "extension_case"
    SANITISATION_CHANGED = "sanitisation_changed"


class PreflightStatus(str, Enum):
    READY = "ready"
    SKIP = "skip"
    ERROR = "error"
    WARNING = "warning"


class S3Status(str, Enum):
    EXISTS = "EXISTS"
    MISSING = "MISSING"
    ERROR = "ERROR"


@dataclass
class SanitisationOptions:
    remove_apple_double: bool = True
    remove_trailing_spaces: bool = True
    remove_duplicate_spaces: bool = True
    remove_invisible_characters: bool = True
    standardise_extension_case: bool = True


@dataclass
class DiscoveredFile:
    path: Path
    original_filename: str
    clean_filename: str
    size_bytes: int
    issues: list[FileIssue] = field(default_factory=list)
    excluded: bool = False
    exclude_reason: str = ""


@dataclass
class DiscoveryResult:
    source_folder: Path
    files: list[DiscoveredFile]
    duplicate_names: list[str]
    hidden_skipped: int
    apple_double_found: int

    @property
    def media_count(self) -> int:
        return sum(1 for f in self.files if not f.excluded)


@dataclass
class PreflightRow:
    discovered: DiscoveredFile
    s3_exists: bool
    s3_size: int | None
    size_mismatch: bool
    action: str  # REPLACE | SKIP
    status: PreflightStatus
    status_message: str
    s3_key: str = ""
    s3_status: str = ""
    catalogue_s3_exists: bool = False
    catalogue_s3_status: str = ""
    governance_status: str = ""
    resolved_asset_id: str = ""
    resolved_file_set_id: str = ""
    resolved_iconik_s3_key: str = ""
    resolution_method: str = ""
    metadata_status: str = ""
    governance_warnings: str = ""
    governance_message: str = ""
