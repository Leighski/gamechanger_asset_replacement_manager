"""Texture Mapper — apply material texture catalogue components."""

from __future__ import annotations

import numpy as np
from PIL import Image, ImageChops


class TextureMapper:
    """Blend certified texture components onto rendered layers."""

    def apply_texture(self, base: Image.Image, texture_image: Image.Image, *, strength: float = 0.35) -> Image.Image:
        if strength <= 0.01:
            return base
        base_rgba = base.convert("RGBA")
        texture = texture_image.convert("RGBA").resize(base_rgba.size, Image.Resampling.BILINEAR)
        overlay = ImageChops.multiply(base_rgba.convert("RGB"), texture.convert("RGB")).convert("RGBA")
        overlay.putalpha(texture.split()[-1])
        data = np.array(base_rgba, dtype=np.float32)
        overlay_data = np.array(overlay, dtype=np.float32)
        blended = data * (1.0 - strength) + overlay_data * strength
        return Image.fromarray(blended.astype(np.uint8), mode="RGBA")
