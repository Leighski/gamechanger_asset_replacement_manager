"""Iconik REST client for search, metadata, and file_set PATCH."""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urljoin

import requests

from gamechanger_rename_manager.config.settings import AppSettings
from gamechanger_rename_manager.services.asset_model import AssetRecord, FileSetRecord, VariantType
from gamechanger_rename_manager.services.asset_status import is_deleted_iconik_doc
from gamechanger_rename_manager.services.s3_service import s3_key_from_file_set
from gamechanger_rename_manager.services.variant import detect_variant

logger = logging.getLogger(__name__)

PER_PAGE = 100
MAX_SEARCH_PAGES = 20
TIMEOUT_SEC = 120


class IconikClient:
    def __init__(self, settings: AppSettings) -> None:
        self._settings = settings
        self._base = settings.iconik_base_url.rstrip("/") + "/"
        self._session = requests.Session()
        self._session.headers.update(
            {
                "App-ID": settings.iconik_app_id.strip(),
                "Auth-Token": settings.iconik_auth_token.strip(),
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
        )

    def get_auth_headers(self) -> dict[str, str]:
        return {
            "App-ID": self._settings.iconik_app_id.strip(),
            "Auth-Token": self._settings.iconik_auth_token.strip(),
        }

    def _url(self, path: str) -> str:
        return urljoin(self._base, path.lstrip("/"))

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        json_body: dict | list | None = None,
    ) -> tuple[int, Any, str]:
        url = self._url(path)
        if params:
            from urllib.parse import urlencode

            url = f"{url}?{urlencode(params)}"
        try:
            resp = self._session.request(
                method,
                url,
                json=json_body,
                timeout=TIMEOUT_SEC,
            )
            text = resp.text[:2000] if resp.text else ""
            try:
                data = resp.json() if resp.content else None
            except ValueError:
                data = None
            return resp.status_code, data, text
        except requests.RequestException as exc:
            logger.exception("Iconik request failed: %s %s", method, path)
            return 0, None, str(exc)

    def search(self, query: str, *, log: logging.Logger | None = None) -> tuple[list[dict], str | None]:
        if not query.strip():
            return [], "Empty search query"
        seen: set[str] = set()
        results: list[dict] = []
        coll = self._settings.iconik_collection_uuid.strip()
        for page in range(1, MAX_SEARCH_PAGES + 1):
            params = {"page": str(page), "per_page": str(PER_PAGE)}
            if coll:
                params["collection_id"] = coll
            code, data, snippet = self._request(
                "POST",
                "search/v1/search/",
                params=params,
                json_body={"doc_types": ["assets"], "query": query.strip()},
            )
            if log:
                total = data.get("total") if isinstance(data, dict) else "?"
                log.info(
                    "Search page=%s HTTP=%s objects=%s total=%s query=%r",
                    page,
                    code,
                    len(data.get("objects") or []) if isinstance(data, dict) else 0,
                    total,
                    query.strip(),
                )
            if code != 200 or not isinstance(data, dict):
                return results, f"Search HTTP {code}: {snippet}"
            objs = data.get("objects") or []
            if not isinstance(objs, list):
                break
            for obj in objs:
                if not isinstance(obj, dict):
                    continue
                aid = str(obj.get("id") or obj.get("asset_id") or "")
                if aid and aid not in seen:
                    seen.add(aid)
                    results.append(obj)
                    if log:
                        log.debug(
                            "Search hit id=%s title=%r keys=%s",
                            aid,
                            obj.get("title"),
                            sorted(obj.keys())[:15],
                        )
            if len(objs) < PER_PAGE:
                break
        if log:
            log.info("Search complete: %s unique asset(s)", len(results))
        return results, None

    def get_collection(self, collection_id: str) -> tuple[dict | None, str | None]:
        code, data, snippet = self._request("GET", f"assets/v1/collections/{collection_id}/")
        if code == 200 and isinstance(data, dict):
            return data, None
        return None, f"GET collection HTTP {code}: {snippet}"

    def get_asset_keyframe_urls(self, asset_id: str) -> list[str]:
        """Keyframe / proxy URLs from files API (often requires auth on download)."""
        urls: list[str] = []
        for path in (
            f"files/v1/assets/{asset_id}/keyframes/",
            f"files/v1/assets/{asset_id}/proxies/",
        ):
            code, data, _ = self._request("GET", path)
            if code != 200:
                logger.debug("Keyframe/proxy GET %s HTTP %s", path, code)
                continue
            items: list = []
            if isinstance(data, dict):
                items = data.get("objects") or data.get("results") or []
            elif isinstance(data, list):
                items = data
            for it in items:
                if not isinstance(it, dict):
                    continue
                for key in (
                    "url",
                    "download_url",
                    "preview_url",
                    "thumbnail_url",
                    "proxy_url",
                    "uri",
                ):
                    v = it.get(key)
                    if isinstance(v, str) and (v.startswith("http") or v.startswith("/")):
                        urls.append(v)
        return urls

    def get_asset(self, asset_id: str) -> tuple[dict | None, str | None]:
        code, data, snippet = self._request("GET", f"assets/v1/assets/{asset_id}/")
        if code == 200 and isinstance(data, dict):
            return data, None
        return None, f"GET asset HTTP {code}: {snippet}"

    def list_file_sets(self, asset_id: str) -> tuple[list[FileSetRecord], str | None]:
        code, data, snippet = self._request(
            "GET",
            f"files/v1/assets/{asset_id}/file_sets/",
        )
        if code != 200:
            return [], f"file_sets HTTP {code}: {snippet}"
        records: list[FileSetRecord] = []
        items: list = []
        if isinstance(data, dict):
            items = data.get("objects") or data.get("results") or []
        elif isinstance(data, list):
            items = data
        for it in items:
            if not isinstance(it, dict):
                continue
            fid = str(it.get("id") or "")
            name = str(it.get("name") or it.get("original_name") or "").strip()
            base_dir = str(it.get("base_dir") or "").strip()
            storage = _extract_storage_path(it)
            bucket, key_from_storage = _split_s3(storage)
            key = s3_key_from_file_set(base_dir, name) if (base_dir or name) else key_from_storage
            records.append(
                FileSetRecord(
                    fileset_id=fid,
                    name=name,
                    base_dir=base_dir,
                    storage_path=storage,
                    bucket=bucket,
                    s3_key=key,
                    format_id=str(it.get("format_id") or ""),
                    raw=it,
                )
            )
        return records, None

    def patch_file_set(self, asset_id: str, fileset_id: str, payload: dict) -> tuple[bool, str]:
        path = f"files/v1/assets/{asset_id}/file_sets/{fileset_id}/"
        code, data, snippet = self._request("PATCH", path, json_body=payload)
        if code in (200, 201, 204):
            return True, "OK"
        return False, f"PATCH file_set HTTP {code}: {snippet}"

    def update_asset_title(self, asset_id: str, title: str) -> tuple[bool, str]:
        code, data, snippet = self._request(
            "PATCH",
            f"assets/v1/assets/{asset_id}/",
            json_body={"title": title},
        )
        if code in (200, 201, 204):
            return True, "OK"
        return False, f"PATCH asset title HTTP {code}: {snippet}"

    def hit_to_asset_record(
        self,
        hit: dict,
        file_sets: list[FileSetRecord] | None = None,
        *,
        collection_ids: list[str] | None = None,
        collection_breadcrumb: str = "",
        collection_paths: list[str] | None = None,
    ) -> AssetRecord:
        asset_id = str(hit.get("id") or hit.get("asset_id") or "")
        title = str(hit.get("title") or hit.get("name") or "").strip()
        thumb = _extract_thumbnail_url(hit)
        duration = _extract_duration(hit)
        fs_list = file_sets or []
        primary = fs_list[0] if fs_list else None
        fname = primary.name if primary else title
        variant = detect_variant(fname or title)
        storage = primary.storage_path if primary else ""
        if primary:
            s3_key = s3_key_from_file_set(primary.base_dir, primary.name)
        else:
            s3_key = ""
        return AssetRecord(
            asset_id=asset_id,
            title=title,
            file_set_name=fname,
            fileset_id=primary.fileset_id if primary else "",
            duration_sec=duration,
            variant=variant,
            storage_path=storage,
            s3_key=s3_key,
            thumbnail_url=thumb,
            search_hit=hit,
            file_sets=fs_list,
            collection_ids=collection_ids or [],
            collection_breadcrumb=collection_breadcrumb,
            collection_paths=collection_paths or [],
            is_deleted=is_deleted_iconik_doc(hit),
        )


