"""Iconik lookup, direct replacement, and post-replacement preservation verification."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import requests

logger = logging.getLogger(__name__)

VERIFY_PASS = "PASS"
VERIFY_WARNING = "WARNING"
VERIFY_FAIL = "FAIL"

METADATA_STATUS_AVAILABLE = "AVAILABLE"
METADATA_STATUS_MISSING = "MISSING"
METADATA_STATUS_ERROR = "ERROR"

REPLACEMENT_DIRECT_FILE = "DIRECT_FILE_REPLACEMENT"
REPLACEMENT_DIRECT_FILESET = "DIRECT_FILESET_REPLACEMENT"
REPLACEMENT_SCAN_FALLBACK = "SCAN_FALLBACK"


@dataclass(frozen=True)
class MetadataLookupResult:
    status: str
    field_count: int = 0
    detail: str = ""


@dataclass(frozen=True)
class IconikAssetReference:
    asset_id: str
    file_set_id: str
    file_id: str
    format_id: str
    storage_id: str
    filename: str
    original_filename: str
    file_size: int
    metadata_field_count: int
    metadata_status: str = METADATA_STATUS_AVAILABLE
    iconik_base_dir: str = ""
    iconik_file_name: str = ""
    iconik_s3_key: str = ""
    storage_path: str = ""


@dataclass(frozen=True)
class IconikVerificationResult:
    asset_preserved: bool
    file_set_preserved: bool
    metadata_preserved: bool
    status: str
    message: str


@dataclass(frozen=True)
class DirectReplacementResult:
    success: bool
    method: str
    message: str


class IconikVerificationService:
    def __init__(
        self,
        *,
        base_url: str,
        app_id: str,
        auth_token: str,
        storage_id: str,
        timeout_sec: int = 60,
    ) -> None:
        self._base = (base_url or "https://app.iconik.io/API").rstrip("/") + "/"
        self._app_id = app_id.strip()
        self._auth_token = auth_token.strip()
        self._storage_id = storage_id.strip()
        self._timeout = timeout_sec
        self._session = requests.Session()
        self._session.headers.update(
            {
                "App-ID": self._app_id,
                "Auth-Token": self._auth_token,
                "Accept": "application/json",
                "Content-Type": "application/json",
            }
        )

    def configured(self) -> bool:
        return bool(self._app_id and self._auth_token and self._storage_id)

    def _url(self, path: str) -> str:
        return urljoin(self._base, path.lstrip("/"))

    def _get(self, path: str, *, params: dict[str, str] | None = None) -> Any:
        resp = self._session.get(self._url(path), params=params or {}, timeout=self._timeout)
        resp.raise_for_status()
        return resp.json() if resp.content else None

    def _post(self, path: str, *, json_body: dict | None = None) -> tuple[int, Any, str]:
        try:
            resp = self._session.post(
                self._url(path),
                json=json_body,
                timeout=self._timeout,
            )
            text = resp.text[:500] if resp.text else ""
            try:
                data = resp.json() if resp.content else None
            except ValueError:
                data = None
            return resp.status_code, data, text
        except requests.RequestException as exc:
            return 0, None, str(exc)

    def _patch(self, path: str, *, json_body: dict) -> tuple[bool, str]:
        try:
            resp = self._session.patch(self._url(path), json=json_body, timeout=self._timeout)
            if resp.status_code in (200, 201, 204):
                return True, "OK"
            return False, f"HTTP {resp.status_code}: {resp.text[:200]}"
        except requests.RequestException as exc:
            return False, str(exc)

    def _put(self, path: str, *, json_body: dict) -> tuple[bool, str]:
        try:
            resp = self._session.put(self._url(path), json=json_body, timeout=self._timeout)
            if resp.status_code in (200, 201, 204):
                return True, "OK"
            return False, f"HTTP {resp.status_code}: {resp.text[:200]}"
        except requests.RequestException as exc:
            return False, str(exc)

    def get_asset(self, asset_id: str) -> dict[str, Any]:
        data = self._get(f"assets/v1/assets/{asset_id}/")
        if not isinstance(data, dict):
            raise ValueError(f"Asset {asset_id} not found")
        return data

    def search_by_filename(self, filename: str) -> list[dict[str, Any]]:
        """Search Iconik for asset candidates; file_set.name exact match is applied later."""
        target = filename.strip()
        if not target:
            return []
        code, data, text = self._post(
            "search/v1/search/",
            json_body={"doc_types": ["assets"], "query": target},
        )
        if code != 200 or not isinstance(data, dict):
            raise RuntimeError(f"Iconik search failed HTTP {code}: {text}")
        objects = data.get("objects") or []
        if not isinstance(objects, list):
            return []
        seen: set[str] = set()
        hits: list[dict[str, Any]] = []
        for obj in objects:
            if not isinstance(obj, dict):
                continue
            asset_id = str(obj.get("id") or obj.get("asset_id") or "")
            if not asset_id or asset_id in seen:
                continue
            seen.add(asset_id)
            hits.append(obj)
        return hits

    def search_exact_title(self, filename: str) -> list[dict[str, Any]]:
        """Backward-compatible alias for filename candidate search."""
        return self.search_by_filename(filename)

    def snapshot_by_asset_id(self, asset_id: str) -> IconikAssetReference | None:
        """Fetch a preservation snapshot for a known asset ID. Never searches by filename."""
        aid = asset_id.strip()
        if not aid:
            return None
        try:
            asset = self.get_asset(aid)
        except Exception as exc:
            logger.warning("snapshot_by_asset_id failed for %s: %s", aid, exc)
            return None
        details = self.resolve_file_details(aid)
        iconik_name = str(asset.get("title") or asset.get("name") or "")
        metadata = self.fetch_metadata(aid)
        return IconikAssetReference(
            asset_id=aid,
            file_set_id=details["file_set_id"],
            file_id=details["file_id"],
            format_id=details["format_id"],
            storage_id=details["storage_id"],
            filename=iconik_name,
            original_filename=details["original_filename"] or iconik_name,
            file_size=details["file_size"],
            metadata_field_count=metadata.field_count,
            metadata_status=metadata.status,
            iconik_base_dir=details["iconik_base_dir"],
            iconik_file_name=details["iconik_file_name"],
            iconik_s3_key=details["iconik_s3_key"],
            storage_path=details["storage_path"],
        )

    def resolve_file_details(self, asset_id: str) -> dict[str, Any]:
        return self._resolve_file_details(asset_id)

    def metadata_field_count(self, asset_id: str) -> int:
        return self.fetch_metadata(asset_id).field_count

    def fetch_metadata(self, asset_id: str) -> MetadataLookupResult:
        return self._fetch_metadata(asset_id)

    @staticmethod
    def _metadata_missing_response(
        http_status: int,
        data: Any,
        text: str,
    ) -> bool:
        if http_status == 404:
            return True
        errors = data.get("errors") if isinstance(data, dict) else None
        if isinstance(errors, list):
            for err in errors:
                if isinstance(err, str) and "doesn't exist" in err:
                    return True
        return "doesn't exist" in (text or "")

    @staticmethod
    def _count_metadata_fields(data: dict[str, Any]) -> int:
        meta_values = data.get("metadata_values")
        if isinstance(meta_values, dict):
            return sum(1 for k in meta_values if not str(k).startswith("__"))
        meta = data.get("metadata")
        if isinstance(meta, dict):
            return sum(1 for k in meta if not str(k).startswith("__"))
        return sum(
            1
            for k in data
            if not str(k).startswith("__")
            and k not in ("metadata_values", "metadata", "view_fields", "errors")
        )

    def _fetch_metadata(self, asset_id: str) -> MetadataLookupResult:
        aid = asset_id.strip()
        if not aid:
            return MetadataLookupResult(
                METADATA_STATUS_ERROR,
                0,
                "asset_id is empty",
            )
        try:
            resp = self._session.get(
                self._url(f"metadata/v1/assets/{aid}/"),
                timeout=self._timeout,
            )
            text = resp.text[:500] if resp.text else ""
            try:
                data = resp.json() if resp.content else None
            except ValueError:
                data = None

            if self._metadata_missing_response(resp.status_code, data, text):
                logger.warning(
                    "Metadata view missing for asset %s (HTTP %s)",
                    aid,
                    resp.status_code,
                )
                return MetadataLookupResult(
                    METADATA_STATUS_MISSING,
                    0,
                    text or f"HTTP {resp.status_code}",
                )

            if resp.status_code != 200 or not isinstance(data, dict):
                logger.warning(
                    "Metadata lookup failed for asset %s: HTTP %s %s",
                    aid,
                    resp.status_code,
                    text,
                )
                return MetadataLookupResult(
                    METADATA_STATUS_ERROR,
                    0,
                    text or f"HTTP {resp.status_code}",
                )

            return MetadataLookupResult(
                METADATA_STATUS_AVAILABLE,
                self._count_metadata_fields(data),
                "",
            )
        except requests.RequestException as exc:
            logger.warning("Metadata lookup error for asset %s: %s", aid, exc)
            return MetadataLookupResult(METADATA_STATUS_ERROR, 0, str(exc))

    @staticmethod
    def _iconik_s3_key(base_dir: str, name: str) -> str:
        bd = base_dir.strip().strip("/")
        nm = name.strip().lstrip("/")
        if bd and nm:
            return f"{bd}/{nm}"
        if nm:
            return nm
        return bd

    @staticmethod
    def _extract_storage_path(record: dict) -> str:
        for key in ("storage_path", "path", "uri", "url"):
            value = record.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""

    def _resolve_file_details(self, asset_id: str) -> dict[str, Any]:
        file_set_id = file_id = format_id = ""
        storage_id = self._storage_id
        file_size = 0
        original_filename = ""
        iconik_base_dir = iconik_file_name = iconik_s3_key = storage_path = ""
        data = self._get(f"files/v1/assets/{asset_id}/file_sets/")
        items: list = []
        if isinstance(data, dict):
            items = data.get("objects") or data.get("results") or []
        elif isinstance(data, list):
            items = data
        if not items:
            return {
                "file_set_id": file_set_id,
                "file_id": file_id,
                "format_id": format_id,
                "storage_id": storage_id,
                "file_size": file_size,
                "original_filename": original_filename,
                "iconik_base_dir": iconik_base_dir,
                "iconik_file_name": iconik_file_name,
                "iconik_s3_key": iconik_s3_key,
                "storage_path": storage_path,
            }
        chosen = items[0]
        for item in items:
            if str(item.get("type", "")).upper() == "ORIGINAL":
                chosen = item
                break
        file_set_id = str(chosen.get("id") or "")
        format_id = str(chosen.get("format_id") or "")
        storage_id = str(chosen.get("storage_id") or storage_id)
        file_size = int(chosen.get("size") or chosen.get("file_size") or 0)
        original_filename = str(chosen.get("name") or chosen.get("original_name") or "")
        iconik_base_dir = str(chosen.get("base_dir") or "")
        iconik_file_name = original_filename
        storage_path = self._extract_storage_path(chosen)
        iconik_s3_key = self._iconik_s3_key(iconik_base_dir, iconik_file_name)
        if file_set_id:
            files_data = self._get(f"files/v1/file_sets/{file_set_id}/files/")
            file_objs: list = []
            if isinstance(files_data, dict):
                file_objs = files_data.get("objects") or files_data.get("results") or []
            elif isinstance(files_data, list):
                file_objs = files_data
            if file_objs:
                chosen_file = file_objs[0]
                for fobj in file_objs:
                    if str(fobj.get("type", "")).upper() == "FILE":
                        chosen_file = fobj
                        break
                file_id = str(chosen_file.get("id") or "")
                if not format_id:
                    format_id = str(chosen_file.get("format_id") or "")
                if file_size == 0:
                    file_size = int(chosen_file.get("size") or chosen_file.get("file_size") or 0)
                storage_id = str(chosen_file.get("storage_id") or storage_id)
                original_filename = str(
                    chosen_file.get("original_name")
                    or chosen_file.get("name")
                    or original_filename
                )
                file_storage_path = self._extract_storage_path(chosen_file)
                if file_storage_path:
                    storage_path = file_storage_path
        if not iconik_s3_key and (iconik_base_dir or iconik_file_name):
            iconik_s3_key = self._iconik_s3_key(iconik_base_dir, iconik_file_name)
        return {
            "file_set_id": file_set_id,
            "file_id": file_id,
            "format_id": format_id,
            "storage_id": storage_id,
            "file_size": file_size,
            "original_filename": original_filename,
            "iconik_base_dir": iconik_base_dir,
            "iconik_file_name": iconik_file_name,
            "iconik_s3_key": iconik_s3_key,
            "storage_path": storage_path,
        }

    def attempt_direct_replacement(
        self,
        local_path: str | Path,
        ref: IconikAssetReference,
    ) -> DirectReplacementResult:
        """Try byte-level Iconik replacement. Metadata-only PATCH is never success."""
        path = Path(local_path)
        if not path.is_file():
            return DirectReplacementResult(False, REPLACEMENT_SCAN_FALLBACK, "local file missing")
        file_size = path.stat().st_size
        original_name = ref.original_filename or ref.filename

        post_ok, post_msg = self._post_file_and_upload(path, ref, file_size, original_name)
        if post_ok:
            return DirectReplacementResult(True, REPLACEMENT_DIRECT_FILESET, post_msg)

        if ref.file_id:
            self._patch(
                f"files/v1/assets/{ref.asset_id}/files/{ref.file_id}/",
                json_body={
                    "size": file_size,
                    "status": "CLOSED",
                    "original_name": original_name,
                    "progress_processed": 100,
                },
            )
            self._put(
                f"files/v1/assets/{ref.asset_id}/files/{ref.file_id}/",
                json_body={
                    "original_name": original_name,
                    "size": file_size,
                    "type": "FILE",
                    "status": "CLOSED",
                    "format_id": ref.format_id,
                    "file_set_id": ref.file_set_id,
                    "storage_id": ref.storage_id,
                    "progress_processed": 100,
                },
            )

        if ref.file_set_id:
            self._patch(
                f"files/v1/assets/{ref.asset_id}/file_sets/{ref.file_set_id}/",
                json_body={
                    "name": original_name,
                    "storage_id": ref.storage_id,
                    "format_id": ref.format_id or None,
                },
            )

        return DirectReplacementResult(
            False,
            REPLACEMENT_SCAN_FALLBACK,
            "no byte-level replacement; metadata sync only — scan required",
        )

    def _post_file_and_upload(
        self,
        path: Path,
        ref: IconikAssetReference,
        file_size: int,
        original_name: str,
    ) -> tuple[bool, str]:
        if not ref.file_set_id or not ref.format_id:
            return False, "missing file_set_id or format_id"
        now = datetime.now(timezone.utc).isoformat()
        payload = {
            "original_name": original_name,
            "directory_path": "",
            "size": file_size,
            "type": "FILE",
            "metadata": {},
            "format_id": ref.format_id,
            "file_set_id": ref.file_set_id,
            "storage_id": ref.storage_id,
            "file_date_created": now,
            "file_date_modified": now,
        }
        code, data, text = self._post(f"files/v1/assets/{ref.asset_id}/files/", json_body=payload)
        if code not in (200, 201) or not isinstance(data, dict):
            return False, f"POST files HTTP {code}: {text}"
        upload_url = data.get("upload_url")
        file_id = str(data.get("id") or "")
        if not upload_url:
            return False, "POST files returned no upload_url"
        if not self._upload_to_presigned_url(str(upload_url), path, file_size):
            return False, "presigned upload failed"
        if file_id:
            self._patch(
                f"files/v1/assets/{ref.asset_id}/files/{file_id}/",
                json_body={"status": "CLOSED", "progress_processed": 100, "size": file_size},
            )
        return True, "file posted and uploaded via Iconik upload_url"

    def _upload_to_presigned_url(self, upload_url: str, path: Path, file_size: int) -> bool:
        try:
            with path.open("rb") as handle:
                resp = requests.put(
                    upload_url,
                    data=handle,
                    headers={"Content-Length": str(file_size)},
                    timeout=max(self._timeout, 300),
                )
                if resp.status_code in (200, 201, 204):
                    return True
                handle.seek(0)
                resp = requests.post(upload_url, data=handle, timeout=max(self._timeout, 300))
                return resp.status_code in (200, 201, 204)
        except requests.RequestException as exc:
            logger.warning("Presigned upload failed: %s", exc)
            return False

    def trigger_storage_scan(self) -> str:
        code, _, _ = self._post(f"files/v1/storages/{self._storage_id}/scan/")
        if code in (200, 202):
            return "started"
        if code in (400, 409):
            return "already_running"
        return "failed"

    def wait_for_scan(self, *, timeout: int = 180, interval: int = 5) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            data = self._get("files/v1/storages/")
            objects = data.get("objects") or [] if isinstance(data, dict) else []
            for storage in objects:
                if str(storage.get("id")) == self._storage_id:
                    if storage.get("scanner_status") != "ACTIVE":
                        return True
            time.sleep(interval)
        return False

    @staticmethod
    def _metadata_compareable(
        before: IconikAssetReference,
        after: IconikAssetReference,
    ) -> bool:
        return (
            before.metadata_status == METADATA_STATUS_AVAILABLE
            and after.metadata_status == METADATA_STATUS_AVAILABLE
        )

    @staticmethod
    def _metadata_preserved(
        before: IconikAssetReference,
        after: IconikAssetReference,
    ) -> bool:
        if not IconikVerificationService._metadata_compareable(before, after):
            return True
        return after.metadata_field_count >= before.metadata_field_count

    def verify_preservation(
        self,
        before: IconikAssetReference,
        after: IconikAssetReference | None,
        *,
        require_file_id: bool = False,
    ) -> IconikVerificationResult:
        if after is None:
            return IconikVerificationResult(
                asset_preserved=False,
                file_set_preserved=False,
                metadata_preserved=False,
                status=VERIFY_FAIL,
                message="Post-replacement Iconik asset not found",
            )
        if before.asset_id != after.asset_id:
            return IconikVerificationResult(
                asset_preserved=False,
                file_set_preserved=before.file_set_id == after.file_set_id,
                metadata_preserved=self._metadata_preserved(before, after),
                status=VERIFY_FAIL,
                message="Asset ID changed after replacement",
            )

        file_set_ok = before.file_set_id == after.file_set_id
        file_id_ok = (
            not require_file_id
            or not before.file_id
            or before.file_id == after.file_id
        )
        metadata_ok = self._metadata_preserved(before, after)

        if not file_set_ok:
            return IconikVerificationResult(
                asset_preserved=True,
                file_set_preserved=False,
                metadata_preserved=metadata_ok,
                status=VERIFY_WARNING,
                message="File set ID changed after replacement",
            )
        if not file_id_ok:
            return IconikVerificationResult(
                asset_preserved=True,
                file_set_preserved=True,
                metadata_preserved=metadata_ok,
                status=VERIFY_WARNING,
                message="File ID changed after replacement",
            )
        if self._metadata_compareable(before, after) and not metadata_ok:
            return IconikVerificationResult(
                asset_preserved=True,
                file_set_preserved=True,
                metadata_preserved=False,
                status=VERIFY_WARNING,
                message="Metadata field count decreased after replacement",
            )

        message = "Asset and file set preserved"
        if (
            before.metadata_status == METADATA_STATUS_MISSING
            or after.metadata_status == METADATA_STATUS_MISSING
        ):
            message += "; metadata view unavailable — IDs used for verification"
        elif (
            before.metadata_status == METADATA_STATUS_ERROR
            or after.metadata_status == METADATA_STATUS_ERROR
        ):
            message += "; metadata lookup error — IDs used for verification"

        return IconikVerificationResult(
            asset_preserved=True,
            file_set_preserved=True,
            metadata_preserved=metadata_ok,
            status=VERIFY_PASS,
            message=message,
        )

    def asset_id_changed(
        self,
        before: IconikAssetReference,
        after: IconikAssetReference | None,
    ) -> bool:
        if not before.asset_id:
            return False
        if after is None:
            return True
        return before.asset_id != after.asset_id

    def log_existing_asset(self, ref: IconikAssetReference, emit: Any) -> None:
        emit("[ICONIK] Existing asset found")
        emit(f"Asset ID: {ref.asset_id}")
        emit(f"File Set ID: {ref.file_set_id}")
        emit(f"File ID: {ref.file_id}")
        emit(f"Format ID: {ref.format_id}")
        emit(f"Storage ID: {ref.storage_id}")
        if ref.iconik_s3_key:
            emit(f"Iconik S3 key: {ref.iconik_s3_key}")
        if ref.storage_path:
            emit(f"Iconik storage path: {ref.storage_path}")
        self.log_metadata_status(ref, emit)

    def log_metadata_status(self, ref: IconikAssetReference, emit: Any) -> None:
        if ref.metadata_status == METADATA_STATUS_MISSING:
            emit("[WARN] Metadata view missing for asset")
            emit(f"Asset ID: {ref.asset_id}")
            emit("Replacement proceeding using asset/file-set records only.")
        elif ref.metadata_status == METADATA_STATUS_ERROR:
            emit("[WARN] Metadata lookup failed for asset")
            emit(f"Asset ID: {ref.asset_id}")
            emit("Replacement proceeding using asset/file-set records only.")
