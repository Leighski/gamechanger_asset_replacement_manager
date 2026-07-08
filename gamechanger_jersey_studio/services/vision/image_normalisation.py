"""Image Normalisation — standard colour space and working copy."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from services.vision.image_loader import LoadedImage


@dataclass(frozen=True)
class NormalisedImage:
    pixels: np.ndarray
    width: int
    height: int
    colour_space: str = "sRGB"


class ImageNormaliser:
    """Convert loaded pixels to a standard sRGB working copy."""

    def normalise(self, loaded: LoadedImage) -> NormalisedImage:
        pixels = loaded.pixels.astype(np.float32)
        pixels = np.clip(pixels, 0.0, 255.0).astype(np.uint8)
        return NormalisedImage(
            pixels=pixels,
            width=loaded.width,
            height=loaded.height,
            colour_space="sRGB",
        )
