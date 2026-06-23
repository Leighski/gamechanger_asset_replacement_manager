"""Filename detection and sanitisation."""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from models.discovery import FileIssue, SanitisationOptions

MEDIA_EXTENSIONS = {".mp4", ".mov"}
IGNORED_FILENAMES = {".ds_store", "thumbs.db"}
INVISIBLE_RE = re.compile(
    r"[\u200b\u200c\u200d\ufeff\u00a0\u2060\u180e\u202a-\u202e\u2066-\u2069]"
)
APPLE_DOUBLE_PREFIX = "._"


def is_ignored_file(name: str) -> bool:
    return name.lower() in IGNORED_FILENAMES or name.startswith(APPLE_DOUBLE_PREFIX)


def is_apple_double(name: str) -> bool:
    return name.startswith(APPLE_DOUBLE_PREFIX)


def is_hidden(name: str) -> bool:
    return name.startswith(".")


def extension_for(name: str) -> str:
    return Path(name).suffix.lower()


def is_valid_media_extension(name: str) -> bool:
    return extension_for(name) in MEDIA_EXTENSIONS


def detect_issues(name: str) -> list[FileIssue]:
    issues: list[FileIssue] = []
    if is_apple_double(name):
        issues.append(FileIssue.APPLE_DOUBLE)
    if is_hidden(name) and name.lower() not in IGNORED_FILENAMES:
        issues.append(FileIssue.HIDDEN)
    if not is_valid_media_extension(name):
        issues.append(FileIssue.INVALID_EXTENSION)
    stem = Path(name).stem
    if stem != stem.rstrip():
        issues.append(FileIssue.TRAILING_SPACE)
    if stem != stem.lstrip():
        issues.append(FileIssue.LEADING_SPACE)
    if "  " in stem:
        issues.append(FileIssue.DOUBLE_SPACE)
    if INVISIBLE_RE.search(name):
        issues.append(FileIssue.INVISIBLE_CHAR)
    suffix = Path(name).suffix
    if suffix and suffix != suffix.lower():
        issues.append(FileIssue.EXTENSION_CASE)
    return issues


def sanitise_filename(name: str, options: SanitisationOptions) -> tuple[str, list[FileIssue]]:
    """Return cleaned filename and issues that were addressed."""
    issues = detect_issues(name)
    if is_apple_double(name) and options.remove_apple_double:
        return "", issues

    path = Path(name)
    stem = path.stem
    ext = path.suffix

    if options.remove_invisible_characters:
        stem = INVISIBLE_RE.sub("", stem)
        ext = INVISIBLE_RE.sub("", ext)

    if options.remove_trailing_spaces:
        stem = stem.rstrip()
        ext = ext.rstrip()

    if options.remove_duplicate_spaces:
        stem = re.sub(r" +", " ", stem).strip()

    if options.standardise_extension_case and ext:
        ext = ext.lower()

    cleaned = f"{stem}{ext}" if stem else ""
    if cleaned and cleaned != name:
        if FileIssue.SANITISATION_CHANGED not in issues:
            issues = list(issues)
            issues.append(FileIssue.SANITISATION_CHANGED)
    return cleaned, issues
