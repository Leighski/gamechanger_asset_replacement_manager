"""Layer Colour Service — apply Design Specification colours to mapped PSD layers."""

from __future__ import annotations

import io

import numpy as np
from PIL import Image

from services.rendering.colour_mapper import ColourMapper, parse_hex_colour

COLOUR_FIELDS: dict[str, str] = {
    "primary_colour": "primary",
    "secondary_colour": "secondary",
    "third_colour": "accent",
    "sleeve_colour": "sleeve",
    "collar_colour": "collar",
    "trim_colour": "trim",
}


class LayerColourService:
    """Tint mapped PSD layer pixels using Design Specification colours."""

    def __init__(self) -> None:
        self._mapper = ColourMapper()

    def spec_colours(self, spec) -> dict[str, str]:
        return {key: str(spec.get_field(key) or "") for key in COLOUR_FIELDS}

    def tint_image(self, image: Image.Image, hex_colour: str) -> Image.Image:
        if not hex_colour:
            return image
        return self._mapper.tint_rgba(image, hex_colour)

    def apply_to_layer_pixels(self, layer, hex_colour: str) -> bool:
        if not hex_colour or not hasattr(layer, "topil"):
            return False
        try:
            image = layer.topil()
        except Exception:
            return False
        tinted = self.tint_image(image.convert("RGBA"), hex_colour)
        if hasattr(layer, "numpy"):
            layer.numpy = np.array(tinted)
            return True
        return False

    def image_to_png_bytes(self, image: Image.Image) -> bytes:
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return buffer.getvalue()
