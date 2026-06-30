"""Image Loader — load reference bytes into a working array without modifying source."""

from __future__ import annotations

import io
from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageOps

from services.reference_image_io import ReferenceImageImportError


@dataclass(frozen=True)
class LoadedImage:
    pixels: np.ndarray
    width: int
    height: int
    source_checksum: str = ""


class ImageLoader:
    """Load immutable reference image bytes into an analysis-ready array."""

    def load(self, data: bytes, *, orientation: int = 0) -> LoadedImage:
        try:
            with Image.open(io.BytesIO(data)) as image:
                image = ImageOps.exif_transpose(image)
                if orientation:
                    image = image.rotate(-orientation, expand=True)
                rgb = image.convert("RGB")
                pixels = np.asarray(rgb, dtype=np.uint8)
        except Exception as exc:
            raise ReferenceImageImportError("Vision Engine could not load image") from exc
        if pixels.size == 0:
            raise ReferenceImageImportError("Vision Engine received an empty image")
        height, width = pixels.shape[:2]
        return LoadedImage(pixels=pixels, width=width, height=height)
