"""Smart Object Render Service — replace Smart Object contents from catalogue assets."""

from __future__ import annotations

import io

import numpy as np
from PIL import Image

from services.rendering.colour_mapper import ColourMapper


class SmartObjectRenderService:
    """Replace Smart Object embedded content without rasterising the parent PSD layer."""

    def __init__(self) -> None:
        self._colour = ColourMapper()

    def replace_layer_content(self, layer, image: Image.Image) -> bool:
        rgba = image.convert("RGBA")
        if hasattr(layer, "smart_object") and layer.smart_object is not None:
            buffer = io.BytesIO()
            rgba.save(buffer, format="PNG")
            layer.smart_object.data = buffer.getvalue()
            return True
        if hasattr(layer, "numpy"):
            layer.numpy = np.array(rgba)
            return True
        return False

    def component_image(
        self,
        source: Image.Image,
        *,
        hex_colour: str = "",
        size: tuple[int, int] | None = None,
    ) -> Image.Image:
        image = source.convert("RGBA")
        if size and image.size != size:
            image = image.resize(size, Image.Resampling.LANCZOS)
        if hex_colour:
            image = self._colour.tint_rgba(image, hex_colour)
        return image
