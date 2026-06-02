"""Thumbnail loading: Iconik URL (authenticated) first, ffmpeg fallback."""

from __future__ import annotations

import logging
import subprocess
import tempfile
from io import BytesIO
from pathlib import Path
from typing import Callable

import requests
from PIL import Image

from gamechanger_rename_manager.config.settings import AppSettings
from gamechanger_rename_manager.services.asset_model import AssetRecord
from gamechanger_rename_manager.services.iconik_client import IconikClient, _normalize_media_url

logger = logging.getLogger(__name__)

LogFn = Callable[[str], None] | None


class ThumbnailService:
    def __init__(
        self,
        settings: AppSettings,
        *,
        iconik: IconikClient | None = None,
        auth_headers: dict[str, str] | None = None,
    ) -> None:
        self._settings = settings
        self._cache = settings.effective_thumbnail_cache()
        self._iconik = iconik
        self._auth_headers = auth_headers or (
            iconik.get_auth_headers() if iconik else _default_auth_headers(settings)
        )
        self._session = requests.Session()
        if self._auth_headers:
            self._session.headers.update(self._auth_headers)

    def cache_path(self, asset_id: str) -> Path:
        return self._cache / f"{asset_id}.jpg"

    def load_for_asset(
        self,
        asset: AssetRecord,
        *,
        max_size: tuple[int, int] = (960, 540),
        log: LogFn = None,
    ) -> tuple[Image.Image, str]:
        """Return (PIL image, source description)."""
        cached = self.cache_path(asset.asset_id)

        def emit(msg: str) -> None:
            logger.info(msg)
            if log:
                log(msg)

        emit(f"Thumbnail load start asset={asset.asset_id} max_size={max_size}")

        if cached.is_file():
            try:
                img = Image.open(cached).convert("RGB")
                img = _fit_aspect(img, max_size)
                emit(f"Thumbnail cache hit: {cached}")
                return img, "cache"
            except OSError as exc:
                emit(f"Thumbnail cache read error: {exc}")

        candidates = self._collect_urls(asset)
        emit(f"Thumbnail URL candidates ({len(candidates)}): {candidates[:3]}")

        for url in candidates:
            data, status = self._fetch_image_bytes(url, log=emit)
            if data:
                try:
                    img = Image.open(BytesIO(data)).convert("RGB")
                    img = _fit_aspect(img, max_size)
                    img.save(cached, "JPEG", quality=88)
                    emit(f"Thumbnail saved cache={cached} from url status={status}")
                    return img, f"iconik:{status}"
                except OSError as exc:
                    emit(f"Thumbnail PIL decode error url={url[:80]}: {exc}")

        emit("Iconik thumbnail fetch failed — trying ffmpeg fallback")
        ffmpeg_path = self._ffmpeg_from_storage(asset, cached, log=emit)
        if ffmpeg_path and ffmpeg_path.is_file():
            try:
                img = Image.open(ffmpeg_path).convert("RGB")
                img = _fit_aspect(img, max_size)
                emit(f"Thumbnail ffmpeg OK: {ffmpeg_path}")
                return img, "ffmpeg"
            except OSError as exc:
                emit(f"Thumbnail ffmpeg PIL error: {exc}")

        emit("Thumbnail using placeholder")
        return _placeholder(max_size), "placeholder"

    def _collect_urls(self, asset: AssetRecord) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        base = self._settings.iconik_base_url.rstrip("/") + "/"

        def add(u: str) -> None:
            nu = _normalize_media_url(u, base)
            if nu and nu not in seen:
                seen.add(nu)
                out.append(nu)

        if asset.thumbnail_url:
            add(asset.thumbnail_url)
        if self._iconik:
            for u in self._iconik.get_asset_keyframe_urls(asset.asset_id):
                add(u)
        return out

    def _fetch_image_bytes(self, url: str, *, log: Callable[[str], None]) -> tuple[bytes | None, int]:
        log(f"Thumbnail GET {url[:160]}")
        try:
            r = self._session.get(url, timeout=45, allow_redirects=True)
            log(f"Thumbnail HTTP status={r.status_code} len={len(r.content)} url={url[:100]}")
            if r.status_code == 200 and r.content:
                return r.content, r.status_code
            if r.status_code in (401, 403):
                log("Thumbnail auth rejected — check App-ID / Auth-Token headers")
        except requests.RequestException as exc:
            log(f"Thumbnail request error: {exc}")
        return None, 0

    def _ffmpeg_from_storage(
        self,
        asset: AssetRecord,
        out_path: Path,
        *,
        log: Callable[[str], None],
    ) -> Path | None:
        local = _local_path_from_storage(asset.storage_path)
        if local and Path(local).is_file():
            log(f"ffmpeg local file: {local}")
            return self._ffmpeg_thumbnail(local, out_path, log=log)

        if asset.s3_key and self._settings.s3_bucket:
            temp = self._download_s3_sample(asset, log=log)
            if temp:
                return self._ffmpeg_thumbnail(str(temp), out_path, log=log)
        return None

    def _download_s3_sample(self, asset: AssetRecord, *, log: Callable[[str], None]) -> Path | None:
        try:
            import boto3

            bucket = asset.file_sets[0].bucket if asset.file_sets and asset.file_sets[0].bucket else self._settings.s3_bucket
            key = asset.s3_key
            if not bucket or not key:
                return None
            log(f"S3 temp download for thumbnail s3://{bucket}/{key}")
            client = boto3.client(
                "s3",
                region_name=self._settings.aws_region,
                aws_access_key_id=self._settings.aws_access_key_id or None,
                aws_secret_access_key=self._settings.aws_secret_access_key or None,
                aws_session_token=self._settings.aws_session_token or None,
            )
            tmp = Path(tempfile.gettempdir()) / f"grm_thumb_{asset.asset_id}.mp4"
            with open(tmp, "wb") as f:
                client.download_fileobj(bucket, key, f)
            log(f"S3 download OK bytes={tmp.stat().st_size}")
            return tmp
        except Exception as exc:
            log(f"S3 thumbnail download failed: {exc}")
            return None

    def _ffmpeg_thumbnail(
        self,
        media_path: str,
        out_path: Path,
        *,
        log: Callable[[str], None],
    ) -> Path | None:
        ffmpeg = self._settings.ffmpeg_path or "ffmpeg"
        try:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            cmd = [
                ffmpeg,
                "-y",
                "-ss",
                "00:00:01",
                "-i",
                media_path,
                "-frames:v",
                "1",
                "-q:v",
                "3",
                str(out_path),
            ]
            log(f"ffmpeg cmd: {' '.join(cmd[:8])}…")
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=90, check=False)
            if proc.returncode != 0:
                log(f"ffmpeg stderr: {(proc.stderr or '')[:300]}")
            if out_path.is_file():
                return out_path
        except (OSError, subprocess.TimeoutExpired) as exc:
            log(f"ffmpeg exception: {exc}")
        return None


def _default_auth_headers(settings: AppSettings) -> dict[str, str]:
    return {
        "App-ID": settings.iconik_app_id.strip(),
        "Auth-Token": settings.iconik_auth_token.strip(),
    }


def _local_path_from_storage(storage: str) -> str:
    s = storage.strip()
    if s.startswith("file://"):
        return s[7:]
    if s.startswith("/") and not s.startswith("//"):
        return s
    return ""


def _fit_aspect(img: Image.Image, max_size: tuple[int, int]) -> Image.Image:
    img = img.copy()
    img.thumbnail(max_size, Image.Resampling.LANCZOS)
    return img


def _placeholder(size: tuple[int, int]) -> Image.Image:
    return Image.new("RGB", size, color=(22, 27, 34))
