"""Lighting Engine — apply certified lighting and shadow catalogue components."""

from __future__ import annotations

import numpy as np
from PIL import Image, ImageChops


class LightingEngine:
    """Apply catalogue lighting and shadow profiles — never invent effects."""

    def apply_shadow(self, base: Image.Image, shadow_image: Image.Image, *, strength: float = 0.45) -> Image.Image:
        if strength <= 0.01:
            return base
        base_rgba = base.convert("RGBA")
        shadow = shadow_image.convert("RGBA").resize(base_rgba.size, Image.Resampling.BILINEAR)
        grey = shadow.convert("L")
        darkened = ImageChops.multiply(base_rgba.convert("RGB"), ImageChops.invert(grey)).convert("RGBA")
        darkened.putalpha(base_rgba.split()[-1])
        data = np.array(base_rgba, dtype=np.float32)
        shadow_data = np.array(darkened, dtype=np.float32)
        blended = data * (1.0 - strength) + shadow_data * strength
        return Image.fromarray(blended.astype(np.uint8), mode="RGBA")

    def apply_lighting(self, base: Image.Image, lighting_image: Image.Image, *, strength: float = 0.4) -> Image.Image:
        if strength <= 0.01:
            return base
        base_rgba = base.convert("RGBA")
        light = lighting_image.convert("RGBA").resize(base_rgba.size, Image.Resampling.BILINEAR)
        lit = ImageChops.screen(base_rgba.convert("RGB"), light.convert("RGB")).convert("RGBA")
        lit.putalpha(base_rgba.split()[-1])
        data = np.array(base_rgba, dtype=np.float32)
        lit_data = np.array(lit, dtype=np.float32)
        blended = data * (1.0 - strength) + lit_data * strength
        return Image.fromarray(blended.astype(np.uint8), mode="RGBA")

    def apply_highlights(self, base: Image.Image, lighting_image: Image.Image, *, strength: float = 0.2) -> Image.Image:
        return self.apply_lighting(base, lighting_image, strength=strength)
