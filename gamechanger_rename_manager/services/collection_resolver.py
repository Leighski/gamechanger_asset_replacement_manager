"""Resolve Iconik collection hierarchy into human-readable breadcrumbs."""

from __future__ import annotations

import logging
from typing import Any

from gamechanger_rename_manager.services.iconik_client import IconikClient

logger = logging.getLogger(__name__)

LogFn = logging.Logger | Any  # callable or logger


def extract_collection_ids(hit: dict) -> list[str]:
    """Collect collection UUIDs from a search hit or asset document."""
    ids: list[str] = []
    seen: set[str] = set()

    def add(cid: str) -> None:
        c = cid.strip()
        if c and c not in seen:
            seen.add(c)
            ids.append(c)

    for key in ("collection_id", "parent_collection_id"):
        v = hit.get(key)
        if isinstance(v, str):
            add(v)

    for key in ("collection_ids", "collections_ids"):
        v = hit.get(key)
        if isinstance(v, list):
            for item in v:
                if isinstance(item, str):
                    add(item)
                elif isinstance(item, dict):
                    add(str(item.get("id") or item.get("collection_id") or ""))

    collections = hit.get("collections")
    if isinstance(collections, list):
        for item in collections:
            if isinstance(item, str):
                add(item)
            elif isinstance(item, dict):
                add(str(item.get("id") or item.get("collection_id") or ""))

    in_collections = hit.get("in_collections")
    if isinstance(in_collections, list):
        for item in in_collections:
            if isinstance(item, str):
                add(item)
            elif isinstance(item, dict):
                add(str(item.get("id") or item.get("collection_id") or ""))

    return ids


class CollectionResolver:
    """Cached collection name + parent chain resolution."""

    def __init__(self, client: IconikClient) -> None:
        self._client = client
        self._cache: dict[str, dict] = {}

    def breadcrumb(self, collection_id: str, *, log: LogFn | None = None) -> str:
        if not collection_id:
            return ""
        parts: list[str] = []
        visited: set[str] = set()
        cid: str | None = collection_id
        depth = 0
        while cid and cid not in visited and depth < 32:
            visited.add(cid)
            coll = self._get_collection(cid, log=log)
            if not coll:
                parts.insert(0, cid[:8] + "…")
                break
            name = str(coll.get("title") or coll.get("name") or coll.get("label") or cid).strip()
            parts.insert(0, name)
            parent = coll.get("parent_id") or coll.get("parent_collection_id") or coll.get("parent")
            if isinstance(parent, dict):
                cid = str(parent.get("id") or "") or None
            elif isinstance(parent, str) and parent.strip():
                cid = parent.strip()
            else:
                cid = None
            depth += 1
        return " > ".join(parts) if parts else collection_id

    def resolve_for_hit(self, hit: dict, *, log: LogFn | None = None) -> tuple[list[str], str]:
        ids = extract_collection_ids(hit)
        if not ids:
            logger.debug("No collection IDs on asset hit keys=%s", list(hit.keys())[:20])
            return [], ""
        crumbs: list[str] = []
        for cid in ids:
            path = self.breadcrumb(cid, log=log)
            if path:
                crumbs.append(path)
                if log:
                    _emit(log, f"Collection {cid}: {path}")
        primary = crumbs[0] if crumbs else ""
        return ids, primary

    def _get_collection(self, collection_id: str, *, log: LogFn | None = None) -> dict | None:
        if collection_id in self._cache:
            return self._cache[collection_id]
        doc, err = self._client.get_collection(collection_id)
        if err:
            logger.warning("Collection fetch %s: %s", collection_id, err)
            if log:
                _emit(log, f"Collection fetch failed {collection_id}: {err}")
            return None
        if doc:
            self._cache[collection_id] = doc
            if log:
                _emit(log, f"Collection loaded: {collection_id} -> {doc.get('title') or doc.get('name')}")
        return doc


def _emit(log: LogFn, msg: str) -> None:
    if callable(log):
        log(msg)
    elif hasattr(log, "info"):
        log.info(msg)
