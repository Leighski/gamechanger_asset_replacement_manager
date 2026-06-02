"""AWS S3 operations via boto3."""

from __future__ import annotations

import logging
from typing import Any

from gamechanger_rename_manager.config.settings import AppSettings

logger = logging.getLogger(__name__)


def s3_key_from_file_set(base_dir: str, name: str) -> str:
    """Build S3 object key from Iconik file_set base_dir + name."""
    bd = base_dir.strip().strip("/")
    nm = name.strip().lstrip("/")
    if bd and nm:
        return f"{bd}/{nm}"
    if nm:
        return nm
    return bd


class S3Service:
    def __init__(self, settings: AppSettings) -> None:
        self._settings = settings
        self._client: Any = None

    def _get_client(self):
        if self._client is not None:
            return self._client
        import boto3

        kwargs: dict = {"region_name": self._settings.aws_region or "eu-west-1"}
        ak = self._settings.aws_access_key_id.strip()
        sk = self._settings.aws_secret_access_key.strip()
        tok = self._settings.aws_session_token.strip()
        if ak and sk:
            kwargs["aws_access_key_id"] = ak
            kwargs["aws_secret_access_key"] = sk
        if tok:
            kwargs["aws_session_token"] = tok
        self._client = boto3.client("s3", **kwargs)
        return self._client

    def resolve_key(self, asset_key: str, fallback_name: str) -> str:
        if asset_key.strip():
            return asset_key.lstrip("/")
        prefix = self._settings.s3_prefix.strip().strip("/")
        name = fallback_name.lstrip("/")
        if prefix:
            return f"{prefix}/{name}"
        return name

    def bucket(self) -> str:
        return self._settings.s3_bucket.strip()

    def object_exists(self, key: str, bucket: str | None = None) -> tuple[bool, str]:
        b = bucket or self.bucket()
        if not b or not key:
            return False, "Missing bucket or key"
        try:
            self._get_client().head_object(Bucket=b, Key=key)
            return True, "exists"
        except Exception as exc:
            code = getattr(exc, "response", {}).get("Error", {}).get("Code", "")
            if code in ("404", "NoSuchKey", "NotFound"):
                return False, "missing"
            logger.exception("S3 head_object failed")
            return False, str(exc)

    def copy_object(
        self,
        source_key: str,
        dest_key: str,
        *,
        bucket: str | None = None,
        dry_run: bool = False,
    ) -> tuple[bool, str]:
        b = bucket or self.bucket()
        if not b:
            return False, "S3 bucket not configured"
        if dry_run:
            return True, f"[dry-run] s3://{b}/{source_key} -> s3://{b}/{dest_key}"
        try:
            self._get_client().copy_object(
                Bucket=b,
                CopySource={"Bucket": b, "Key": source_key},
                Key=dest_key,
            )
            return True, f"Copied s3://{b}/{source_key} -> s3://{b}/{dest_key}"
        except Exception as exc:
            logger.exception("S3 copy_object failed")
            return False, str(exc)

    def backup_object(
        self,
        source_key: str,
        *,
        bucket: str | None = None,
        dry_run: bool = False,
    ) -> tuple[bool, str, str]:
        b = bucket or self.bucket()
        backup_prefix = self._settings.s3_backup_prefix.strip().strip("/")
        import time

        ts = time.strftime("%Y%m%d_%H%M%S")
        base = source_key.split("/")[-1]
        dest = f"{backup_prefix}/{ts}/{base}" if backup_prefix else f"backups/{ts}/{base}"
        ok, msg = self.copy_object(source_key, dest, bucket=b, dry_run=dry_run)
        return ok, msg, dest
