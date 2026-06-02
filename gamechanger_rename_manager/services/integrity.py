"""Integrity analysis before rename execution."""

from __future__ import annotations

import logging
from collections import defaultdict

from gamechanger_rename_manager.services.asset_model import (
    AssetRecord,
    IntegrityIssue,
    IntegrityLevel,
    VariantType,
)
from gamechanger_rename_manager.services.s3_service import S3Service, s3_key_from_file_set
from gamechanger_rename_manager.services.variant import linked_variant_filenames, variant_base_stem

logger = logging.getLogger(__name__)


def _primary_file_set(asset: AssetRecord):
    for fs in asset.file_sets:
        if fs.fileset_id and fs.fileset_id == asset.fileset_id:
            return fs
    return asset.file_sets[0] if asset.file_sets else None


def analyze_assets(assets: list[AssetRecord], s3: S3Service | None) -> None:
    """Mutate assets in-place with integrity_status and integrity_issues."""
    operational = [a for a in assets if a.is_operational]
    deleted_n = len(assets) - len(operational)
    if deleted_n:
        logger.info(
            "Integrity analysis: excluding %s soft-deleted asset(s) from collision checks",
            deleted_n,
        )

    by_filename: dict[str, list[AssetRecord]] = defaultdict(list)
    by_s3_key: dict[str, list[AssetRecord]] = defaultdict(list)
    by_base: dict[str, list[AssetRecord]] = defaultdict(list)

    for a in operational:
        fn = a.display_filename
        if fn:
            by_filename[fn.lower()].append(a)
        key = a.s3_key.strip()
        if key:
            by_s3_key[key].append(a)
        base = variant_base_stem(fn or a.title)
        if base:
            by_base[base.lower()].append(a)

    for a in assets:
        if a.is_deleted:
            a.integrity_issues = []
            a.has_duplicate_filename = False
            a.integrity_status = IntegrityLevel.OK
            continue

        issues: list[IntegrityIssue] = []

        if a.title and a.file_set_name and a.title.strip() != a.file_set_name.strip():
            issues.append(
                IntegrityIssue(
                    IntegrityLevel.WARN,
                    "title_mismatch",
                    f"asset.title ({a.title!r}) != file_set.name ({a.file_set_name!r})",
                )
            )

        if len(by_filename.get(a.display_filename.lower(), [])) > 1:
            issues.append(
                IntegrityIssue(
                    IntegrityLevel.WARN,
                    "duplicate_filename",
                    f"Duplicate filename across {len(by_filename[a.display_filename.lower()])} assets",
                )
            )

        key = a.s3_key.strip()
        if key and len(by_s3_key.get(key, [])) > 1:
            issues.append(
                IntegrityIssue(
                    IntegrityLevel.WARN,
                    "shared_s3_object",
                    f"Multiple assets reference S3 key: {key}",
                )
            )

        if s3 and key:
            exists, detail = s3.object_exists(key, a.file_sets[0].bucket if a.file_sets else None)
            if not exists:
                issues.append(
                    IntegrityIssue(
                        IntegrityLevel.ERROR,
                        "missing_s3",
                        f"S3 object missing ({detail}): {key}",
                    )
                )

        base = variant_base_stem(a.display_filename or a.title)
        family = by_base.get(base.lower(), [])
        present = {x.variant for x in family}
        expected = {VariantType.MAIN, VariantType.CFX, VariantType.MT}
        missing = expected - present
        if a.variant == VariantType.MAIN and missing:
            names = linked_variant_filenames(a.display_filename)
            missing_names = [names[v] for v in sorted(missing, key=lambda x: x.value)]
            issues.append(
                IntegrityIssue(
                    IntegrityLevel.WARN,
                    "missing_variants",
                    f"Linked variants not in search set: {', '.join(missing_names)}",
                )
            )

        a.has_duplicate_filename = len(by_filename.get(a.display_filename.lower(), [])) > 1
        a.integrity_issues = issues
        if any(i.level == IntegrityLevel.ERROR for i in issues):
            a.integrity_status = IntegrityLevel.ERROR
        elif issues:
            a.integrity_status = IntegrityLevel.WARN
        else:
            a.integrity_status = IntegrityLevel.OK


def analyze_rename_plan(
    asset: AssetRecord,
    new_filename: str,
    s3: S3Service | None,
) -> list[IntegrityIssue]:
    if asset.is_deleted:
        return [
            IntegrityIssue(
                IntegrityLevel.ERROR,
                "asset_deleted",
                "Asset is soft-deleted in Iconik — cannot rename",
            )
        ]
    issues = list(asset.integrity_issues)
    if not new_filename.strip():
        issues.append(IntegrityIssue(IntegrityLevel.ERROR, "empty_name", "New filename is empty"))
    if asset.display_filename.strip() == new_filename.strip():
        issues.append(
            IntegrityIssue(IntegrityLevel.WARN, "no_change", "New filename matches current file_set name")
        )
    dest_key = ""
    if s3:
        fs = _primary_file_set(asset)
        if fs and fs.base_dir:
            dest_key = s3_key_from_file_set(fs.base_dir, new_filename)
        else:
            dest_key = s3.resolve_key(asset.s3_key, new_filename)
        src_key = asset.s3_key or (s3_key_from_file_set(fs.base_dir, fs.name) if fs else "")
        if src_key and dest_key:
            exists, _ = s3.object_exists(dest_key)
            if exists and dest_key != src_key:
                issues.append(
                    IntegrityIssue(
                        IntegrityLevel.ERROR,
                        "dest_exists",
                        f"Destination S3 key already exists: {dest_key}",
                    )
                )
    return issues
