"""Recursive media file discovery."""

from __future__ import annotations

import logging
from collections import Counter
from pathlib import Path

from models.discovery import DiscoveredFile, DiscoveryResult, FileIssue
from services.filename_sanitizer import (
    is_apple_double,
    is_hidden,
    is_ignored_file,
    is_valid_media_extension,
    sanitise_filename,
)
from models.discovery import SanitisationOptions

logger = logging.getLogger(__name__)


class FileDiscoveryService:
    def scan(
        self,
        source_folder: Path,
        options: SanitisationOptions,
    ) -> DiscoveryResult:
        logger.info("Scanning folder: %s", source_folder)
        if not source_folder.is_dir():
            raise NotADirectoryError(f"Source folder does not exist: {source_folder}")

        discovered: list[DiscoveredFile] = []
        hidden_skipped = 0
        apple_double_found = 0
        name_counter: Counter[str] = Counter()

        for path in sorted(source_folder.rglob("*")):
            if not path.is_file():
                continue
            name = path.name

            if is_ignored_file(name):
                logger.debug("Ignored system file: %s", name)
                continue

            if is_apple_double(name):
                apple_double_found += 1
                if options.remove_apple_double:
                    discovered.append(
                        DiscoveredFile(
                            path=path,
                            original_filename=name,
                            clean_filename="",
                            size_bytes=path.stat().st_size,
                            issues=[FileIssue.APPLE_DOUBLE],
                            excluded=True,
                            exclude_reason="AppleDouble file (excluded from upload)",
                        )
                    )
                    continue

            if is_hidden(name) and name.lower() not in {".ds_store", "thumbs.db"}:
                hidden_skipped += 1
                continue

            if not is_valid_media_extension(name):
                continue

            clean_name, issues = sanitise_filename(name, options)
            if not clean_name:
                discovered.append(
                    DiscoveredFile(
                        path=path,
                        original_filename=name,
                        clean_filename="",
                        size_bytes=path.stat().st_size,
                        issues=issues,
                        excluded=True,
                        exclude_reason="Could not produce clean filename",
                    )
                )
                continue

            name_counter[clean_name.lower()] += 1
            if FileIssue.DUPLICATE_NAME not in issues and name_counter[clean_name.lower()] > 1:
                issues = list(issues)
                issues.append(FileIssue.DUPLICATE_NAME)

            discovered.append(
                DiscoveredFile(
                    path=path,
                    original_filename=name,
                    clean_filename=clean_name,
                    size_bytes=path.stat().st_size,
                    issues=issues,
                )
            )

        duplicate_names = [n for n, c in name_counter.items() if c > 1]
        for item in discovered:
            if item.clean_filename.lower() in duplicate_names:
                if FileIssue.DUPLICATE_NAME not in item.issues:
                    item.issues.append(FileIssue.DUPLICATE_NAME)

        logger.info(
            "Scan complete: %s media files, %s duplicates, %s AppleDouble",
            sum(1 for f in discovered if not f.excluded),
            len(duplicate_names),
            apple_double_found,
        )
        return DiscoveryResult(
            source_folder=source_folder,
            files=discovered,
            duplicate_names=duplicate_names,
            hidden_skipped=hidden_skipped,
            apple_double_found=apple_double_found,
        )