def enrich_assets(
    client: IconikClient,
    hits: list[dict],
    *,
    log: logging.Logger | None = None,
) -> tuple[list[AssetRecord], int]:
    from gamechanger_rename_manager.services.collection_resolver import (
        CollectionResolver,
        extract_collection_ids,
    )

    resolver = CollectionResolver(client)
    out: list[AssetRecord] = []
    skipped_deleted = 0
    for hit in hits:
        aid = str(hit.get("id") or hit.get("asset_id") or "")
        if not aid:
            continue
        if is_deleted_iconik_doc(hit):
            skipped_deleted += 1
            if log:
                log.info("Excluding soft-deleted asset from search results: %s", aid)
            continue
        fs, err = client.list_file_sets(aid)
        if err:
            logger.warning("file_sets for %s: %s", aid, err)
            if log:
                log.warning("file_sets for %s: %s", aid, err)

        coll_ids = extract_collection_ids(hit)
        coll_paths: list[str] = []
        primary_crumb = ""
        if coll_ids:
            for cid in coll_ids:
                path = resolver.breadcrumb(cid, log=log)
                if path:
                    coll_paths.append(path)
            primary_crumb = coll_paths[0] if coll_paths else ""
        else:
            asset_doc, aerr = client.get_asset(aid)
            if asset_doc:
                if is_deleted_iconik_doc(asset_doc):
                    skipped_deleted += 1
                    if log:
                        log.info("Excluding soft-deleted asset (asset GET): %s", aid)
                    continue
                coll_ids = extract_collection_ids(asset_doc)
                for cid in coll_ids:
                    path = resolver.breadcrumb(cid, log=log)
                    if path:
                        coll_paths.append(path)
                primary_crumb = coll_paths[0] if coll_paths else ""
            elif aerr and log:
                log.debug("Asset doc for collections %s: %s", aid, aerr)

        rec = client.hit_to_asset_record(
            hit,
            fs,
            collection_ids=coll_ids,
            collection_breadcrumb=primary_crumb,
            collection_paths=coll_paths,
        )
        if not rec.thumbnail_url:
            extra = client.get_asset_keyframe_urls(aid)
            if extra:
                rec.thumbnail_url = _normalize_media_url(extra[0], client._base)
                if log:
                    log.info("Keyframe URL for %s: %s", aid, rec.thumbnail_url[:120])
        if log:
            log.debug(
                "Enriched %s variant=%s thumb=%s collection=%r",
                aid,
                rec.variant.value,
                bool(rec.thumbnail_url),
                primary_crumb,
            )
        out.append(rec)
    if skipped_deleted and log:
        log.info(
            "Soft-delete filter: excluded %s asset(s) from operational search results",
            skipped_deleted,
        )
    return out, skipped_deleted


