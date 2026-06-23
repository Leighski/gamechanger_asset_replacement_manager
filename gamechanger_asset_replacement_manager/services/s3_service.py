"""AWS S3 operations via boto3."""

from __future__ import annotations

import logging
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from models.catalogue import S3Location
from services.content_verification import ContentFingerprint, etag_to_md5, fingerprint_file

logger = logging.getLogger(__name__)


@dataclass
class S3ObjectInfo:
    exists: bool
    size: int | None
    etag: str | None
    error: str | None = None


class S3Service:
    def __init__(
        self,
        *,
        region: str = "eu-west-1",
        access_key_id: str = "",
        secret_access_key: str = "",
        session_token: str = "",
    ) -> None:
        self._region = region
        self._access_key_id = access_key_id.strip()
        self._secret_access_key = secret_access_key.strip()
        self._session_token = session_token.strip()
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        import boto3

        kwargs: dict[str, Any] = {"region_name": self._region or "eu-west-1"}
        if self._access_key_id and self._secret_access_key:
            kwargs["aws_access_key_id"] = self._access_key_id
            kwargs["aws_secret_access_key"] = self._secret_access_key
        if self._session_token:
            kwargs["aws_session_token"] = self._session_token
        self._client = boto3.client("s3", **kwargs)
        return self._client

    def head_object(self, location: S3Location, key: str) -> S3ObjectInfo:
        full_key = key.lstrip("/")
        try:
            resp = self._get_client().head_object(Bucket=location.bucket, Key=full_key)
            size = resp.get("ContentLength")
            return S3ObjectInfo(
                exists=True,
                size=int(size) if size is not None else None,
                etag=resp.get("ETag"),
            )
        except Exception as exc:
            code = ""
            if hasattr(exc, "response"):
                err = getattr(exc, "response", {}).get("Error", {})
                code = err.get("Code", "")
            if code in ("404", "NoSuchKey", "NotFound", "403"):
                if code == "403":
                    logger.warning("S3 head denied for %s/%s", location.bucket, full_key)
                return S3ObjectInfo(exists=False, size=None, etag=None)
            logger.exception("S3 head_object failed for %s", full_key)
            return S3ObjectInfo(exists=False, size=None, etag=None, error=str(exc))

    def upload_file(
        self,
        local_path: str,
        location: S3Location,
        key: str,
        *,
        content_type: str | None = None,
    ) -> tuple[bool, str]:
        full_key = key.lstrip("/")
        extra: dict[str, Any] = {}
        if content_type:
            extra["ContentType"] = content_type
        try:
            if extra:
                self._get_client().upload_file(
                    local_path,
                    location.bucket,
                    full_key,
                    ExtraArgs=extra,
                )
            else:
                self._get_client().upload_file(local_path, location.bucket, full_key)
            logger.info("Uploaded %s -> s3://%s/%s", local_path, location.bucket, full_key)
            return True, "success"
        except Exception as exc:
            logger.exception("Upload failed for %s", full_key)
            return False, str(exc)

    @staticmethod
    def content_type_for_filename(filename: str) -> str:
        lower = filename.lower()
        if lower.endswith(".mp4"):
            return "video/mp4"
        if lower.endswith(".mov"):
            return "video/quicktime"
        if lower.endswith(".wav"):
            return "audio/wav"
        return "application/octet-stream"

    def download_object(
        self,
        location: S3Location,
        key: str,
        *,
        dest_path: Path | None = None,
    ) -> tuple[Path | None, str | None]:
        full_key = key.lstrip("/")
        try:
            if dest_path is None:
                suffix = Path(full_key).suffix or ".bin"
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
                tmp.close()
                dest_path = Path(tmp.name)
            self._get_client().download_file(location.bucket, full_key, str(dest_path))
            return dest_path, None
        except Exception as exc:
            logger.exception("S3 download failed for %s", full_key)
            return None, str(exc)

    def fingerprint_remote_object(
        self,
        location: S3Location,
        key: str,
    ) -> tuple[ContentFingerprint | None, str | None, str | None]:
        """Return fingerprint, etag, error for an S3 object."""
        info = self.head_object(location, key)
        if not info.exists:
            return None, None, info.error or "object not found"
        downloaded, err = self.download_object(location, key)
        if downloaded is None:
            return None, info.etag, err
        try:
            fp = fingerprint_file(downloaded)
            return fp, info.etag, None
        finally:
            try:
                downloaded.unlink(missing_ok=True)
            except OSError:
                pass

    def remote_matches_local(
        self,
        location: S3Location,
        key: str,
        local_path: Path,
    ) -> tuple[bool, str]:
        local_fp = fingerprint_file(local_path)
        remote_fp, etag, err = self.fingerprint_remote_object(location, key)
        if remote_fp is None:
            return False, err or "remote fingerprint unavailable"
        etag_md5 = etag_to_md5(etag)
        if etag_md5 and etag_md5 == local_fp.md5 and remote_fp.md5 == local_fp.md5:
            return True, "etag and content match local source"
        if remote_fp.matches(local_fp):
            return True, "remote content matches local source"
        return (
            False,
            "remote mismatch "
            f"(local size={local_fp.size} md5={local_fp.md5} "
            f"remote size={remote_fp.size} md5={remote_fp.md5} etag={etag})",
        )

    @staticmethod
    def iconik_key_from_file_set(base_dir: str, name: str) -> str:
        bd = base_dir.strip().strip("/")
        nm = name.strip().lstrip("/")
        if bd and nm:
            return f"{bd}/{nm}"
        if nm:
            return nm
        return bd

    def test_connection(self, location: S3Location) -> tuple[bool, str]:
        try:
            prefix = location.prefix.strip("/")
            kwargs: dict[str, Any] = {"Bucket": location.bucket, "MaxKeys": 1}
            if prefix:
                kwargs["Prefix"] = f"{prefix}/"
            self._get_client().list_objects_v2(**kwargs)
            return True, f"Connected to s3://{location.bucket}/{prefix or ''}"
        except Exception as exc:
            logger.exception("S3 connection test failed")
            return False, str(exc)
