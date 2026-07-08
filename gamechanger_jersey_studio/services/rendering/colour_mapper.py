"""Colour Mapper — apply Design Specification colours to component assets."""

from __future__ import annotations

import re

import numpy as np
from PIL import Image


_HEX_RE = re.compile(r"^#?([0-9A-Fa-f]{6})$")


def parse_hex_colour(value: str, fallback: tuple[int, int, int] = (128, 128, 128)) -> tuple[int, int, int]:
    if not value:
        return fallback
    match = _HEX_RE.match(value.strip())
    if not match:
        return fallback
    raw = match.group(1)
    return (int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16))


class ColourMapper:
    """Map solid Design Specification colours onto catalogue component images."""

    def tint_rgba(self, image: Image.Image, hex_colour: str, *, opacity: float = 1.0) -> Image.Image:
        rgb = parse_hex_colour(hex_colour)
        source = image.convert("RGBA")
        alpha = np.array(source.split()[-1], dtype=np.float32) / 255.0
        luminance = np.array(source.convert("L"), dtype=np.float32) / 255.0
        strength = np.clip(luminance[..., None], 0.15, 1.0)
        colour = np.array(rgb, dtype=np.float32)
        tinted = (colour * strength).astype(np.uint8)
        out_alpha = (alpha * opacity * 255.0).astype(np.uint8)
        result = np.dstack([tinted, out_alpha])
        return Image.fromarray(result, mode="RGBA")

    def spec_colours(self, spec) -> dict[str, str]:
        return {
            "primary": spec.primary_colour,
            "secondary": spec.secondary_colour,
            "accent": spec.third_colour,
            "trim": spec.trim_colour,
            "sleeve": spec.sleeve_colour,
            "collar": spec.collar_colour,
        }