def _normalize_media_url(url: str, api_base: str) -> str:
    u = url.strip()
    if u.startswith("http"):
        return u
    if u.startswith("/"):
        return api_base.rstrip("/") + u
    return u


def _extract_thumbnail_url(hit: dict) -> str:
    urls: list[str] = []

    def collect(obj: dict, depth: int = 0) -> None:
        if depth > 4:
            return
        for key in (
            "thumbnail_url",
            "proxy_url",
            "preview_url",
            "thumb_url",
            "poster_url",
            "url",
            "download_url",
        ):
            v = obj.get(key)
            if isinstance(v, str) and (v.startswith("http") or v.startswith("/")):
                urls.append(v)
        for key in ("versions", "proxies", "keyframes", "files", "formats"):
            nested = obj.get(key)
            if isinstance(nested, list):
                for item in nested:
                    if isinstance(item, dict):
                        collect(item, depth + 1)
            elif isinstance(nested, dict):
                collect(nested, depth + 1)

    collect(hit)
    return urls[0] if urls else ""


def _extract_duration(hit: dict) -> float | None:
    for key in ("duration", "media_duration", "timecode_duration"):
        v = hit.get(key)
        if isinstance(v, (int, float)):
            return float(v)
        if isinstance(v, str) and v.replace(".", "", 1).isdigit():
            return float(v)
    return None


def _extract_storage_path(file_set: dict) -> str:
    for key in ("storage_path", "path", "uri", "url"):
        v = file_set.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()
    files = file_set.get("files")
    if isinstance(files, list) and files:
        f0 = files[0]
        if isinstance(f0, dict):
            for key in ("storage_path", "path", "uri", "url", "name"):
                v = f0.get(key)
                if isinstance(v, str) and v.strip():
                    return v.strip()
    return ""


def _split_s3(storage: str) -> tuple[str, str]:
    s = storage.strip()
    if s.startswith("s3://"):
        rest = s[5:]
        if "/" in rest:
            bucket, key = rest.split("/", 1)
            return bucket, key
        return rest, ""
    return "", s
