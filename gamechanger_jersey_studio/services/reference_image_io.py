"""Reference image import, metadata extraction, and byte handling."""

from __future__ import annotations

import hashlib
import io
from pathlib import Path

from models.reference_image import SUPPORTED_EXTENSIONS

try:
    from PIL import Image, ImageOps
except ImportError:  # pragma: no cover
    Image = None  # type: ignore[assignment,misc]
    ImageOps = None  # type: ignore[assignment,misc]

LARGE_FILE_BYTES = 20 * 1024 * 1024
SMALL_IMAGE_PX = 400


class ReferenceImageImportError(ValueError):
    """Raised when a file cannot be imported as a reference image."""


def normalise_extension(path: Path) -> str:
    ext = path.suffix.lower()
    if ext == ".jpeg":
        return ".jpg"
    if ext == ".tif":
        return ".tiff"
    return ext


def is_supported_path(path: Path) -> bool:
    return path.suffix.lower() in SUPPORTED_EXTENSIONS or path.suffix.lower() == ".jpeg"


def read_source_bytes(path: Path) -> tuple[bytes, str]:
    """Read and normalise source file bytes. PSD files are flattened to PNG."""
    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise ReferenceImageImportError(f"File not found: {source}")
    if not is_supported_path(source):
        raise ReferenceImageImportError(
            f"Unsupported format: {source.suffix}. Supported: PNG, JPEG, TIFF, WEBP, PSD"
        )

    ext = normalise_extension(source)
    raw = source.read_bytes()

    if ext == ".psd":
        return _flatten_psd(raw), ".png"

    if Image is None:
        return raw, ext

    try:
        with Image.open(io.BytesIO(raw)) as image:
            image = ImageOps.exif_transpose(image)
            if ext in {".jpg", ".jpeg"}:
                buffer = io.BytesIO()
                rgb = image.convert("RGB")
                rgb.save(buffer, format="JPEG", quality=95)
                return buffer.getvalue(), ".jpg"
            if ext == ".png":
                buffer = io.BytesIO()
                image.save(buffer, format="PNG")
                return buffer.getvalue(), ".png"
            if ext == ".webp":
                buffer = io.BytesIO()
                image.save(buffer, format="WEBP", quality=95)
                return buffer.getvalue(), ".webp"
            if ext == ".tiff":
                buffer = io.BytesIO()
                image.save(buffer, format="TIFF")
                return buffer.getvalue(), ".tiff"
    except Exception as exc:
        raise ReferenceImageImportError(f"Corrupt or unreadable image: {source.name}") from exc

    return raw, ext


def _flatten_psd(raw: bytes) -> bytes:
    try:
        from psd_tools import PSDImage
    except ImportError as exc:  # pragma: no cover
        raise ReferenceImageImportError(
            "PSD import requires psd-tools. Install with: pip install psd-tools"
        ) from exc
    try:
        psd = PSDImage.open(io.BytesIO(raw))
        composite = psd.composite()
        buffer = io.BytesIO()
        composite.save(buffer, format="PNG")
        return buffer.getvalue()
    except Exception as exc:
        raise ReferenceImageImportError("Could not flatten PSD preview") from exc


def extract_metadata(data: bytes, *, ext: str) -> dict[str, object]:
    if Image is None:  # pragma: no cover
        return {"width": 0, "height": 0, "colour_profile": "", "orientation": 0}
    try:
        with Image.open(io.BytesIO(data)) as image:
            image = ImageOps.exif_transpose(image)
            profile = ""
            if image.info.get("icc_profile"):
                profile = "ICC"
            elif image.mode in {"RGB", "RGBA"}:
                profile = "sRGB"
            return {
                "width": int(image.width),
                "height": int(image.height),
                "colour_profile": profile,
                "orientation": 0,
            }
    except Exception as exc:
        raise ReferenceImageImportError("Could not read image metadata") from exc


def checksum_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def media_type_for_extension(ext: str) -> str:
    mapping = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".tiff": "image/tiff",
        ".tif": "image/tiff",
        ".webp": "image/webp",
    }
    return mapping.get(ext, "application/octet-stream")
